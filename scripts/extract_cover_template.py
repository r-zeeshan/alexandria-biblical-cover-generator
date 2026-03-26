"""
extract_cover_template.py
=========================
Builds the full cover template by assembling individual ornament PNGs
(pre-extracted from classics covers) onto a clean navy canvas.

The ornaments in config/ornaments/ were extracted using a combination of:
  - 4-book pixel diff (pixels identical across all 4 classics = template)
  - Gold pixel detection (brightness > 100 AND R > B + 10)
  - Manual bounding box crops per ornament region

This programmatic assembly approach avoids ghost text artifacts that occur
with full-cover pixel diff (text varies per book but shares gold color).

Output
------
  config/cover_template_full.png  -- RGB, 3784x2777
    Navy background with all gold ornamental elements composited on top.

Usage
-----
  python scripts/extract_cover_template.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORNAMENTS_DIR = PROJECT_ROOT / "config" / "ornaments"
FRAME_OVERLAY = PROJECT_ROOT / "config" / "frame_overlay_template.png"
OUTPUT_PATH = PROJECT_ROOT / "config" / "cover_template_full.png"

# Cover dimensions — widened by 100px to add 50px gap on each side of spine
W, H = 3884, 2777

# Layout boundaries (original spine 1852-1927, now with 50px padding each side)
SPINE_LEFT = 1902
SPINE_RIGHT = 1977
SPINE_CENTER = (SPINE_LEFT + SPINE_RIGHT) // 2
FRONT_CENTER = (SPINE_RIGHT + W) // 2
BACK_CENTER = SPINE_LEFT // 2

# Navy background color (sampled from original covers)
NAVY = (10, 20, 52)

# Medallion frame center on front cover (measured from original)
# frame_overlay top-left at (2250, 830), size 1360x1353
# => center = (2250 + 680, 830 + 676) = (2930, 1506)
MEDALLION_CX, MEDALLION_CY = 2930, 1506


def place_ornament(canvas: Image.Image, path: Path, x: int, y: int) -> None:
    """Paste an RGBA ornament PNG onto the canvas using its alpha as mask."""
    orn = Image.open(path).convert("RGBA")
    rgb_layer = Image.fromarray(np.array(orn)[:, :, :3])
    canvas.paste(rgb_layer, (x, y), orn.split()[3])
    ow, oh = orn.size
    print(f"  {path.name:30s} {ow:4d}x{oh:<4d} at ({x},{y})")


def load_size(path: Path) -> tuple[int, int]:
    """Return (width, height) of an image without fully loading it."""
    with Image.open(path) as img:
        return img.size


def main() -> None:
    print("=" * 60)
    print("Alexandria Cover Template Builder")
    print("=" * 60)

    # 1. Create navy canvas
    print(f"\n[1/4] Creating {W}x{H} navy canvas...")
    template = Image.new("RGB", (W, H), NAVY)

    # 2. Place corner ornaments
    print("\n[2/4] Placing ornaments...")

    # Corner positions — finalized via visual editor
    place_ornament(template, ORNAMENTS_DIR / "corner_back_tl.png", 0, 0)
    place_ornament(template, ORNAMENTS_DIR / "corner_back_tr.png", 1362, 0)
    place_ornament(template, ORNAMENTS_DIR / "corner_back_bl.png", 0, 2237)
    place_ornament(template, ORNAMENTS_DIR / "corner_back_br.png", 1362, 2237)

    place_ornament(template, ORNAMENTS_DIR / "corner_front_tl.png", 1977, 0)
    place_ornament(template, ORNAMENTS_DIR / "corner_front_tr.png", 3344, 0)
    place_ornament(template, ORNAMENTS_DIR / "corner_front_bl.png", 1977, 2237)
    place_ornament(template, ORNAMENTS_DIR / "corner_front_br.png", 3344, 2237)

    # publisher_logo removed — not needed for biblical covers

    # Front cover edge strips removed — not needed for biblical covers

    # Back cover dividers (ornate scrollwork with fleur-de-lis)
    place_ornament(template, ORNAMENTS_DIR / "divider_back_top.png", 314, 380)
    place_ornament(template, ORNAMENTS_DIR / "divider_back_bottom.png", 314, 1900)

    # Spine decorations (placed LAST — clear spine area first to remove
    # bleed-through from corners/strips, then draw spine ornaments on clean navy)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(template)

    # Clear spine ornament areas — ornaments are wider than the spine column,
    # so clear each ornament's full bounding box (with margin) to remove bleed
    ow_t, oh_t = load_size(ORNAMENTS_DIR / "spine_top.png")
    ow_b, oh_b = load_size(ORNAMENTS_DIR / "spine_bottom.png")
    max_ow = max(ow_t, ow_b)
    clear_x0 = SPINE_CENTER - max_ow // 2 - 5
    clear_x1 = SPINE_CENTER + max_ow // 2 + 5
    draw.rectangle([(clear_x0, 0), (clear_x1, H)], fill=NAVY)

    place_ornament(template, ORNAMENTS_DIR / "spine_top.png", SPINE_CENTER - ow_t // 2, 50)
    place_ornament(template, ORNAMENTS_DIR / "spine_bottom.png", SPINE_CENTER - ow_b // 2, H - 50 - oh_b)

    # 3. Place medallion frame overlay
    print("\n[3/4] Placing medallion frame...")
    fw, fh = load_size(FRAME_OVERLAY)
    place_ornament(template, FRAME_OVERLAY, MEDALLION_CX - fw // 2, MEDALLION_CY - fh // 2)

    # 4. Save
    print(f"\n[4/4] Saving -> {OUTPUT_PATH}")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    template.save(str(OUTPUT_PATH), quality=95)

    file_size_mb = OUTPUT_PATH.stat().st_size / (1024 ** 2)
    print(f"  Saved. File size: {file_size_mb:.1f} MB")
    print("\nDone.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
