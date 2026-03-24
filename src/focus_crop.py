"""Focus-aware crop helpers for medallion-safe AI art placement."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps


def _normalize_map(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32)
    if arr.size <= 0:
        return arr
    finite = arr[np.isfinite(arr)]
    if finite.size <= 0:
        return np.zeros_like(arr, dtype=np.float32)
    scale = float(np.percentile(finite, 95))
    if scale <= 1e-6:
        scale = float(finite.max()) if finite.size else 0.0
    if scale <= 1e-6:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip(arr / scale, 0.0, 1.0)


def _border_background(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    band_y = max(1, int(round(h * 0.08)))
    band_x = max(1, int(round(w * 0.08)))
    strips = [
        rgb[:band_y, :, :].reshape(-1, 3),
        rgb[max(0, h - band_y):, :, :].reshape(-1, 3),
        rgb[:, :band_x, :].reshape(-1, 3),
        rgb[:, max(0, w - band_x):, :].reshape(-1, 3),
    ]
    pixels = np.concatenate(strips, axis=0)
    return np.median(pixels, axis=0)


def _focus_weights(image: Image.Image) -> np.ndarray:
    rgba = np.array(image.convert("RGBA"), dtype=np.float32)
    h, w = rgba.shape[:2]
    if h <= 1 or w <= 1:
        return np.zeros((max(1, h), max(1, w)), dtype=np.float32)

    alpha = rgba[..., 3]
    active_alpha = alpha > 24.0
    alpha_coverage = float(active_alpha.mean()) if active_alpha.size else 1.0
    if 0.01 < alpha_coverage < 0.98:
        weights = np.where(active_alpha, alpha / 255.0, 0.0).astype(np.float32)
        if float(weights.sum()) > 1e-3:
            return weights

    rgb = rgba[..., :3]
    background = _border_background(rgb)
    color_distance = np.sqrt(np.sum((rgb - background) ** 2, axis=2))

    gray = (0.299 * rgb[..., 0]) + (0.587 * rgb[..., 1]) + (0.114 * rgb[..., 2])
    edge_x = np.pad(np.abs(np.diff(gray, axis=1)), ((0, 0), (0, 1)), mode="constant")
    edge_y = np.pad(np.abs(np.diff(gray, axis=0)), ((0, 1), (0, 0)), mode="constant")
    edge_strength = edge_x + edge_y
    saturation = rgb.max(axis=2) - rgb.min(axis=2)

    score = (
        (0.58 * _normalize_map(color_distance))
        + (0.27 * _normalize_map(edge_strength))
        + (0.15 * _normalize_map(saturation))
    )

    margin_y = max(1, int(round(h * 0.04)))
    margin_x = max(1, int(round(w * 0.04)))
    score[:margin_y, :] *= 0.35
    score[max(0, h - margin_y):, :] *= 0.35
    score[:, :margin_x] *= 0.35
    score[:, max(0, w - margin_x):] *= 0.35

    if float(score.max()) <= 1e-6:
        return np.zeros((h, w), dtype=np.float32)

    finite = score[np.isfinite(score)]
    threshold = max(
        float(np.percentile(finite, 90)),
        float(finite.mean() + (finite.std() * 0.75)),
        float(score.max() * 0.40),
    )
    mask = score >= threshold
    if float(mask.mean()) < 0.002:
        threshold = max(float(np.percentile(finite, 82)), float(score.max() * 0.30))
        mask = score >= threshold

    weights = np.where(mask, score, 0.0).astype(np.float32)
    if float(weights.sum()) > 1e-3:
        return weights
    return score.astype(np.float32)


def focus_centering(image: Image.Image) -> tuple[float, float]:
    weights = _focus_weights(image)
    h, w = weights.shape[:2]
    if h <= 1 or w <= 1:
        return 0.5, 0.5

    total = float(weights.sum())
    if total <= 1e-6:
        return 0.5, 0.5

    yy, xx = np.indices((h, w), dtype=np.float32)
    center_x = float((xx * weights).sum() / total) / float(max(1, w - 1))
    center_y = float((yy * weights).sum() / total) / float(max(1, h - 1))

    damped_x = 0.5 + ((center_x - 0.5) * 0.72)
    damped_y = 0.5 + ((center_y - 0.5) * 0.72)
    return (
        float(np.clip(damped_x, 0.18, 0.82)),
        float(np.clip(damped_y, 0.18, 0.82)),
    )


def smart_square_crop(image: Image.Image) -> Image.Image:
    src = image.convert("RGBA")
    width, height = src.size
    if width <= 1 or height <= 1:
        return src

    side = min(width, height)
    focus_x, focus_y = focus_centering(src)
    center_x = focus_x * float(width - 1)
    center_y = focus_y * float(height - 1)

    left = int(round(center_x - (side / 2.0)))
    top = int(round(center_y - (side / 2.0)))
    left = max(0, min(left, width - side))
    top = max(0, min(top, height - side))
    return src.crop((left, top, left + side, top + side))


def smart_fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    src = image.convert("RGB")
    centering = focus_centering(src)
    return ImageOps.fit(src, size, method=Image.LANCZOS, centering=centering)
