from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from src import focus_crop


def _subject_bounds(image: Image.Image) -> tuple[float, float]:
    arr = np.array(image.convert("RGB"), dtype=np.uint8)
    mask = (arr[..., 0] > 200) & (arr[..., 1] > 120) & (arr[..., 2] < 80)
    ys, xs = np.where(mask)
    assert xs.size > 0
    assert ys.size > 0
    return float(xs.mean()), float(ys.mean())


def test_smart_square_crop_recenters_off_axis_subject():
    image = Image.new("RGB", (900, 600), (18, 24, 52))
    draw = ImageDraw.Draw(image, "RGB")
    draw.rectangle((640, 140, 835, 470), fill=(246, 168, 26))

    naive = image.crop((150, 0, 750, 600))
    cropped = focus_crop.smart_square_crop(image)

    assert cropped.size == (600, 600)
    naive_x, _naive_y = _subject_bounds(naive)
    mean_x, mean_y = _subject_bounds(cropped)
    assert abs(mean_x - 300.0) < abs(naive_x - 300.0)
    assert (abs(naive_x - 300.0) - abs(mean_x - 300.0)) >= 100.0
    assert abs(mean_y - 305.0) <= 80.0


def test_smart_fit_biases_toward_subject_in_rectangular_resize():
    image = Image.new("RGB", (1000, 540), (12, 18, 42))
    draw = ImageDraw.Draw(image, "RGB")
    draw.rectangle((760, 110, 960, 430), fill=(245, 170, 22))

    naive = ImageOps.fit(image, (420, 420), method=Image.LANCZOS, centering=(0.5, 0.5))
    fitted = focus_crop.smart_fit(image, (420, 420))

    assert fitted.size == (420, 420)
    naive_x, _naive_y = _subject_bounds(naive)
    mean_x, mean_y = _subject_bounds(fitted)
    assert abs(mean_x - 210.0) < abs(naive_x - 210.0)
    assert (abs(naive_x - 210.0) - abs(mean_x - 210.0)) >= 40.0
    assert abs(mean_y - 210.0) <= 90.0
