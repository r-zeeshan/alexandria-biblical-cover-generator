from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from src.print_validator import PrintValidator


def _write_specs(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ingram_spark": {
                    "bleed_inches": 0.125,
                    "safe_zone_inches": 0.125,
                    "minimum_dpi": 300,
                    "color_profile": "CMYK",
                    "max_file_size_mb": 0.001,
                },
                "kdp": {
                    "bleed_inches": 0.125,
                    "safe_zone_inches": 0.0625,
                    "minimum_dpi": 300,
                    "color_profile": "RGB",
                    "max_file_size_mb": 10,
                },
            }
        ),
        encoding="utf-8",
    )


def test_print_validator_detects_dpi_color_and_file_size_issues(tmp_path: Path):
    specs = tmp_path / "print_specs.json"
    _write_specs(specs)
    validator = PrintValidator(specs_path=specs)

    image_path = tmp_path / "cover.jpg"
    Image.new("RGB", (1600, 2400), color=(30, 40, 70)).save(image_path, format="JPEG", dpi=(72, 72), quality=95)

    with Image.open(image_path) as image:
        result = validator.validate_all(image, [], image_path, "ingram_spark")
        assert result["passed"] is False
        error_types = {row.get("type") for row in result["errors"]}
        assert "resolution" in error_types
        assert "color_profile" in error_types

    large_blob = tmp_path / "large_blob.bin"
    large_blob.write_bytes(b"x" * 250_000)
    file_errors = validator.validate_file_size(large_blob, {"max_file_size_mb": 0.1})
    assert file_errors
    assert file_errors[0]["type"] == "file_size"


def test_print_validator_safe_zone_and_all_distributors(tmp_path: Path):
    specs = tmp_path / "print_specs.json"
    _write_specs(specs)
    validator = PrintValidator(specs_path=specs)

    image_path = tmp_path / "cover_rgb.png"
    Image.new("RGB", (2000, 3000), color=(20, 30, 50)).save(image_path, format="PNG", dpi=(300, 300))
    text_elements = [{"label": "title", "x": 1, "y": 1, "width": 1200, "height": 200}]

    with Image.open(image_path) as image:
        safe_zone_errors = validator.validate_safe_zone(image, text_elements, validator.distributor_spec("kdp"))
        assert safe_zone_errors
        bundle = validator.validate_for_all_distributors(image, [], image_path)
        assert set(bundle.keys()) == {"ingram_spark", "kdp"}
        assert isinstance(bundle["kdp"]["passed"], bool)
