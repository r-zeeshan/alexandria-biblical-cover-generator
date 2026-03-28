"""
biblical_compositor.py — Composites AI art + text onto the biblical cover template.
Simple layer stack: template → art in medallion → frame overlay → text.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image, ImageDraw

from src.text_renderer import render_text_on_template

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed layout constants (from template editor)
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TEMPLATE_PATH = CONFIG_DIR / "cover_template_full.png"
FRAME_OVERLAY_PATH = CONFIG_DIR / "frame_overlay_template.png"

# Medallion center and radius (front cover)
MEDALLION_CX = 2930
MEDALLION_CY = 1506
ART_RADIUS = 540  # Radius of the circular opening for art

# Frame overlay position (centered on medallion)
# Frame overlay is 1360x1353


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

    Args:
        ai_art: Square AI-generated illustration (any size, will be resized).
        title: Book title.
        subtitle: Book subtitle.
        author: Book author.
        back_description: Back cover description text.
        template: Optional pre-loaded template image. Loads from disk if None.

    Returns:
        Complete cover as PIL Image (3884x2777 RGB).
    """
    # 1. Load template
    if template is None:
        template = Image.open(TEMPLATE_PATH).convert("RGB")
    img = template.copy()

    # 2. Place AI art inside medallion circle
    img = _place_art_in_medallion(img, ai_art)

    # 3. Overlay frame on top (preserves ornate gold ring)
    img = _apply_frame_overlay(img)

    # 4. Render text on top of everything
    img = render_text_on_template(img, title, subtitle, author, back_description)

    return img


def _strip_dark_borders(img: Image.Image, threshold: int = 30) -> Image.Image:
    """Crop away dark borders so the art fills the medallion."""
    import numpy as np
    arr = np.array(img.convert("RGB"))
    brightness = arr.mean(axis=2)
    # Find rows/cols where average brightness exceeds threshold
    row_mask = brightness.mean(axis=1) > threshold
    col_mask = brightness.mean(axis=0) > threshold
    if not row_mask.any() or not col_mask.any():
        return img
    rows = np.where(row_mask)[0]
    cols = np.where(col_mask)[0]
    cropped = img.crop((int(cols[0]), int(rows[0]), int(cols[-1] + 1), int(rows[-1] + 1)))
    # Make square (center crop the longer dimension)
    w, h = cropped.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        cropped = cropped.crop((left, top, left + side, top + side))
    return cropped


def _place_art_in_medallion(cover: Image.Image, art: Image.Image) -> Image.Image:
    """Place circular-cropped art into the medallion opening."""
    # Strip dark borders so art fills the circle
    art = _strip_dark_borders(art)
    # Resize art to fit the medallion diameter
    diameter = ART_RADIUS * 2
    art_resized = art.convert("RGBA").resize((diameter, diameter), Image.LANCZOS)

    # Create circular mask
    mask = Image.new("L", (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill=255)

    # Apply feathered edge (soften the last 8 pixels)
    from PIL import ImageFilter
    mask = mask.filter(ImageFilter.GaussianBlur(radius=4))

    # Paste art at medallion position
    x = MEDALLION_CX - ART_RADIUS
    y = MEDALLION_CY - ART_RADIUS
    cover.paste(art_resized, (x, y), mask)

    return cover


def _apply_frame_overlay(cover: Image.Image) -> Image.Image:
    """Composite the gold frame overlay on top of the art."""
    if not FRAME_OVERLAY_PATH.exists():
        return cover

    frame = Image.open(FRAME_OVERLAY_PATH).convert("RGBA")
    fw, fh = frame.size

    # Center frame on medallion
    x = MEDALLION_CX - fw // 2
    y = MEDALLION_CY - fh // 2

    # Paste using alpha channel
    cover.paste(frame, (x, y), frame.split()[3])

    return cover


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
