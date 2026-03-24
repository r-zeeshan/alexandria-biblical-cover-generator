"""Print readiness validation for distributor-specific cover requirements."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image

from src import config, safe_json


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _specs_path(*, config_dir: Path | None = None) -> Path:
    root = config_dir or config.CONFIG_DIR
    return root / "print_specs.json"


class PrintValidator:
    def __init__(self, specs_path: Path | None = None):
        payload = safe_json.load_json(specs_path or _specs_path(), {})
        self.specs = payload if isinstance(payload, dict) else {}

    def distributor_spec(self, distributor: str) -> dict[str, Any]:
        token = str(distributor or "").strip().lower()
        if token not in self.specs:
            raise KeyError(f"Unknown distributor: {distributor}")
        row = self.specs.get(token)
        return dict(row) if isinstance(row, dict) else {}

    @staticmethod
    def _dpi(image: Image.Image) -> tuple[float, float]:
        dpi = image.info.get("dpi", ()) if isinstance(image.info, dict) else ()
        if isinstance(dpi, tuple) and len(dpi) >= 2:
            x = max(1.0, _safe_float(dpi[0], 300.0))
            y = max(1.0, _safe_float(dpi[1], 300.0))
            return x, y
        return 300.0, 300.0

    def validate_bleed(self, image: Image.Image, spec: dict[str, Any]) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        required = max(0.0, _safe_float(spec.get("bleed_inches"), 0.125))
        actual_override = spec.get("actual_bleed_inches", {})
        actual_by_side = actual_override if isinstance(actual_override, dict) else {}

        for side in ("top", "bottom", "left", "right"):
            actual = _safe_float(actual_by_side.get(side), required)
            if actual + 1e-9 >= required:
                continue
            errors.append(
                {
                    "type": "bleed",
                    "side": side,
                    "actual_inches": round(actual, 4),
                    "required_inches": round(required, 4),
                    "message": f"Insufficient bleed on {side} edge",
                }
            )

        if errors:
            return errors

        width, height = image.size
        dpi_x, dpi_y = self._dpi(image)
        min_bleed_px_x = int(math.ceil(required * dpi_x))
        min_bleed_px_y = int(math.ceil(required * dpi_y))
        if width <= min_bleed_px_x * 2:
            errors.append(
                {
                    "type": "bleed",
                    "side": "left",
                    "actual_inches": 0.0,
                    "required_inches": round(required, 4),
                    "message": "Insufficient bleed on left edge",
                }
            )
        if height <= min_bleed_px_y * 2:
            errors.append(
                {
                    "type": "bleed",
                    "side": "top",
                    "actual_inches": 0.0,
                    "required_inches": round(required, 4),
                    "message": "Insufficient bleed on top edge",
                }
            )
        return errors

    def validate_safe_zone(
        self,
        image: Image.Image,
        text_elements: list[dict[str, Any]] | None,
        spec: dict[str, Any],
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        rows = text_elements if isinstance(text_elements, list) else []
        safe_zone_inches = max(0.0, _safe_float(spec.get("safe_zone_inches"), 0.125))
        dpi_x, dpi_y = self._dpi(image)
        margin_x = int(math.ceil(safe_zone_inches * dpi_x))
        margin_y = int(math.ceil(safe_zone_inches * dpi_y))
        width, height = image.size

        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            x = _safe_int(row.get("x"), 0)
            y = _safe_int(row.get("y"), 0)
            w = max(0, _safe_int(row.get("width"), 0))
            h = max(0, _safe_int(row.get("height"), 0))
            label = str(row.get("label", f"element_{idx + 1}"))
            if x < margin_x or y < margin_y or (x + w) > (width - margin_x) or (y + h) > (height - margin_y):
                errors.append(
                    {
                        "type": "safe_zone",
                        "element": label,
                        "required_margin_inches": round(safe_zone_inches, 4),
                        "message": f"Text element '{label}' crosses safe zone boundary",
                    }
                )
        return errors

    def validate_resolution(self, image: Image.Image, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        min_dpi = max(1, _safe_int(spec.get("minimum_dpi"), 300))
        dpi_x, dpi_y = self._dpi(image)

        if dpi_x < min_dpi or dpi_y < min_dpi:
            errors.append(
                {
                    "type": "resolution",
                    "actual_dpi": [round(dpi_x, 2), round(dpi_y, 2)],
                    "required_dpi": min_dpi,
                    "message": "Image DPI is below minimum print requirement",
                }
            )
        elif dpi_x <= (min_dpi + 20) or dpi_y <= (min_dpi + 20):
            warnings.append(
                {
                    "type": "resolution",
                    "actual_dpi": [round(dpi_x, 2), round(dpi_y, 2)],
                    "required_dpi": min_dpi,
                    "message": "Resolution acceptable but consider higher DPI for safety",
                }
            )
        return errors, warnings

    def validate_color_profile(self, image: Image.Image, spec: dict[str, Any]) -> list[dict[str, Any]]:
        required = str(spec.get("color_profile", "RGB")).strip().upper() or "RGB"
        mode = str(image.mode or "").upper()
        if required == "CMYK":
            valid = mode in {"CMYK"}
        else:
            valid = mode in {"RGB", "RGBA"}
        if valid:
            return []
        return [
            {
                "type": "color_profile",
                "actual_mode": mode,
                "required_mode": required,
                "message": "Image color mode does not match distributor requirement",
            }
        ]

    def validate_file_size(self, file_path: Path | None, spec: dict[str, Any]) -> list[dict[str, Any]]:
        if file_path is None:
            return []
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return [
                {
                    "type": "file_size",
                    "message": "File does not exist for size validation",
                }
            ]
        max_mb = max(0.1, _safe_float(spec.get("max_file_size_mb"), 40.0))
        actual_mb = float(path.stat().st_size) / (1024.0 * 1024.0)
        if actual_mb <= max_mb:
            return []
        return [
            {
                "type": "file_size",
                "actual_mb": round(actual_mb, 4),
                "required_max_mb": round(max_mb, 4),
                "message": "File exceeds distributor max file size",
            }
        ]

    def validate_all(
        self,
        image: Image.Image,
        text_elements: list[dict[str, Any]] | None,
        file_path: Path | None,
        distributor: str,
    ) -> dict[str, Any]:
        spec = self.distributor_spec(distributor)
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        errors.extend(self.validate_bleed(image, spec))
        errors.extend(self.validate_safe_zone(image, text_elements, spec))
        resolution_errors, resolution_warnings = self.validate_resolution(image, spec)
        errors.extend(resolution_errors)
        warnings.extend(resolution_warnings)
        errors.extend(self.validate_color_profile(image, spec))
        errors.extend(self.validate_file_size(file_path, spec))

        return {
            "distributor": str(distributor),
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def validate_for_all_distributors(
        self,
        image: Image.Image,
        text_elements: list[dict[str, Any]] | None,
        file_path: Path | None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for distributor in sorted(self.specs.keys()):
            results[distributor] = self.validate_all(image, text_elements, file_path, distributor)
        return results
