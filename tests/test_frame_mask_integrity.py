from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def test_frame_mask_integrity() -> None:
    mask_path = Path("config/frame_mask.png")
    assert mask_path.exists(), "config/frame_mask.png is missing"

    mask = Image.open(mask_path).convert("L")
    arr = np.array(mask, dtype=np.uint8)

    assert mask.size == (3784, 2777), f"Wrong size: {mask.size}"
    assert int(arr.min()) < 10, "No transparent region found"
    assert int(arr.max()) > 245, "No opaque region found"

    hole = arr < 128
    ys, xs = np.where(hole)
    assert len(xs) > 0 and len(ys) > 0, "Frame mask hole was not detected"
    center_x = float(xs.mean())
    center_y = float(ys.mean())
    assert abs(center_x - 2864) < 50, f"Hole center X off: {center_x:.2f}"
    assert abs(center_y - 1620) < 50, f"Hole center Y off: {center_y:.2f}"

    opaque_ratio = float((arr > 200).sum() / arr.size)
    assert opaque_ratio > 0.80, f"Too little frame retained: {opaque_ratio:.2%}"
