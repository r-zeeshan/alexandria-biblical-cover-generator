#!/usr/bin/env python3
"""Generate visual comparison grids for compositor output verification."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src import config
    from src import safe_json
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore
    import safe_json  # type: ignore

CENTER_X = 2864
CENTER_Y = 1620
RADIUS = 500
FRAME_CHANGED_THRESHOLD_PCT = 2.0
FRAME_MEAN_DELTA_THRESHOLD = 5.0


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_project_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _find_original_image(folder: Path) -> Path | None:
    if not folder.exists() or not folder.is_dir():
        return None
    candidates = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"}])
    return candidates[0] if candidates else None


def _find_latest_composite_for_book(composited_dir: Path, book_number: int) -> Path | None:
    book_dir = composited_dir / str(int(book_number))
    if not book_dir.exists() or not book_dir.is_dir():
        return None
    candidates = [p for p in book_dir.rglob("variant_*.jpg") if p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _ensure_same_size(original: Image.Image, composite: Image.Image) -> tuple[Image.Image, Image.Image]:
    if original.size == composite.size:
        return original, composite
    return original, composite.resize(original.size, Image.LANCZOS)


def _difference_metrics(
    original_arr: np.ndarray,
    composite_arr: np.ndarray,
    *,
    center_x: int = CENTER_X,
    center_y: int = CENTER_Y,
    radius: int = RADIUS,
) -> dict[str, float | str]:
    diff = np.abs(original_arr.astype(np.float32) - composite_arr.astype(np.float32))
    max_diff = diff.max(axis=2)
    height, width = original_arr.shape[:2]
    cx = int(np.clip(int(center_x), 0, max(0, width - 1)))
    cy = int(np.clip(int(center_y), 0, max(0, height - 1)))
    y_grid, x_grid = np.ogrid[:original_arr.shape[0], :original_arr.shape[1]]
    dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)
    frame_mask = (dist >= max(0, int(radius) - 120)) & (dist <= int(radius) + 20)
    frame_values = max_diff[frame_mask]
    if frame_values.size == 0:
        changed_pct = 0.0
        mean_delta = 0.0
        max_delta = 0.0
    else:
        changed_pct = float(np.sum(frame_values > 2.0)) / float(frame_values.size) * 100.0
        mean_delta = float(frame_values.mean())
        max_delta = float(frame_values.max())
    verdict = "PASS" if (changed_pct < FRAME_CHANGED_THRESHOLD_PCT and mean_delta < FRAME_MEAN_DELTA_THRESHOLD) else "FAIL"
    return {
        "frame_changed_pct": round(changed_pct, 4),
        "frame_mean_delta": round(mean_delta, 4),
        "frame_max_delta": round(max_delta, 4),
        "verdict": verdict,
    }


def generate_comparison_grid(
    original_path: str | Path,
    composite_path: str | Path,
    output_path: str | Path,
    *,
    book_number: int = 0,
    book_title: str = "",
    center_x: int = CENTER_X,
    center_y: int = CENTER_Y,
    radius: int = RADIUS,
) -> Path:
    """Generate side-by-side + zoom + heatmap comparison grid."""
    original = Image.open(Path(original_path)).convert("RGB")
    composite = Image.open(Path(composite_path)).convert("RGB")
    original, composite = _ensure_same_size(original, composite)

    original_arr = np.array(original, dtype=np.uint8)
    composite_arr = np.array(composite, dtype=np.uint8)
    metrics = _difference_metrics(original_arr, composite_arr, center_x=center_x, center_y=center_y, radius=radius)

    ow, oh = original.size
    cx = int(np.clip(int(center_x), 0, max(0, ow - 1)))
    cy = int(np.clip(int(center_y), 0, max(0, oh - 1)))
    scale = min(600 / max(1, ow), 400 / max(1, oh))
    thumb_w = max(1, int(round(ow * scale)))
    thumb_h = max(1, int(round(oh * scale)))

    orig_thumb = original.resize((thumb_w, thumb_h), Image.LANCZOS)
    comp_thumb = composite.resize((thumb_w, thumb_h), Image.LANCZOS)

    row1_w = thumb_w * 2 + 20
    row1_h = thumb_h + 40
    row1 = Image.new("RGB", (row1_w, row1_h), (30, 30, 30))
    row1.paste(orig_thumb, (0, 40))
    row1.paste(comp_thumb, (thumb_w + 20, 40))
    draw1 = ImageDraw.Draw(row1)
    draw1.text((thumb_w // 2, 10), "ORIGINAL", fill=(120, 255, 120), anchor="mt")
    draw1.text((thumb_w + 20 + thumb_w // 2, 10), "COMPOSITE", fill=(255, 220, 120), anchor="mt")

    crop_margin = max(40, int(radius) + 100)
    crop_left = max(0, cx - crop_margin)
    crop_top = max(0, cy - crop_margin)
    crop_right = min(ow, cx + crop_margin)
    crop_bottom = min(oh, cy + crop_margin)
    if crop_right <= crop_left:
        crop_left = 0
        crop_right = ow
    if crop_bottom <= crop_top:
        crop_top = 0
        crop_bottom = oh

    orig_crop = original.crop((crop_left, crop_top, crop_right, crop_bottom))
    comp_crop = composite.crop((crop_left, crop_top, crop_right, crop_bottom))
    crop_w, crop_h = orig_crop.size
    zoom = min(600 / max(1, crop_w), 500 / max(1, crop_h))
    zoom_w = max(1, int(round(crop_w * zoom)))
    zoom_h = max(1, int(round(crop_h * zoom)))
    orig_zoom = orig_crop.resize((zoom_w, zoom_h), Image.LANCZOS)
    comp_zoom = comp_crop.resize((zoom_w, zoom_h), Image.LANCZOS)

    row2_w = zoom_w * 2 + 20
    row2_h = zoom_h + 40
    row2 = Image.new("RGB", (row2_w, row2_h), (30, 30, 30))
    row2.paste(orig_zoom, (0, 40))
    row2.paste(comp_zoom, (zoom_w + 20, 40))
    draw2 = ImageDraw.Draw(row2)
    draw2.text((zoom_w // 2, 10), "ORIGINAL (medallion zoom)", fill=(120, 255, 120), anchor="mt")
    draw2.text((zoom_w + 20 + zoom_w // 2, 10), "COMPOSITE (medallion zoom)", fill=(255, 220, 120), anchor="mt")

    max_diff = np.abs(original_arr.astype(np.float32) - composite_arr.astype(np.float32)).max(axis=2)
    heatmap = np.zeros((oh, ow, 3), dtype=np.uint8)
    heatmap[:, :, 0] = np.clip(max_diff * 3.0, 0, 255).astype(np.uint8)
    heatmap[:, :, 1] = np.where(max_diff < 2.0, 40, 0).astype(np.uint8)
    heatmap[:, :, 2] = np.where(max_diff < 2.0, 40, 0).astype(np.uint8)
    heatmap_img = Image.fromarray(heatmap, mode="RGB")
    heat_thumb = heatmap_img.resize((thumb_w * 2 + 20, thumb_h), Image.LANCZOS)

    row3_w = thumb_w * 2 + 20
    row3_h = thumb_h + 60
    row3 = Image.new("RGB", (row3_w, row3_h), (30, 30, 30))
    row3.paste(heat_thumb, (0, 60))
    draw3 = ImageDraw.Draw(row3)
    draw3.text((row3_w // 2, 10), "DIFFERENCE HEATMAP (red = changed pixels)", fill=(255, 120, 120), anchor="mt")
    verdict = str(metrics.get("verdict", "FAIL"))
    verdict_color = (120, 255, 120) if verdict == "PASS" else (255, 80, 80)
    stats_text = (
        f"Frame ring: {float(metrics.get('frame_changed_pct', 0.0)):.1f}% changed"
        f" | Mean delta: {float(metrics.get('frame_mean_delta', 0.0)):.1f} [{verdict}]"
    )
    draw3.text((row3_w // 2, 35), stats_text, fill=verdict_color, anchor="mt")

    max_w = max(row1_w, row2_w, row3_w)
    total_h = row1_h + row2_h + row3_h + 80
    grid = Image.new("RGB", (max_w, total_h), (20, 20, 20))
    draw = ImageDraw.Draw(grid)
    header = f"Book {book_number}: {book_title}" if int(book_number) > 0 else "Comparison Grid"
    draw.text((max_w // 2, 20), header, fill=(255, 255, 255), anchor="mt")
    draw.text((max_w // 2, 45), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), fill=(160, 160, 160), anchor="mt")

    y = 80
    grid.paste(row1, ((max_w - row1_w) // 2, y))
    y += row1_h
    grid.paste(row2, ((max_w - row2_w) // 2, y))
    y += row2_h
    grid.paste(row3, ((max_w - row3_w) // 2, y))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    grid.save(destination, format="JPEG", quality=90)
    return destination


def _build_catalog_rows(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in catalog:
        if not isinstance(row, dict):
            continue
        number = _safe_int(row.get("number"), 0)
        if number <= 0:
            continue
        rows.append(
            {
                "number": number,
                "title": str(row.get("title", f"Book {number}")),
                "folder_name": str(row.get("folder_name", "")).strip(),
            }
        )
    rows.sort(key=lambda item: int(item["number"]))
    return rows


def generate_all_comparisons(
    *,
    input_covers_dir: str | Path,
    composited_dir: str | Path,
    output_dir: str | Path,
    catalog: list[dict[str, Any]] | None = None,
    book_numbers: list[int] | None = None,
) -> dict[str, Any]:
    """Generate comparison grids for all comparable books and save index metadata."""
    input_root = Path(input_covers_dir)
    composite_root = Path(composited_dir)
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    catalog_rows = _build_catalog_rows(catalog or [])
    if not catalog_rows:
        discovered = sorted(
            {_safe_int(path.name, 0) for path in composite_root.iterdir() if path.is_dir() and path.name.isdigit()}
        )
        catalog_rows = [{"number": n, "title": f"Book {n}", "folder_name": ""} for n in discovered if n > 0]

    wanted = {int(n) for n in (book_numbers or []) if int(n) > 0}
    if wanted:
        catalog_rows = [row for row in catalog_rows if int(row.get("number", 0)) in wanted]

    generated_at = datetime.now(timezone.utc).isoformat()
    comparisons: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for row in catalog_rows:
        number = int(row["number"])
        title = str(row["title"])
        folder_name = str(row.get("folder_name", "") or "").strip()

        original = _find_original_image(input_root / folder_name) if folder_name else None
        if original is None:
            fallback_dirs = sorted([p for p in input_root.glob(f"{number}.*") if p.is_dir()])
            for candidate_dir in fallback_dirs:
                original = _find_original_image(candidate_dir)
                if original is not None:
                    break

        composite = _find_latest_composite_for_book(composite_root, number)
        if original is None or composite is None:
            missing.append(
                {
                    "book_number": number,
                    "book_title": title,
                    "missing_original": original is None,
                    "missing_composite": composite is None,
                }
            )
            continue

        output_image = out_root / f"compare_{number:03d}.jpg"
        generate_comparison_grid(
            original_path=original,
            composite_path=composite,
            output_path=output_image,
            book_number=number,
            book_title=title,
        )

        original_arr = np.array(Image.open(original).convert("RGB"), dtype=np.uint8)
        composite_arr = np.array(Image.open(composite).convert("RGB"), dtype=np.uint8)
        if original_arr.shape != composite_arr.shape:
            resized = Image.fromarray(composite_arr, mode="RGB").resize((original_arr.shape[1], original_arr.shape[0]), Image.LANCZOS)
            composite_arr = np.array(resized, dtype=np.uint8)
        metrics = _difference_metrics(original_arr, composite_arr)
        comparisons.append(
            {
                "book_number": number,
                "book_title": title,
                "comparison_path": _to_project_relative(output_image),
                "comparison_abs_path": str(output_image.resolve()),
                "original_path": _to_project_relative(original),
                "composite_path": _to_project_relative(composite),
                "frame_changed_pct": float(metrics["frame_changed_pct"]),
                "frame_mean_delta": float(metrics["frame_mean_delta"]),
                "frame_max_delta": float(metrics["frame_max_delta"]),
                "verdict": str(metrics["verdict"]),
                "generated_at": generated_at,
            }
        )

    comparisons.sort(
        key=lambda row: (
            0 if str(row.get("verdict", "")).upper() == "FAIL" else 1,
            -float(row.get("frame_changed_pct", 0.0)),
            -float(row.get("frame_mean_delta", 0.0)),
            int(row.get("book_number", 0)),
        )
    )

    summary = {
        "total": len(catalog_rows),
        "generated": len(comparisons),
        "passed": sum(1 for row in comparisons if str(row.get("verdict", "")).upper() == "PASS"),
        "failed": sum(1 for row in comparisons if str(row.get("verdict", "")).upper() == "FAIL"),
        "not_compared": len(missing),
    }

    payload = {
        "generated_at": generated_at,
        "comparisons": comparisons,
        "missing": missing,
        "summary": summary,
    }
    safe_json.atomic_write_json(out_root / "index.json", payload)
    return payload


def _load_catalog_for_runtime(runtime: config.Config) -> list[dict[str, Any]]:
    payload = safe_json.load_json(runtime.book_catalog_path, [])
    return payload if isinstance(payload, list) else []


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="Generate visual comparison grids")
    parser.add_argument("--catalog", type=str, default=config.DEFAULT_CATALOG_ID, help="Catalog id")
    parser.add_argument("--book", type=int, help="Single book number to compare")
    parser.add_argument("--all", action="store_true", help="Compare all available books")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/visual-qa"), help="Output directory for comparison images")
    args = parser.parse_args()

    runtime = config.get_config(args.catalog)
    books: list[int] | None = None
    if args.book and args.book > 0:
        books = [int(args.book)]
    elif not args.all:
        args.all = True

    result = generate_all_comparisons(
        input_covers_dir=runtime.input_dir,
        composited_dir=runtime.tmp_dir / "composited",
        output_dir=args.output_dir,
        catalog=_load_catalog_for_runtime(runtime),
        book_numbers=books,
    )

    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    print(
        "Comparison summary: "
        f"total={_safe_int(summary.get('total'))} "
        f"generated={_safe_int(summary.get('generated'))} "
        f"passed={_safe_int(summary.get('passed'))} "
        f"failed={_safe_int(summary.get('failed'))} "
        f"not_compared={_safe_int(summary.get('not_compared'))}"
    )

    failures = [row for row in result.get("comparisons", []) if isinstance(row, dict) and str(row.get("verdict", "")).upper() == "FAIL"]
    for row in failures:
        print(
            f"FAIL book={_safe_int(row.get('book_number'))} "
            f"changed={float(row.get('frame_changed_pct', 0.0)):.2f}% "
            f"delta={float(row.get('frame_mean_delta', 0.0)):.2f} "
            f"path={row.get('comparison_path')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
