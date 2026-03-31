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
from src.cover_compositor import (
    _strip_border,
    _smart_square_crop,
    _color_match_illustration,
    Region,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed layout constants (from template editor)
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TEMPLATE_PATH = CONFIG_DIR / "cover_template_full.png"
FRAME_OVERLAY_PATH = CONFIG_DIR / "frame_overlay_template.png"

# Medallion geometry — same approach as Tim's classics compositor:
# Art is placed at ART_CLIP_RADIUS (larger), frame covers the overlap at FRAME_HOLE_RADIUS (smaller).
# The frame ring hides the art edge, creating a clean transition.
MEDALLION_CX = 2930
MEDALLION_CY = 1506
ART_CLIP_RADIUS = 600    # Art extends to this radius (same as classics)
FRAME_HOLE_RADIUS = 540  # Frame opening radius (same as classics)
INNER_FEATHER_PX = 8     # Feather on art clip edge
NAVY_FILL_RGB = (21, 32, 76)


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
    # Try SVG-based compositor first (produces identical output to Tim's classics)
    try:
        from src.svg_compositor import compose_cover_svg
        result = compose_cover_svg(ai_art, title, subtitle, author, back_description)
        if result is not None:
            return result
    except Exception as e:
        log.debug("SVG compositor unavailable, using PIL fallback: %s", e)

    # PIL fallback
    if template is None:
        template = Image.open(TEMPLATE_PATH).convert("RGB")
    img = template.copy()

    # Preprocess art (same pipeline as classics)
    ai_art = _strip_border(ai_art, border_percent=0.05)
    ai_art = _smart_square_crop(ai_art)
    region = Region(
        center_x=MEDALLION_CX,
        center_y=MEDALLION_CY,
        radius=ART_CLIP_RADIUS,
        frame_bbox=(MEDALLION_CX - ART_CLIP_RADIUS, MEDALLION_CY - ART_CLIP_RADIUS,
                    MEDALLION_CX + ART_CLIP_RADIUS, MEDALLION_CY + ART_CLIP_RADIUS),
        region_type="circle",
    )
    ai_art = _color_match_illustration(img, ai_art, region)

    # === LAYERING (same as classics compositor) ===
    cover_w, cover_h = img.size

    # Layer 1: Art placed at ART_CLIP_RADIUS (600px)
    art_diameter = ART_CLIP_RADIUS * 2
    art_resized = ai_art.convert("RGBA").resize((art_diameter, art_diameter), Image.LANCZOS)

    # Fill art background with navy (prevents transparency gaps)
    art_bg = Image.new("RGBA", (art_diameter, art_diameter), (*NAVY_FILL_RGB, 255))
    art_bg.alpha_composite(art_resized)

    # Place art on full canvas with circular clip mask
    art_layer = Image.new("RGBA", (cover_w, cover_h), (0, 0, 0, 0))
    art_layer.paste(art_bg, (MEDALLION_CX - ART_CLIP_RADIUS, MEDALLION_CY - ART_CLIP_RADIUS))

    clip_mask = _build_circle_feather_mask(
        cover_w, cover_h, MEDALLION_CX, MEDALLION_CY, ART_CLIP_RADIUS, INNER_FEATHER_PX
    )
    art_layer.putalpha(clip_mask)

    # Layer 2: Composite art onto template
    canvas = img.convert("RGBA")
    result = Image.alpha_composite(canvas, art_layer)

    # Layer 3: Frame overlay on top (covers art edge)
    result = _apply_frame_overlay_rgba(result)

    # Convert back to RGB and render text
    img = result.convert("RGB")
    img = render_text_on_template(img, title, subtitle, author, back_description)

    return img


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
