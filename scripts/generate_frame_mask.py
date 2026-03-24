#!/usr/bin/env python3
"""Generate config/frame_mask.png from fixed medallion geometry."""

from pathlib import Path

from PIL import Image, ImageDraw

WIDTH = 3784
HEIGHT = 2777
CENTER_X = 2864
CENTER_Y = 1620
OPENING_RADIUS = 455
SUPERSAMPLE_SCALE = 4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "config" / "frame_mask.png"


def generate_frame_mask() -> Path:
    large = Image.new("L", (WIDTH * SUPERSAMPLE_SCALE, HEIGHT * SUPERSAMPLE_SCALE), 255)
    draw_large = ImageDraw.Draw(large)

    cx = CENTER_X * SUPERSAMPLE_SCALE
    cy = CENTER_Y * SUPERSAMPLE_SCALE
    radius = OPENING_RADIUS * SUPERSAMPLE_SCALE
    draw_large.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=0)

    mask = large.resize((WIDTH, HEIGHT), Image.LANCZOS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mask.save(OUTPUT_PATH)
    return OUTPUT_PATH


def main() -> None:
    path = generate_frame_mask()
    print(
        f"Generated frame_mask.png: {WIDTH}x{HEIGHT}, opening at "
        f"({CENTER_X},{CENTER_Y}) r={OPENING_RADIUS} -> {path}"
    )


if __name__ == "__main__":
    main()
