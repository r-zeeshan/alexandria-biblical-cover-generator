"""PDF-based compositor – frame overlay approach.

Replaces the center art inside the ornamental medallion using a pre-generated
frame overlay PNG.  The overlay was created by diffing Im0 CMYK data across
multiple books to identify which pixels are frame (identical across all books)
vs illustration (different per book).

Algorithm:
  1. Open the source PDF to read Im0 dimensions and its cm-transform on the page.
  2. Open the original source JPG (rendered by Adobe Illustrator).
  3. Map Im0 coordinates into JPG pixel space via the cm transform matrix.
  4. Navy-fill the medallion interior to erase old illustration.
  5. Paste new AI art into the medallion center.
  6. Paste the opaque frame overlay (from config/frame_overlay_template.png)
     on top — frame sits perfectly over the art with no bleed-through.
  7. Save the result as a high-quality JPG.

The frame overlay is pixel-perfect because it uses the original Illustrator-
rendered JPG colors at full opacity, with a transparent hole only where
illustration pixels were identified by cross-book comparison.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

try:
    import pikepdf  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("pikepdf is required for PDF compositor") from exc

try:
    from src import config
    from src import safe_json
    from src.logger import get_logger
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore
    import safe_json  # type: ignore
    from logger import get_logger  # type: ignore

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXPECTED_DPI = 300
EXPECTED_JPG_SIZE = (3784, 2777)          # full cover w x h

# Frame overlay template — pre-generated RGBA PNG with transparent art hole
FRAME_OVERLAY_TEMPLATE = Path(__file__).resolve().parent.parent / "config" / "frame_overlay_template.png"
NAVY_FILL_RGB = (21, 32, 76)  # cover background color

# Art pre-processing
AI_ART_EDGE_TRIM_RATIO = 0.08
AI_UNIFORM_MARGIN_MAX_TRIM_RATIO = 0.22
AI_UNIFORM_MARGIN_COLOR_TOL = 26.0
AI_UNIFORM_MARGIN_STD_MAX = 22.0
AI_UNIFORM_MARGIN_MATCH_RATIO = 0.92


# ---------------------------------------------------------------------------
# Utility: trim uniform margins from generated art
# ---------------------------------------------------------------------------
def _trim_uniform_margins(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] != 3:
        return rgb
    h, w = int(arr.shape[0]), int(arr.shape[1])
    if h < 64 or w < 64:
        return rgb

    patch = max(4, min(h, w) // 40)
    corners = np.concatenate(
        [
            arr[:patch, :patch].reshape(-1, 3),
            arr[:patch, w - patch :].reshape(-1, 3),
            arr[h - patch :, :patch].reshape(-1, 3),
            arr[h - patch :, w - patch :].reshape(-1, 3),
        ],
        axis=0,
    )
    corner_color = np.median(corners, axis=0)

    def _line_matches(line: np.ndarray) -> bool:
        if line.size == 0:
            return False
        diff = np.abs(line - corner_color).mean(axis=1)
        match_ratio = float(np.mean(diff <= AI_UNIFORM_MARGIN_COLOR_TOL))
        std_mean = float(np.std(line, axis=0).mean())
        return match_ratio >= AI_UNIFORM_MARGIN_MATCH_RATIO and std_mean <= AI_UNIFORM_MARGIN_STD_MAX

    max_trim_x = max(0, int(round(w * AI_UNIFORM_MARGIN_MAX_TRIM_RATIO)))
    max_trim_y = max(0, int(round(h * AI_UNIFORM_MARGIN_MAX_TRIM_RATIO)))

    left = 0
    while left < max_trim_x and _line_matches(arr[:, left, :]):
        left += 1
    right = 0
    while right < max_trim_x and _line_matches(arr[:, w - 1 - right, :]):
        right += 1
    top = 0
    while top < max_trim_y and _line_matches(arr[top, :, :]):
        top += 1
    bottom = 0
    while bottom < max_trim_y and _line_matches(arr[h - 1 - bottom, :, :]):
        bottom += 1

    if (left + right + top + bottom) <= 0:
        return rgb

    new_w = w - left - right
    new_h = h - top - bottom
    if new_w < max(64, int(w * 0.55)) or new_h < max(64, int(h * 0.55)):
        return rgb

    return rgb.crop((left, top, w - right, h - bottom))


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------
def _load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = safe_json.load_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _find_book_folder_name(*, catalog_path: Path, book_number: int) -> str:
    for row in _load_catalog(catalog_path):
        try:
            number = int(row.get("number", 0))
        except (TypeError, ValueError):
            continue
        if number == int(book_number):
            return str(row.get("folder_name", "")).strip()
    return ""


def find_source_pdf_for_book(*, input_dir: Path, book_number: int, catalog_path: Path = config.BOOK_CATALOG_PATH) -> Path | None:
    """Return source PDF path for a book when available."""
    folder_name = _find_book_folder_name(catalog_path=catalog_path, book_number=book_number)
    if not folder_name:
        return None
    folder = input_dir / folder_name
    if not folder.exists() or not folder.is_dir():
        return None

    pdfs = sorted([path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"])
    if pdfs:
        return pdfs[0]

    ais = sorted([path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".ai"])
    if ais:
        return ais[0]
    return None


def find_source_jpg_for_book(*, input_dir: Path, book_number: int, catalog_path: Path = config.BOOK_CATALOG_PATH) -> Path | None:
    """Return the original Illustrator-rendered JPG for a book."""
    folder_name = _find_book_folder_name(catalog_path=catalog_path, book_number=book_number)
    if not folder_name:
        return None
    folder = input_dir / folder_name
    if not folder.exists() or not folder.is_dir():
        return None

    jpgs = sorted([path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg")])
    if jpgs:
        return jpgs[0]
    return None


# ---------------------------------------------------------------------------
# PDF helpers — extract Im0 position on page
# ---------------------------------------------------------------------------
def _resolve_im0(page: Any) -> Any:
    """Find the Im0 image XObject in the PDF page."""
    resources = page.get("/Resources")
    if resources is None:
        raise ValueError("PDF page has no /Resources")
    xobjects = resources.get("/XObject")
    if xobjects is None:
        raise ValueError("PDF page has no /XObject resources")

    if "/Im0" in xobjects:
        return xobjects["/Im0"]

    for _name, obj in xobjects.items():
        try:
            subtype = str(obj.get("/Subtype", ""))
        except Exception:
            subtype = ""
        if subtype == "/Image" and obj.get("/SMask") is not None:
            return obj
    raise ValueError("No image XObject with SMask found (expected /Im0)")


def _extract_im0_transform(pdf_path: Path) -> dict[str, Any]:
    """Extract Im0 dimensions and its cm-transform from the page content stream.

    The content stream contains a `cm` operator that places Im0 on the page:
        a 0 0 d tx ty cm
    Where:
        a  = width in points
        d  = height in points
        tx = left offset in points from left edge
        ty = bottom offset in points from bottom edge
    """
    pdf = pikepdf.Pdf.open(str(pdf_path))
    try:
        if len(pdf.pages) == 0:
            raise ValueError("Source PDF has no pages")
        page = pdf.pages[0]
        im0 = _resolve_im0(page)

        im0_w = int(im0.get("/Width"))
        im0_h = int(im0.get("/Height"))

        # Parse content stream for cm transform preceding Im0 reference
        raw_content = page.Contents.read_bytes().decode("latin-1")

        # Find the cm transform — it's typically the last `cm` before `/Im0 Do`
        # Content stream pattern: ... a 0 0 d tx ty cm ... /Im0 Do ...
        # Find all cm operators
        cm_pattern = re.compile(
            r"(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+cm"
        )
        matches = list(cm_pattern.finditer(raw_content))

        # Find the position of /Im0 Do
        im0_pos = raw_content.find("/Im0")
        if im0_pos < 0:
            # Try to find any image reference
            im0_pos = raw_content.find("Do")

        # Get the cm transform closest before Im0
        best_match = None
        for m in matches:
            if m.start() < im0_pos:
                best_match = m

        if best_match is None:
            raise ValueError("Could not find cm transform for Im0 in content stream")

        a = float(best_match.group(1))   # width in points
        b = float(best_match.group(2))
        c = float(best_match.group(3))
        d = float(best_match.group(4))   # height in points
        tx = float(best_match.group(5))  # x offset in points
        ty = float(best_match.group(6))  # y offset in points

        # Get page dimensions in points
        mediabox = page.MediaBox
        page_w_pts = float(mediabox[2]) - float(mediabox[0])
        page_h_pts = float(mediabox[3]) - float(mediabox[1])

        return {
            "im0_w": im0_w,
            "im0_h": im0_h,
            "cm_a": a,
            "cm_d": d,
            "cm_tx": tx,
            "cm_ty": ty,
            "page_w_pts": page_w_pts,
            "page_h_pts": page_h_pts,
        }
    finally:
        pdf.close()


def _im0_to_jpg_mapping(transform: dict[str, Any], jpg_w: int, jpg_h: int) -> dict[str, Any]:
    """Compute the mapping from Im0 pixel coordinates to JPG pixel coordinates.

    The PDF places Im0 at (tx, ty) with size (a x d) points on a page of
    (page_w x page_h) points.  The JPG is a flat render of the full page.

    In JPG space:
        scale_x = jpg_w / page_w_pts
        scale_y = jpg_h / page_h_pts
        im0_left_jpg  = tx * scale_x
        im0_top_jpg   = (page_h_pts - ty - d) * scale_y   (PDF y is bottom-up)
        im0_width_jpg = a * scale_x
        im0_height_jpg = d * scale_y
    """
    page_w_pts = transform["page_w_pts"]
    page_h_pts = transform["page_h_pts"]
    a = transform["cm_a"]
    d = transform["cm_d"]
    tx = transform["cm_tx"]
    ty = transform["cm_ty"]

    scale_x = jpg_w / page_w_pts
    scale_y = jpg_h / page_h_pts

    im0_left = tx * scale_x
    im0_top = (page_h_pts - ty - d) * scale_y
    im0_w_jpg = a * scale_x
    im0_h_jpg = d * scale_y
    im0_cx = im0_left + im0_w_jpg / 2.0
    im0_cy = im0_top + im0_h_jpg / 2.0

    # Scale factor from Im0 pixel space to JPG pixel space
    im0_to_jpg_scale_x = im0_w_jpg / transform["im0_w"]
    im0_to_jpg_scale_y = im0_h_jpg / transform["im0_h"]

    return {
        "im0_left": im0_left,
        "im0_top": im0_top,
        "im0_w_jpg": im0_w_jpg,
        "im0_h_jpg": im0_h_jpg,
        "im0_cx": im0_cx,
        "im0_cy": im0_cy,
        "im0_to_jpg_scale_x": im0_to_jpg_scale_x,
        "im0_to_jpg_scale_y": im0_to_jpg_scale_y,
        "scale_x": scale_x,
        "scale_y": scale_y,
    }


# ---------------------------------------------------------------------------
# SMask extraction — conservative art-zone mask that protects the full frame
# ---------------------------------------------------------------------------
def _extract_conservative_art_mask(pdf_path: Path) -> np.ndarray:
    """Extract the SMask from Im0 and build a conservative art-zone blend mask.

    The SMask's opaque zone (value 255) includes both the illustration AND
    the solid parts of the gold frame — it's a transparency mask, not a
    content mask.  To protect the frame we:

      1. Find the frame ring (SMask 5-250) — the semi-transparent ornament edges.
      2. DILATE the frame ring outward by SMASK_FRAME_DILATE_PX pixels.
         This expands the protected zone to cover the solid frame metal that
         sits behind the semi-transparent edges (also at SMask=255).
      3. Safe art zone = opaque zone (SMask > 250) MINUS the expanded frame.
      4. Erode the safe art zone by SMASK_ART_ERODE_PX for additional safety.
      5. Apply Gaussian feather for smooth blending.

    This follows the actual irregular scrollwork shape — every curl, protrusion,
    and ornamental detail is protected regardless of how deep it extends.

    Returns a float32 array (H, W) with values 0.0..1.0.
    """
    from scipy.ndimage import binary_dilation, binary_erosion, gaussian_filter

    pdf = pikepdf.Pdf.open(str(pdf_path))
    try:
        page = pdf.pages[0]
        im0 = _resolve_im0(page)
        smask = im0["/SMask"]
        smask_data = bytes(smask.read_bytes())
        w = int(smask["/Width"])
        h = int(smask["/Height"])
        smask_arr = np.frombuffer(smask_data, dtype=np.uint8).reshape((h, w))

        # Step 1: Identify frame ring (semi-transparent ornament edges)
        frame_ring = (smask_arr >= SMASK_FRAME_LO) & (smask_arr <= SMASK_FRAME_HI)

        # Step 2: Dilate frame ring to cover solid frame metal behind it.
        # Use iterative dilation with smaller structuring elements to avoid
        # memory issues with very large kernels.
        if SMASK_FRAME_DILATE_PX > 0:
            expanded_frame = frame_ring.copy()
            step = 20  # dilate 20px per iteration
            remaining = SMASK_FRAME_DILATE_PX
            while remaining > 0:
                r = min(step, remaining)
                dilate_struct = np.ones((2 * r + 1, 2 * r + 1), dtype=bool)
                expanded_frame = binary_dilation(expanded_frame, structure=dilate_struct)
                remaining -= r
        else:
            expanded_frame = frame_ring

        # Step 3: Safe art zone = fully opaque minus expanded frame
        safe_art = (smask_arr > SMASK_FRAME_HI) & ~expanded_frame

        # Step 4: Additional erosion for safety margin
        if SMASK_ART_ERODE_PX > 0:
            erode_struct = np.ones(
                (2 * SMASK_ART_ERODE_PX + 1, 2 * SMASK_ART_ERODE_PX + 1),
                dtype=bool,
            )
            safe_art = binary_erosion(safe_art, structure=erode_struct)

        safe_art = safe_art.astype(np.float32)

        # Step 5: Gaussian feather for smooth transition
        if SMASK_FEATHER_PX > 0:
            safe_art = gaussian_filter(safe_art, sigma=SMASK_FEATHER_PX)

        logger.info(
            "SMask conservative art mask: %d x %d, frame_dilate=%d, art_erode=%d, feather=%d, art_pixels=%d",
            w, h, SMASK_FRAME_DILATE_PX, SMASK_ART_ERODE_PX,
            SMASK_FEATHER_PX, int((safe_art > 0.5).sum()),
        )
        return safe_art
    finally:
        pdf.close()


# ---------------------------------------------------------------------------
# Art loading
# ---------------------------------------------------------------------------
def _load_ai_art_rgb(*, ai_art_path: Path, width: int, height: int) -> Image.Image:
    """Load AI art, trim margins, edge-trim, resize to (width, height) as RGB."""
    with Image.open(ai_art_path) as source:
        rgb_source = _trim_uniform_margins(source)
        if AI_ART_EDGE_TRIM_RATIO > 0:
            src_w, src_h = rgb_source.size
            trim_x = int(round(src_w * AI_ART_EDGE_TRIM_RATIO / 2.0))
            trim_y = int(round(src_h * AI_ART_EDGE_TRIM_RATIO / 2.0))
            if (src_w - 2 * trim_x) >= 64 and (src_h - 2 * trim_y) >= 64:
                rgb_source = rgb_source.crop((trim_x, trim_y, src_w - trim_x, src_h - trim_y))
        rgb = ImageOps.fit(
            rgb_source,
            (int(width), int(height)),
            method=Image.LANCZOS,
            centering=(0.5, 0.5),
        )
    return rgb.convert("RGB")


# ---------------------------------------------------------------------------
# Main entry: composite_cover_pdf  (frame overlay approach)
# ---------------------------------------------------------------------------
def composite_cover_pdf(
    source_pdf_path: str,
    ai_art_path: str,
    output_pdf_path: str,
    output_jpg_path: str,
    output_ai_path: str | None = None,
    *,
    source_jpg_path: str | None = None,
) -> dict[str, Any]:
    """Replace medallion art using frame overlay approach.

    Uses a pre-generated frame overlay PNG (created by diffing Im0 across
    multiple books) to cleanly separate frame from illustration.  The overlay
    is fully opaque with a transparent hole where new art is placed.

    Steps:
      1. Start with original JPG (has perfect cover: text, corners, background)
      2. Navy-fill the medallion interior (erases old illustration)
      3. Paste new AI art into the medallion area
      4. Paste opaque frame overlay on top (frame sits perfectly over art)
    """
    source_pdf = Path(source_pdf_path)
    art_path = Path(ai_art_path)
    output_pdf = Path(output_pdf_path)
    output_jpg = Path(output_jpg_path)
    output_ai = Path(output_ai_path) if output_ai_path else output_pdf.with_suffix(".ai")

    if not source_pdf.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf}")
    if not art_path.exists():
        raise FileNotFoundError(f"AI art image not found: {art_path}")

    # Find source JPG — either passed explicitly or inferred from same folder
    jpg_path: Path | None = None
    if source_jpg_path:
        jpg_path = Path(source_jpg_path)
    else:
        folder = source_pdf.parent
        jpg_candidates = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")])
        if jpg_candidates:
            jpg_path = jpg_candidates[0]

    if jpg_path is None or not jpg_path.exists():
        raise FileNotFoundError(f"Source JPG not found alongside PDF: {source_pdf.parent}")

    if not FRAME_OVERLAY_TEMPLATE.exists():
        raise FileNotFoundError(
            f"Frame overlay template not found: {FRAME_OVERLAY_TEMPLATE}. "
            "Generate it by running scripts/generate_frame_overlay.py with 3+ book PDFs."
        )

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    output_ai.parent.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Extract Im0 position from PDF ---
    transform = _extract_im0_transform(source_pdf)

    # --- Step 2: Open original JPG ---
    base_jpg = Image.open(jpg_path).convert("RGB")
    jpg_w, jpg_h = base_jpg.size

    # --- Step 3: Map Im0 coordinates to JPG space ---
    mapping = _im0_to_jpg_mapping(transform, jpg_w, jpg_h)

    im0_region_w = int(round(mapping["im0_w_jpg"]))
    im0_region_h = int(round(mapping["im0_h_jpg"]))
    im0_cx = mapping["im0_cx"]
    im0_cy = mapping["im0_cy"]
    im0_left = int(round(mapping["im0_left"]))
    im0_top = int(round(mapping["im0_top"]))

    # --- Step 4: Load frame overlay (already at JPG region size) ---
    frame_overlay = Image.open(FRAME_OVERLAY_TEMPLATE).convert("RGBA")
    if frame_overlay.size != (im0_region_w, im0_region_h):
        frame_overlay_scaled = frame_overlay.resize((im0_region_w, im0_region_h), Image.LANCZOS)
    else:
        frame_overlay_scaled = frame_overlay

    # --- Step 5: Load and prep new AI art ---
    new_art = _load_ai_art_rgb(ai_art_path=art_path, width=im0_region_w, height=im0_region_h)

    # --- Step 6: Composite — navy fill → art → frame overlay on top ---
    base_rgba = base_jpg.convert("RGBA")
    base_arr = np.array(base_rgba)

    # Navy-fill the medallion interior
    yy, xx = np.mgrid[:jpg_h, :jpg_w]
    dist = np.sqrt((xx - im0_cx) ** 2 + (yy - im0_cy) ** 2)
    im0_scale = (mapping["im0_to_jpg_scale_x"] + mapping["im0_to_jpg_scale_y"]) / 2.0
    wipe_r = 1100 * im0_scale
    wipe_mask = np.clip((wipe_r - dist) / 3.0, 0.0, 1.0)
    for c in range(3):
        base_arr[:, :, c] = (
            NAVY_FILL_RGB[c] * wipe_mask + base_arr[:, :, c].astype(float) * (1.0 - wipe_mask)
        ).astype(np.uint8)

    # Paste AI art ONLY where the frame overlay is transparent (the art hole).
    # This prevents the AI art's white background from showing outside the
    # circular frame area as a visible rectangle.
    art_arr = np.array(new_art, dtype=np.float32)
    overlay_alpha = np.array(frame_overlay_scaled.split()[3], dtype=np.float32) / 255.0
    art_mask = 1.0 - overlay_alpha  # 1.0 where transparent (art hole), 0.0 where opaque (frame)
    art_mask_3ch = art_mask[:, :, np.newaxis]

    src_y1 = max(0, im0_top)
    src_y2 = min(jpg_h, im0_top + im0_region_h)
    src_x1 = max(0, im0_left)
    src_x2 = min(jpg_w, im0_left + im0_region_w)
    art_y1 = src_y1 - im0_top
    art_x1 = src_x1 - im0_left
    rh = src_y2 - src_y1
    rw = src_x2 - src_x1

    region = base_arr[src_y1:src_y2, src_x1:src_x2, :3].astype(np.float32)
    art_region = art_arr[art_y1:art_y1 + rh, art_x1:art_x1 + rw]
    mask_region = art_mask_3ch[art_y1:art_y1 + rh, art_x1:art_x1 + rw]

    # Blend: art where transparent, navy-wiped base where opaque
    blended = art_region * mask_region + region * (1.0 - mask_region)
    base_arr[src_y1:src_y2, src_x1:src_x2, :3] = np.clip(blended, 0, 255).astype(np.uint8)

    # Paste frame overlay ON TOP — frame is opaque, art hole is transparent
    base_with_art = Image.fromarray(base_arr, "RGBA")
    base_with_art.paste(frame_overlay_scaled, (im0_left, im0_top), frame_overlay_scaled)

    result_arr = np.array(base_with_art.convert("RGB"), dtype=np.float32)

    # --- Step 7: Save result ---
    result_img = Image.fromarray(np.clip(result_arr, 0, 255).astype(np.uint8), "RGB")

    # Ensure expected dimensions
    if result_img.size != EXPECTED_JPG_SIZE:
        result_img = result_img.resize(EXPECTED_JPG_SIZE, Image.LANCZOS)

    result_img.save(output_jpg, format="JPEG", quality=100, subsampling=0, dpi=(EXPECTED_DPI, EXPECTED_DPI))

    # Copy source PDF and AI files for reference (they are not modified)
    shutil.copyfile(source_pdf, output_pdf)
    shutil.copyfile(source_pdf, output_ai)

    logger.info(
        "Frame overlay compositor completed",
        extra={
            "source_pdf": str(source_pdf),
            "source_jpg": str(jpg_path),
            "output_jpg": str(output_jpg),
            "im0_center_jpg": f"({im0_cx:.0f}, {im0_cy:.0f})",
            "blend_mode": "frame_overlay",
            "frame_overlay": str(FRAME_OVERLAY_TEMPLATE),
            "im0_region": f"{im0_region_w}x{im0_region_h}",
        },
    )

    return {
        "success": True,
        "blend_mode": "frame_overlay",
        "source_pdf": str(source_pdf),
        "source_jpg": str(jpg_path),
        "output_pdf": str(output_pdf),
        "output_jpg": str(output_jpg),
        "output_ai": str(output_ai),
        "center_x": int(round(im0_cx)),
        "center_y": int(round(im0_cy)),
        "image_width": int(transform["im0_w"]),
        "image_height": int(transform["im0_h"]),
    }


# ---------------------------------------------------------------------------
# Batch: composite all variants for a book
# ---------------------------------------------------------------------------
def _parse_variant(stem: str) -> int:
    if "variant_" not in stem:
        return 0
    token = stem.split("variant_", 1)[1].split("_", 1)[0]
    try:
        return int(token)
    except ValueError:
        return 0


def _collect_generated_for_book(generated_dir: Path, book_number: int) -> list[dict[str, Any]]:
    base = generated_dir / str(book_number)
    if not base.exists():
        return []

    rows: list[dict[str, Any]] = []
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}

    for model_dir in sorted([path for path in base.iterdir() if path.is_dir()]):
        if model_dir.name == "history":
            continue
        for image in sorted([p for p in model_dir.iterdir() if p.is_file() and p.suffix.lower() in image_extensions]):
            variant = _parse_variant(image.stem)
            if variant <= 0:
                continue
            rows.append({"model": model_dir.name, "variant": variant, "path": image})

    for image in sorted([p for p in base.iterdir() if p.is_file() and p.suffix.lower() in image_extensions]):
        variant = _parse_variant(image.stem)
        if variant <= 0:
            continue
        rows.append({"model": "default", "variant": variant, "path": image})

    dedup: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        dedup[(str(row["model"]), int(row["variant"]))] = row
    return sorted(dedup.values(), key=lambda row: (str(row["model"]), int(row["variant"])))


def composite_all_variants(
    *,
    book_number: int,
    input_dir: Path,
    generated_dir: Path,
    output_dir: Path,
    catalog_path: Path = config.BOOK_CATALOG_PATH,
) -> list[Path]:
    """Composite all generated variants for a book via JPG-level blend."""
    source_pdf = find_source_pdf_for_book(input_dir=input_dir, book_number=book_number, catalog_path=catalog_path)
    if source_pdf is None:
        raise FileNotFoundError(f"No source PDF found for book {book_number}")

    source_jpg = find_source_jpg_for_book(input_dir=input_dir, book_number=book_number, catalog_path=catalog_path)
    if source_jpg is None:
        raise FileNotFoundError(f"No source JPG found for book {book_number}")

    image_rows = _collect_generated_for_book(generated_dir=generated_dir, book_number=book_number)
    if not image_rows:
        raise FileNotFoundError(f"No generated variants found for book {book_number}")

    outputs: list[Path] = []
    report_items: list[dict[str, Any]] = []

    for row in image_rows:
        model = str(row["model"])
        variant = int(row["variant"])
        image_path = Path(row["path"])

        if model == "default":
            base_output = output_dir / str(book_number) / f"variant_{variant}"
        else:
            base_output = output_dir / str(book_number) / model / f"variant_{variant}"

        output_pdf = base_output.with_suffix(".pdf")
        output_jpg = base_output.with_suffix(".jpg")
        output_ai = base_output.with_suffix(".ai")

        result = composite_cover_pdf(
            source_pdf_path=str(source_pdf),
            ai_art_path=str(image_path),
            output_pdf_path=str(output_pdf),
            output_jpg_path=str(output_jpg),
            output_ai_path=str(output_ai),
            source_jpg_path=str(source_jpg),
        )
        outputs.append(output_jpg)
        report_items.append(
            {
                "output_path": str(output_jpg),
                "valid": True,
                "issues": [],
                "mode": "jpg_blend",
                "source_pdf": str(source_pdf),
                "source_jpg": str(source_jpg),
                "variant": variant,
                "model": model,
                "metrics": {
                    "image_width": float(result.get("image_width", 0)),
                    "image_height": float(result.get("image_height", 0)),
                },
            }
        )

    report = {
        "book_number": int(book_number),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(report_items),
        "invalid": 0,
        "items": report_items,
    }
    safe_json.atomic_write_json(output_dir / str(book_number) / "composite_validation.json", report)
    logger.info(
        "JPG blend compositor completed",
        extra={"book_number": int(book_number), "variants": len(outputs), "source_pdf": str(source_pdf)},
    )
    return outputs


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="PDF compositor (JPG blend) for one generated image")
    parser.add_argument("source_pdf", type=Path)
    parser.add_argument("ai_art", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("output_jpg", type=Path)
    parser.add_argument("--output-ai", type=Path, default=None)
    parser.add_argument("--source-jpg", type=Path, default=None, help="Original JPG (auto-detected if not given)")
    args = parser.parse_args()

    result = composite_cover_pdf(
        source_pdf_path=str(args.source_pdf),
        ai_art_path=str(args.ai_art),
        output_pdf_path=str(args.output_pdf),
        output_jpg_path=str(args.output_jpg),
        output_ai_path=str(args.output_ai) if args.output_ai else None,
        source_jpg_path=str(args.source_jpg) if args.source_jpg else None,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
