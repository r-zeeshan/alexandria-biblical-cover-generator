from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from src import safe_image


def _truncated_image_bytes(fmt: str, *, trim: int) -> bytes:
    image = Image.new("RGB", (64, 64), (255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()[:-trim]


def test_load_image_repairs_small_truncated_jpeg(tmp_path: Path):
    target = tmp_path / "sample.jpg"
    target.write_bytes(_truncated_image_bytes("JPEG", trim=15))

    recovered = safe_image.load_image(target, mode="RGB", repair=True)

    assert recovered.size == (64, 64)
    strict = safe_image.load_image(target, mode="RGB", repair=False)
    assert strict.size == (64, 64)


def test_load_image_repairs_small_truncated_png(tmp_path: Path):
    target = tmp_path / "sample.png"
    target.write_bytes(_truncated_image_bytes("PNG", trim=68))

    recovered = safe_image.load_image(target, mode="RGB", repair=True)

    assert recovered.size == (64, 64)
    strict = safe_image.load_image(target, mode="RGB", repair=False)
    assert strict.size == (64, 64)


def test_atomic_write_image_bytes_writes_strictly_loadable_png(tmp_path: Path):
    target = tmp_path / "written.png"
    image = Image.new("RGB", (32, 24), (0, 128, 255))
    payload = io.BytesIO()
    image.save(payload, format="PNG")

    safe_image.atomic_write_image_bytes(target, payload.getvalue())

    loaded = safe_image.load_image(target, mode="RGB", repair=False)
    assert loaded.size == (32, 24)
