#!/usr/bin/env python3
"""Generate a pixel-accurate frame mask from template PNG analysis.

Mask contract:
- 255 = preserved frame/background (opaque)
- 0 = art opening (transparent punch)
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "config" / "templates"
DEFAULT_OUTPUT = PROJECT_ROOT / "config" / "frame_mask.png"
DEFAULT_CENTER_X = 2864
DEFAULT_CENTER_Y = 1620


def _pick_template(
    path_hint: str | None,
    *,
    center_x: int,
    center_y: int,
    scan_min_radius: int,
    scan_max_radius: int,
    lookahead_px: int,
    min_hits: int,
) -> Path:
    if path_hint:
        candidate = Path(path_hint).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if not candidate.exists():
            raise FileNotFoundError(f"Template not found: {candidate}")
        return candidate

    candidates = sorted(TEMPLATE_DIR.glob("*_template.png"))
    if not candidates:
        raise FileNotFoundError(f"No template PNGs found in {TEMPLATE_DIR}")
    best: tuple[float, Path] | None = None
    for candidate in candidates:
        img = Image.open(candidate).convert("RGB")
        rgb = np.array(img, dtype=np.uint8)
        height, width = rgb.shape[0], rgb.shape[1]
        if not (0 <= center_x < width and 0 <= center_y < height):
            continue
        hsv = np.array(img.convert("HSV"), dtype=np.uint8)
        radii = _scan_radii(
            rgb,
            hsv,
            cx=center_x,
            cy=center_y,
            r_min=scan_min_radius,
            r_max=scan_max_radius,
            lookahead_px=lookahead_px,
            min_hits=min_hits,
        )
        values = np.array([int(v) for _, v in sorted(radii.items())], dtype=np.int32)
        frac_min = float((values == int(scan_min_radius)).mean())
        median = float(np.median(values))
        q1, q3 = np.percentile(values, [25, 75]).tolist()
        spread = float(q3 - q1)
        score = (1.0 - frac_min) * 2.0 + (spread / 120.0) - (abs(median - 455.0) / 120.0)
        if best is None or score > best[0]:
            best = (score, candidate)

    if best is None:
        return candidates[0]
    print(f"auto-selected template: {best[1]} (score={best[0]:.3f})")
    return best[1]


def _is_gold_or_ring_pixel(rgb: np.ndarray, hsv: np.ndarray, x: int, y: int) -> bool:
    h_val = int(hsv[y, x, 0])
    s_val = int(hsv[y, x, 1])
    v_val = int(hsv[y, x, 2])
    r_ch, g_ch, b_ch = [int(v) for v in rgb[y, x]]

    is_gold = (15 <= h_val <= 55) and (s_val > 40) and (v_val > 100)
    is_ring_band = (v_val > 80) and (s_val > 20) and (r_ch > g_ch > b_ch)
    return bool(is_gold or is_ring_band)


def _scan_radii(
    rgb: np.ndarray,
    hsv: np.ndarray,
    *,
    cx: int,
    cy: int,
    r_min: int,
    r_max: int,
    lookahead_px: int,
    min_hits: int,
) -> dict[int, int]:
    height, width = rgb.shape[0], rgb.shape[1]
    radii: dict[int, int] = {}
    for angle_deg in range(360):
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        radial_flags: list[bool] = []
        for r in range(r_min, r_max + 1):
            x = int(cx + r * cos_a)
            y = int(cy - r * sin_a)
            if not (0 <= x < width and 0 <= y < height):
                radial_flags.append(False)
                continue
            radial_flags.append(_is_gold_or_ring_pixel(rgb, hsv, x, y))

        found = None
        window = max(4, int(lookahead_px))
        needed = max(2, int(min_hits))
        for idx, r in enumerate(range(r_min, r_max + 1)):
            end = min(len(radial_flags), idx + window)
            if end <= idx:
                continue
            hits = int(sum(1 for flag in radial_flags[idx:end] if flag))
            if hits >= needed:
                found = r
                break

        radii[angle_deg] = int(found if found is not None else 450)
    return radii


def _smooth_radii(
    radii: dict[int, int],
    *,
    min_radius: int,
    max_radius: int,
    median_window: int = 9,
    mean_window: int = 7,
) -> dict[int, int]:
    values = np.array([int(radii.get(i, 450)) for i in range(360)], dtype=np.float32)
    if median_window > 1:
        half = max(1, int(median_window) // 2)
        out = np.zeros_like(values)
        for i in range(360):
            idx = [(i + off) % 360 for off in range(-half, half + 1)]
            out[i] = float(np.median(values[idx]))
        values = out
    if mean_window > 1:
        half = max(1, int(mean_window) // 2)
        out = np.zeros_like(values)
        for i in range(360):
            idx = [(i + off) % 360 for off in range(-half, half + 1)]
            out[i] = float(np.mean(values[idx]))
        values = out
    values = np.clip(values, int(min_radius), int(max_radius))
    return {i: int(round(values[i])) for i in range(360)}


def _build_mask(
    *,
    width: int,
    height: int,
    cx: int,
    cy: int,
    radii: dict[int, int],
    safety_inset: int,
    blur_radius: float,
    threshold: int,
) -> Image.Image:
    mask_img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(mask_img)

    points: list[tuple[float, float]] = []
    for angle_deg in range(360):
        angle_rad = math.radians(angle_deg)
        r = max(1, int(radii.get(angle_deg, 450)) - int(safety_inset))
        x = cx + r * math.cos(angle_rad)
        y = cy - r * math.sin(angle_rad)
        points.append((x, y))

    draw.polygon(points, fill=0)

    smoothed = mask_img.filter(ImageFilter.GaussianBlur(radius=float(blur_radius)))
    arr = np.array(smoothed, dtype=np.uint8)
    binary = np.where(arr > int(threshold), 255, 0).astype(np.uint8)
    return Image.fromarray(binary, mode="L")


def _print_radii_summary(radii: dict[int, int]) -> None:
    vals = np.array([int(v) for _, v in sorted(radii.items())], dtype=np.int32)
    q0, q25, q50, q75, q100 = np.percentile(vals, [0, 25, 50, 75, 100]).tolist()
    print(
        "radii summary:"
        f" min={q0:.1f} q25={q25:.1f} median={q50:.1f} q75={q75:.1f} max={q100:.1f}"
    )
    print(
        "cardinal radii:"
        f" 0°={radii.get(0)}"
        f" 90°={radii.get(90)}"
        f" 180°={radii.get(180)}"
        f" 270°={radii.get(270)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate config/frame_mask.png from template artwork")
    parser.add_argument("--template", default="", help="Optional template PNG path override")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output mask path")
    parser.add_argument("--center-x", type=int, default=DEFAULT_CENTER_X)
    parser.add_argument("--center-y", type=int, default=DEFAULT_CENTER_Y)
    parser.add_argument("--scan-min-radius", type=int, default=380)
    parser.add_argument("--scan-max-radius", type=int, default=550)
    parser.add_argument("--lookahead-px", type=int, default=24)
    parser.add_argument("--min-hits", type=int, default=10)
    parser.add_argument("--median-window", type=int, default=9)
    parser.add_argument("--mean-window", type=int, default=7)
    parser.add_argument("--safety-inset", type=int, default=5)
    parser.add_argument("--blur-radius", type=float, default=4.0)
    parser.add_argument("--threshold", type=int, default=128)
    args = parser.parse_args()

    template_path = _pick_template(
        args.template or None,
        center_x=int(args.center_x),
        center_y=int(args.center_y),
        scan_min_radius=int(args.scan_min_radius),
        scan_max_radius=int(args.scan_max_radius),
        lookahead_px=int(args.lookahead_px),
        min_hits=int(args.min_hits),
    )
    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    template = Image.open(template_path).convert("RGB")
    rgb = np.array(template, dtype=np.uint8)
    hsv = np.array(template.convert("HSV"), dtype=np.uint8)
    height, width = rgb.shape[0], rgb.shape[1]

    cx = int(args.center_x)
    cy = int(args.center_y)
    if not (0 <= cx < width and 0 <= cy < height):
        raise ValueError(f"Center ({cx}, {cy}) is outside template size ({width}, {height})")

    print(f"template: {template_path}")
    print(f"size: {width}x{height}")
    print(f"center: ({cx}, {cy})")
    print(f"scan radii: {args.scan_min_radius}..{args.scan_max_radius}")

    radii = _scan_radii(
        rgb,
        hsv,
        cx=cx,
        cy=cy,
        r_min=int(args.scan_min_radius),
        r_max=int(args.scan_max_radius),
        lookahead_px=int(args.lookahead_px),
        min_hits=int(args.min_hits),
    )
    radii = _smooth_radii(
        radii,
        min_radius=int(args.scan_min_radius),
        max_radius=int(args.scan_max_radius),
        median_window=int(args.median_window),
        mean_window=int(args.mean_window),
    )
    _print_radii_summary(radii)

    mask = _build_mask(
        width=width,
        height=height,
        cx=cx,
        cy=cy,
        radii=radii,
        safety_inset=int(args.safety_inset),
        blur_radius=float(args.blur_radius),
        threshold=int(args.threshold),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(output_path)
    print(f"wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
