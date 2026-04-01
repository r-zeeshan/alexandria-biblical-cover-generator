"""
biblical_compositor.py — Composites AI art + text onto the biblical cover template.
Simple layer stack: template → art in medallion → frame overlay → text.

Includes adaptive border stripping (ported from cover_compositor.py) to handle
AI-generated art with letterboxing, decorative borders, or edge artifacts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from src.text_renderer import render_text_on_template

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adaptive border stripping (ported from cover_compositor.py)
# ---------------------------------------------------------------------------

def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _trim_uniform_edge_bars(image: Image.Image) -> Image.Image:
    """Trim solid white/black letterboxing bars from AI-generated art."""
    rgb = np.array(image.convert("RGB"), dtype=np.float32)
    if rgb.size == 0:
        return image
    h, w = rgb.shape[:2]
    if h < 64 or w < 64:
        return image

    gray = rgb.mean(axis=2)
    cy0, cy1 = int(h * 0.25), int(h * 0.75)
    cx0, cx1 = int(w * 0.25), int(w * 0.75)
    center_mean = float(gray[cy0:cy1, cx0:cx1].mean()) if gray[cy0:cy1, cx0:cx1].size else float(gray.mean())

    row_std = gray.std(axis=1)
    row_mean = gray.mean(axis=1)
    row_edge = np.abs(np.diff(gray, axis=1)).mean(axis=1)

    col_std = gray.std(axis=0)
    col_mean = gray.mean(axis=0)
    col_edge = np.abs(np.diff(gray, axis=0)).mean(axis=0)

    row_bar = (
        (row_std < 10.0) & (row_edge < 8.0)
        & ((row_mean > 230.0) | (row_mean < 25.0))
        & (np.abs(row_mean - center_mean) >= 24.0)
    )
    col_bar = (
        (col_std < 10.0) & (col_edge < 8.0)
        & ((col_mean > 230.0) | (col_mean < 25.0))
        & (np.abs(col_mean - center_mean) >= 24.0)
    )

    def _run_len(mask: np.ndarray, forward: bool) -> int:
        max_len = int(mask.size * 0.24)
        run = 0
        seq = mask if forward else mask[::-1]
        for flag in seq[:max_len]:
            if not bool(flag):
                break
            run += 1
        return run

    min_row = max(6, int(round(h * 0.03)))
    min_col = max(6, int(round(w * 0.03)))

    top = _run_len(row_bar, True)
    bottom = _run_len(row_bar, False)
    left = _run_len(col_bar, True)
    right = _run_len(col_bar, False)

    top = top if top >= min_row else 0
    bottom = bottom if bottom >= min_row else 0
    left = left if left >= min_col else 0
    right = right if right >= min_col else 0

    if top == 0 and bottom == 0 and left == 0 and right == 0:
        return image

    new_left = int(np.clip(left, 0, max(0, w - 2)))
    new_top = int(np.clip(top, 0, max(0, h - 2)))
    new_right = int(np.clip(w - right, new_left + 1, w))
    new_bottom = int(np.clip(h - bottom, new_top + 1, h))
    if (new_right - new_left) < 64 or (new_bottom - new_top) < 64:
        return image

    log.debug("Trimmed letterbox bars: top=%d bot=%d left=%d right=%d", top, bottom, left, right)
    return image.crop((new_left, new_top, new_right, new_bottom))


def _adaptive_border_strip_percent(image: Image.Image) -> float:
    """Score how much extra border to strip based on edge artifact density."""
    rgb = np.array(image.convert("RGB"), dtype=np.float32)
    if rgb.size == 0:
        return 0.0
    gray = rgb.mean(axis=2)
    h, w = gray.shape[:2]
    if h < 24 or w < 24:
        return 0.0

    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    edge_map = np.pad(dx, ((0, 0), (0, 1)), mode="constant") + np.pad(dy, ((0, 1), (0, 0)), mode="constant")
    if float(edge_map.max()) < 2.0:
        return 0.0

    margin = max(6, int(min(h, w) * 0.14))
    yy, xx = np.ogrid[:h, :w]
    outer_mask = (xx < margin) | (xx >= w - margin) | (yy < margin) | (yy >= h - margin)
    center_mask = (xx >= int(w * 0.30)) & (xx <= int(w * 0.70)) & (yy >= int(h * 0.30)) & (yy <= int(h * 0.70))

    outer_vals = edge_map[outer_mask]
    center_vals = edge_map[center_mask]
    if outer_vals.size == 0 or center_vals.size == 0:
        return 0.0

    outer_strength = float(np.percentile(outer_vals, 90))
    center_strength = float(np.percentile(center_vals, 90))
    strength_ratio = outer_strength / max(1e-6, center_strength)

    threshold = float(np.percentile(edge_map, 97))
    strong = edge_map >= threshold
    outer_density = float(strong[outer_mask].mean())
    center_density = float(strong[center_mask].mean())
    density_ratio = outer_density / max(1e-6, center_density + 1e-6)

    row_fill = strong.mean(axis=1)
    col_fill = strong.mean(axis=0)
    top_peak = float(row_fill[:max(2, int(h * 0.20))].max(initial=0.0))
    bottom_peak = float(row_fill[min(h - 1, int(h * 0.80)):].max(initial=0.0))
    left_peak = float(col_fill[:max(2, int(w * 0.20))].max(initial=0.0))
    right_peak = float(col_fill[min(w - 1, int(w * 0.80)):].max(initial=0.0))
    boundary_peak = (top_peak + bottom_peak + left_peak + right_peak) / 4.0

    artifact_score = (
        0.55 * _clip((strength_ratio - 1.25) / 1.55)
        + 0.25 * _clip((density_ratio - 1.45) / 2.30)
        + 0.20 * _clip((boundary_peak - 0.17) / 0.32)
    )
    return 0.10 * _clip(artifact_score)


def _strip_border(image: Image.Image, border_percent: float = 0.05) -> Image.Image:
    """Smart border strip: removes letterboxing + adaptive extra for AI artifacts."""
    image = _trim_uniform_edge_bars(image)
    base_percent = max(0.0, min(0.20, float(border_percent or 0.0)))
    adaptive_extra = _adaptive_border_strip_percent(image)
    percent = max(0.0, min(0.12, base_percent + adaptive_extra))
    if percent <= 0:
        return image
    w, h = image.size
    crop_x = int(w * percent)
    crop_y = int(h * percent)
    if crop_x <= 0 and crop_y <= 0:
        return image
    left = max(0, crop_x)
    top = max(0, crop_y)
    right = min(w, w - crop_x)
    bottom = min(h, h - crop_y)
    if right <= left or bottom <= top:
        return image
    return image.crop((left, top, right, bottom))


def _smart_square_crop(img: Image.Image) -> Image.Image:
    """Center-crop to square."""
    w, h = img.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    return img.crop((left, top, left + s, top + s))


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CompositeValidation:
    """Lightweight post-composite sanity check results."""
    output_path: str
    valid: bool
    issues: list[str] = field(default_factory=list)
    dimensions_ok: bool = True
    dpi_ok: bool = True
    file_size_ok: bool = True

    def to_dict(self) -> dict:
        return {
            "output_path": self.output_path,
            "valid": self.valid,
            "issues": list(self.issues),
            "dimensions_ok": self.dimensions_ok,
            "dpi_ok": self.dpi_ok,
            "file_size_ok": self.file_size_ok,
        }


def _validate_output(output_path: Path, expected_size: tuple[int, int]) -> CompositeValidation:
    """Check that a composited output is sane: dimensions, DPI, file size."""
    issues: list[str] = []

    # File size: 60KB–30MB
    file_size_kb = float(output_path.stat().st_size) / 1024.0 if output_path.exists() else 0.0
    file_size_ok = 60.0 <= file_size_kb <= 30_000.0
    if not file_size_ok:
        issues.append(f"file_size_out_of_bounds ({file_size_kb:.0f}KB)")

    # Dimensions match template
    dimensions_ok = True
    dpi_ok = True
    try:
        with Image.open(output_path) as out_img:
            if out_img.size != expected_size:
                dimensions_ok = False
                issues.append(f"dimension_mismatch (got {out_img.size}, expected {expected_size})")
            dpi = out_img.info.get("dpi", (0, 0))
            dpi_x = float(dpi[0]) if len(dpi) > 0 else 0.0
            dpi_y = float(dpi[1]) if len(dpi) > 1 else 0.0
            if dpi_x < 295.0 or dpi_y < 295.0:
                dpi_ok = False
                issues.append(f"dpi_low ({dpi_x:.0f}x{dpi_y:.0f})")
    except Exception as e:
        dimensions_ok = False
        dpi_ok = False
        issues.append(f"read_failed ({e})")

    return CompositeValidation(
        output_path=str(output_path),
        valid=len(issues) == 0,
        issues=issues,
        dimensions_ok=dimensions_ok,
        dpi_ok=dpi_ok,
        file_size_ok=file_size_ok,
    )


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

    expected_size = template.size
    results = []
    for idx, img_path in enumerate(variant_images):
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
            try:
                rel = img_path.relative_to(generated_dir / str(book_number))
                out_path = output_dir / str(book_number) / rel.parent / (rel.stem + ".jpg")
            except ValueError:
                out_path = output_dir / str(book_number) / (img_path.stem + ".jpg")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cover.save(str(out_path), "JPEG", quality=95, dpi=(300, 300))

            # Validate output
            validation = _validate_output(out_path, expected_size)
            if not validation.valid:
                log.warning("Validation issues for book #%d variant %d: %s",
                            book_number, idx + 1, ", ".join(validation.issues))

            results.append(out_path)
            log.info("Composited book #%d: %s", book_number, out_path.relative_to(output_dir))
        except Exception as e:
            log.error("Failed to composite variant %d for book #%d: %s", idx + 1, book_number, e)

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
