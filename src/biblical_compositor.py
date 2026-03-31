"""
biblical_compositor.py — Composites AI art + text onto the biblical cover template.
Simple layer stack: template → art in medallion → frame overlay → text.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from src.text_renderer import render_text_on_template

try:
    from src.cover_compositor import (
        _strip_border,
        _smart_square_crop,
        _color_match_illustration,
        Region,
    )
except (ImportError, ModuleNotFoundError):
    # Lightweight fallbacks for local dev without full dependency chain
    Region = None
    _color_match_illustration = None

    def _strip_border(img, border_percent=0.05):
        w, h = img.size
        b = int(min(w, h) * border_percent)
        return img.crop((b, b, w - b, h - b))

    def _smart_square_crop(img):
        w, h = img.size
        s = min(w, h)
        left = (w - s) // 2
        top = (h - s) // 2
        return img.crop((left, top, left + s, top + s))

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed layout constants (from template editor)
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TEMPLATE_PATH = CONFIG_DIR / "template-latest.png"
FRAME_OVERLAY_PATH = CONFIG_DIR / "frame_overlay_template.png"

# Medallion geometry — from green mask in template-latest.png
# Green mask: center=(2185,1243), radius=373
MEDALLION_CX = 2185
MEDALLION_CY = 1243
ART_CLIP_RADIUS = 373    # Exact green mask radius
FRAME_HOLE_RADIUS = 373  # Same — frame is already in template
INNER_FEATHER_PX = 6
NAVY_FILL_RGB = (0, 27, 80)  # #001b50 from SVG


def compose_biblical_cover(
    ai_art: Image.Image,
    title: str,
    subtitle: str = "",
    author: str = "",
    back_description: str = "",
    template: Image.Image | None = None,
) -> Image.Image:
    """
    Compose a complete biblical cover from AI art and book metadata.

    Tries SVG compositor first (identical to Tim's originals with gradient ornaments).
    Falls back to PIL compositor if cairosvg not available (Windows dev).
    """
    # Uses green mask in template for exact art placement
    if template is None:
        template = Image.open(TEMPLATE_PATH).convert("RGB")
    img = template.copy()

    # Preprocess art (same pipeline as classics)
    ai_art = _strip_border(ai_art, border_percent=0.05)
    ai_art = _smart_square_crop(ai_art)

    # Place art by replacing green mask pixels
    img = _replace_green_mask_with_art(img, ai_art)

    # Render text on top
    img = render_text_on_template(img, title, subtitle, author, back_description)

    return img


def _replace_green_mask_with_art(cover: Image.Image, art: Image.Image) -> Image.Image:
    """Replace green mask pixels in template with AI art, preserving the gold frame on top."""
    import numpy as np

    arr = np.array(cover)
    # Detect green pixels: G channel high, R and B low
    g = arr[:, :, 1].astype(int)
    r = arr[:, :, 0].astype(int)
    b_ch = arr[:, :, 2].astype(int)
    green_mask = (g - r > 80) & (g > 100) & (g - b_ch > 80)

    if not green_mask.any():
        log.warning("No green mask found in template, falling back to circle placement")
        # Fallback: circular paste at medallion position
        diameter = ART_CLIP_RADIUS * 2
        art_resized = art.convert("RGB").resize((diameter, diameter), Image.LANCZOS)
        cover.paste(art_resized, (MEDALLION_CX - ART_CLIP_RADIUS, MEDALLION_CY - ART_CLIP_RADIUS))
        return cover

    # Get bounding box of green area
    rows = np.where(green_mask.any(axis=1))[0]
    cols = np.where(green_mask.any(axis=0))[0]
    top, bot = int(rows[0]), int(rows[-1])
    left, right = int(cols[0]), int(cols[-1])
    mask_w = right - left + 1
    mask_h = bot - top + 1

    # Resize art to fill the green area
    art_resized = art.convert("RGB").resize((mask_w, mask_h), Image.LANCZOS)
    art_arr = np.array(art_resized)

    # Replace only green pixels with art pixels
    green_region = green_mask[top:bot+1, left:right+1]
    arr[top:bot+1, left:right+1][green_region] = art_arr[green_region]

    return Image.fromarray(arr)


def _build_circle_feather_mask(w, h, cx, cy, radius, feather_px):
    """Build a circular alpha mask with feathered edge — same as classics."""
    import numpy as np
    yy, xx = np.ogrid[:h, :w]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(np.float32)
    mask = np.clip((radius - dist) / max(feather_px, 1), 0.0, 1.0)
    return Image.fromarray((mask * 255).astype(np.uint8), mode="L")


def _apply_frame_overlay_rgba(cover: Image.Image) -> Image.Image:
    """Composite the gold frame overlay on top of the art (RGBA input)."""
    if not FRAME_OVERLAY_PATH.exists():
        return cover

    frame = Image.open(FRAME_OVERLAY_PATH).convert("RGBA")
    fw, fh = frame.size

    # Place frame centered on medallion
    frame_layer = Image.new("RGBA", cover.size, (0, 0, 0, 0))
    x = MEDALLION_CX - fw // 2
    y = MEDALLION_CY - fh // 2
    frame_layer.paste(frame, (x, y))

    return Image.alpha_composite(cover, frame_layer)


# ---------------------------------------------------------------------------
# Pipeline integration — matches existing compositor interface
# ---------------------------------------------------------------------------

def composite_all_variants(
    book_number: int,
    generated_dir: Path,
    output_dir: Path,
    *,
    catalog_path: Path | None = None,
    **kwargs,
) -> list[Path]:
    """
    Composite all generated variants for a biblical book.

    Matches the interface of cover_compositor.composite_all_variants()
    so it can be used as a drop-in replacement in the pipeline.
    """
    # Load book metadata
    cat_path = catalog_path or (CONFIG_DIR / "book_catalog.json")
    book_meta = _load_book_meta(cat_path, book_number)
    if not book_meta:
        log.warning("Book #%d not found in catalog", book_number)
        return []

    # Pre-load template once for all variants
    template = Image.open(TEMPLATE_PATH).convert("RGB")

    # Find all generated variant images (may be nested: book_num/model_name/variant_N.png)
    gen_book_dir = generated_dir / str(book_number)
    if not gen_book_dir.exists():
        gen_book_dir = generated_dir

    variant_images = sorted(
        p for p in gen_book_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    )

    if not variant_images:
        log.warning("No generated images found for book #%d in %s", book_number, gen_book_dir)
        return []

    results = []
    for img_path in variant_images:
        try:
            ai_art = Image.open(img_path)
            cover = compose_biblical_cover(
                ai_art=ai_art,
                title=book_meta.get("title", ""),
                subtitle=book_meta.get("subtitle", ""),
                author=book_meta.get("author", ""),
                back_description=book_meta.get("back_cover_description", ""),
                template=template,
            )

            # Mirror the generated file's relative path into composited output
            # e.g. generated/{job}/{book}/{model}/variant_1.png → composited/{job}/{book}/{model}/variant_1.jpg
            try:
                rel = img_path.relative_to(generated_dir / str(book_number))
                out_path = output_dir / str(book_number) / rel.parent / (rel.stem + ".jpg")
            except ValueError:
                out_path = output_dir / str(book_number) / (img_path.stem + ".jpg")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cover.save(str(out_path), "JPEG", quality=95, dpi=(300, 300))
            results.append(out_path)
            log.info("Composited book #%d: %s", book_number, out_path.relative_to(output_dir))
        except Exception as e:
            log.error("Failed to composite variant %d for book #%d: %s", i + 1, book_number, e)

    return results


def _load_book_meta(catalog_path: Path, book_number: int) -> dict | None:
    """Load metadata for a single book from the catalog."""
    try:
        with open(catalog_path, encoding="utf-8") as f:
            books = json.load(f)
        return next((b for b in books if b.get("number") == book_number), None)
    except (OSError, json.JSONDecodeError) as e:
        log.error("Failed to load catalog %s: %s", catalog_path, e)
        return None
