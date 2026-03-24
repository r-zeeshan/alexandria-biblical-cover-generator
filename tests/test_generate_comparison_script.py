from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from scripts import generate_comparison as gc


def _make_image(path: Path, *, size: tuple[int, int] = (640, 480), color: tuple[int, int, int] = (20, 40, 80)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="JPEG", quality=95)


def test_generate_comparison_grid_writes_output(tmp_path: Path) -> None:
    original = tmp_path / "original.jpg"
    composite = tmp_path / "composite.jpg"
    output = tmp_path / "compare.jpg"

    _make_image(original, size=(800, 600), color=(15, 20, 90))
    _make_image(composite, size=(800, 600), color=(15, 20, 90))
    with Image.open(composite).convert("RGB") as img:
        draw = ImageDraw.Draw(img)
        draw.ellipse((260, 160, 540, 440), fill=(220, 220, 230))
        img.save(composite, format="JPEG", quality=95)

    result = gc.generate_comparison_grid(
        original_path=original,
        composite_path=composite,
        output_path=output,
        book_number=1,
        book_title="Test Book",
        center_x=400,
        center_y=300,
        radius=150,
    )

    assert result == output
    assert output.exists()
    with Image.open(output) as rendered:
        assert rendered.width > 400
        assert rendered.height > 300


def test_generate_all_comparisons_writes_index_and_summary(tmp_path: Path) -> None:
    input_dir = tmp_path / "Input Covers"
    composited_dir = tmp_path / "tmp" / "composited"
    output_dir = tmp_path / "tmp" / "visual-qa"

    source_folder = input_dir / "1. Test Book copy"
    original = source_folder / "test.jpg"
    _make_image(original, size=(700, 500), color=(12, 30, 70))

    composite = composited_dir / "1" / "model_a" / "variant_1.jpg"
    _make_image(composite, size=(700, 500), color=(12, 30, 70))
    with Image.open(composite).convert("RGB") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((250, 140, 460, 360), fill=(230, 180, 120))
        img.save(composite, format="JPEG", quality=95)

    payload = gc.generate_all_comparisons(
        input_covers_dir=input_dir,
        composited_dir=composited_dir,
        output_dir=output_dir,
        catalog=[
            {"number": 1, "title": "Test Book", "folder_name": "1. Test Book copy"},
        ],
    )

    summary = payload.get("summary", {})
    assert int(summary.get("total", 0)) == 1
    assert int(summary.get("generated", 0)) == 1
    assert int(summary.get("not_compared", 0)) == 0
    assert isinstance(payload.get("comparisons"), list)
    assert len(payload.get("comparisons", [])) == 1

    index_path = output_dir / "index.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert isinstance(data.get("comparisons"), list)
    assert len(data.get("comparisons", [])) == 1


def test_generate_all_comparisons_counts_missing_pairs(tmp_path: Path) -> None:
    input_dir = tmp_path / "Input Covers"
    composited_dir = tmp_path / "tmp" / "composited"
    output_dir = tmp_path / "tmp" / "visual-qa"

    source_folder = input_dir / "2. Missing Composite copy"
    _make_image(source_folder / "source.jpg", size=(500, 500), color=(40, 60, 90))

    payload = gc.generate_all_comparisons(
        input_covers_dir=input_dir,
        composited_dir=composited_dir,
        output_dir=output_dir,
        catalog=[
            {"number": 2, "title": "Missing Composite", "folder_name": "2. Missing Composite copy"},
        ],
    )

    summary = payload.get("summary", {})
    assert int(summary.get("total", 0)) == 1
    assert int(summary.get("generated", 0)) == 0
    assert int(summary.get("not_compared", 0)) == 1
