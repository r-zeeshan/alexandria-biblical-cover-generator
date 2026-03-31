"""
svg_compositor.py — SVG-based cover compositor using Tim's original Illustrator template.

Injects text + AI art into the SVG template, then renders to high-res PNG.
Produces covers with identical ornament gradients and styling to Tim's classics.

Requires: cairosvg (available on Linux/Docker, optional on Windows).
Falls back to biblical_compositor.py (PIL-based) if cairosvg unavailable.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SVG_TEMPLATE_PATH = CONFIG_DIR / "cover_template.svg"
FONTS_DIR = CONFIG_DIR / "fonts"

# SVG coordinate system (from viewBox)
SVG_W = 890.08
SVG_H = 649.13

# Scale factor: SVG coords → our 3884x2777 pixel space
SCALE_X = 3884 / SVG_W  # ~4.36
SCALE_Y = 2777 / SVG_H  # ~4.28

# Text positions in SVG coordinates (derived from Tim's original)
# Title: ~15% down, centered on right half
TITLE_X = 667    # center of front cover in SVG coords
TITLE_Y = 96     # ~15% down
AUTHOR_X = 667
AUTHOR_Y = 580   # ~89% down
SUBTITLE_X = 667
SUBTITLE_Y = 155

# Spine
SPINE_X = 445    # center of spine
SPINE_Y = 325    # center vertically

# Back cover
BACK_CX = 216    # center of back cover
QUOTE_Y = 160
BODY_Y = 310
BODY_X_LEFT = 43
BODY_X_RIGHT = 390

# Medallion center in SVG coords
MEDALLION_CX = 667
MEDALLION_CY = 330
MEDALLION_R = 137   # approximate radius in SVG coords

# Colors from Tim's SVG
GOLD_HEX = "#f0ce46"
WHITE_HEX = "#ffffff"
NAVY_HEX = "#001b50"


def _svg_available() -> bool:
    """Check if cairosvg is available for rendering."""
    try:
        import cairosvg  # noqa: F401
        return True
    except (ImportError, OSError):
        return False


def compose_cover_svg(
    ai_art: Image.Image,
    title: str,
    subtitle: str = "",
    author: str = "",
    back_description: str = "",
) -> Image.Image | None:
    """
    Compose a cover using the SVG template.

    Returns PIL Image if cairosvg is available, None otherwise.
    Caller should fall back to biblical_compositor if None returned.
    """
    if not SVG_TEMPLATE_PATH.exists():
        log.warning("SVG template not found at %s", SVG_TEMPLATE_PATH)
        return None

    if not _svg_available():
        log.info("cairosvg not available, falling back to PIL compositor")
        return None

    import cairosvg

    # Read template SVG
    svg_text = SVG_TEMPLATE_PATH.read_text(encoding="utf-8")

    # Parse and inject content
    svg_text = _inject_art(svg_text, ai_art)
    svg_text = _inject_text(svg_text, title, subtitle, author, back_description)

    # Render to PNG at 300 DPI (3884x2777)
    png_data = cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        output_width=3884,
        output_height=2777,
    )

    img = Image.open(io.BytesIO(png_data)).convert("RGB")
    return img


def _inject_art(svg_text: str, ai_art: Image.Image) -> str:
    """Inject AI art as base64 image inside the medallion circle."""
    # Convert art to base64 PNG
    buf = io.BytesIO()
    ai_art.convert("RGB").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    # Create circular clip path + image element
    clip_and_image = f"""
    <defs>
      <clipPath id="medallion-clip">
        <circle cx="{MEDALLION_CX}" cy="{MEDALLION_CY}" r="{MEDALLION_R}"/>
      </clipPath>
    </defs>
    <image
      x="{MEDALLION_CX - MEDALLION_R}" y="{MEDALLION_CY - MEDALLION_R}"
      width="{MEDALLION_R * 2}" height="{MEDALLION_R * 2}"
      href="data:image/png;base64,{b64}"
      clip-path="url(#medallion-clip)"
      preserveAspectRatio="xMidYMid slice"
    />
    """

    # Insert BEFORE the closing </svg> but AFTER the defs
    # We want art behind the frame ornaments
    # Find the first <g or <path after </defs> and insert before it
    insert_pos = svg_text.find("</defs>")
    if insert_pos > 0:
        insert_pos = svg_text.find(">", insert_pos) + 1
        # Insert clip def into existing defs, and image after defs
        svg_text = (
            svg_text[:insert_pos]
            + f'\n<clipPath id="medallion-clip"><circle cx="{MEDALLION_CX}" cy="{MEDALLION_CY}" r="{MEDALLION_R}"/></clipPath>'
            + svg_text[insert_pos:]
        )
        # Find after </defs> to insert image
        defs_end = svg_text.find("</defs>")
        after_defs = svg_text.find(">", defs_end) + 1
        image_el = f"""
<image x="{MEDALLION_CX - MEDALLION_R}" y="{MEDALLION_CY - MEDALLION_R}"
  width="{MEDALLION_R * 2}" height="{MEDALLION_R * 2}"
  href="data:image/png;base64,{b64}"
  clip-path="url(#medallion-clip)"
  preserveAspectRatio="xMidYMid slice"/>"""
        svg_text = svg_text[:after_defs] + image_el + svg_text[after_defs:]

    return svg_text


def _inject_text(svg_text: str, title: str, subtitle: str, author: str, back_description: str) -> str:
    """Inject all text elements into SVG."""
    from src.text_renderer import _split_quote_body

    text_elements = []

    # --- Front title (Trajan Pro 3 Bold / Cinzel) ---
    title_upper = title.upper()
    # Word-wrap title to ~15 chars per line
    title_lines = _wrap_text(title_upper, max_chars=18)
    for i, line in enumerate(title_lines):
        y = TITLE_Y + i * 32
        text_elements.append(
            f'<text x="{TITLE_X}" y="{y}" '
            f'font-family="Cinzel, Trajan Pro 3, serif" font-weight="bold" font-size="30" '
            f'fill="{GOLD_HEX}" text-anchor="middle" letter-spacing="2">'
            f'{_xml_escape(line)}</text>'
        )

    # --- Front subtitle ---
    if subtitle:
        sub_lines = _wrap_text(subtitle, max_chars=35)
        for i, line in enumerate(sub_lines):
            y = SUBTITLE_Y + i * 16
            text_elements.append(
                f'<text x="{SUBTITLE_X}" y="{y}" '
                f'font-family="Georgia, serif" font-style="italic" font-size="12" '
                f'fill="{GOLD_HEX}" text-anchor="middle">'
                f'{_xml_escape(line)}</text>'
            )

    # --- Front author ---
    author_upper = author.upper()
    author_lines = _wrap_text(author_upper, max_chars=25)
    for i, line in enumerate(author_lines):
        y = AUTHOR_Y + i * 22
        # White shadow
        text_elements.append(
            f'<text x="{AUTHOR_X}" y="{y + 0.5}" '
            f'font-family="Cinzel, Trajan Pro 3, serif" font-weight="bold" font-size="18" '
            f'fill="{WHITE_HEX}" text-anchor="middle" letter-spacing="1">'
            f'{_xml_escape(line)}</text>'
        )
        # Gold on top
        text_elements.append(
            f'<text x="{AUTHOR_X}" y="{y}" '
            f'font-family="Cinzel, Trajan Pro 3, serif" font-weight="bold" font-size="18" '
            f'fill="{GOLD_HEX}" text-anchor="middle" letter-spacing="1">'
            f'{_xml_escape(line)}</text>'
        )

    # --- Spine (white, bold, uppercase) ---
    spine_text = title.upper()
    text_elements.append(
        f'<text x="{SPINE_X}" y="{SPINE_Y}" '
        f'font-family="Cinzel, Trajan Pro 3, serif" font-weight="bold" font-size="8" '
        f'fill="{WHITE_HEX}" text-anchor="middle" letter-spacing="1" '
        f'transform="rotate(-90 {SPINE_X} {SPINE_Y})">'
        f'{_xml_escape(spine_text)}</text>'
    )

    # --- Back cover ---
    if back_description:
        quote, attrib, body = _split_quote_body(back_description)

        if quote:
            quote_lines = _wrap_text(quote, max_chars=45)
            for i, line in enumerate(quote_lines):
                y = QUOTE_Y + i * 14
                text_elements.append(
                    f'<text x="{BACK_CX}" y="{y}" '
                    f'font-family="Georgia, serif" font-style="italic" font-size="10" '
                    f'fill="{GOLD_HEX}" text-anchor="middle">'
                    f'{_xml_escape(line)}</text>'
                )

            if attrib:
                attr_y = QUOTE_Y + len(quote_lines) * 14 + 8
                text_elements.append(
                    f'<text x="{BACK_CX}" y="{attr_y}" '
                    f'font-family="Georgia, serif" font-style="italic" font-size="8" '
                    f'fill="{GOLD_HEX}" text-anchor="middle">'
                    f'{_xml_escape("— " + attrib)}</text>'
                )

        if body:
            body_lines = _wrap_text(body, max_chars=55)
            body_start = BODY_Y
            for i, line in enumerate(body_lines):
                y = body_start + i * 11
                if y > 580:  # Don't overflow past bottom divider
                    break
                text_elements.append(
                    f'<text x="{BODY_X_LEFT}" y="{y}" '
                    f'font-family="Georgia, serif" font-size="8" '
                    f'fill="{GOLD_HEX}">'
                    f'{_xml_escape(line)}</text>'
                )

    # Insert all text elements before </svg>
    insert_point = svg_text.rfind("</svg>")
    all_text = "\n".join(text_elements)
    svg_text = svg_text[:insert_point] + all_text + "\n" + svg_text[insert_point:]

    return svg_text


def _wrap_text(text: str, max_chars: int = 30) -> list[str]:
    """Simple word-wrap for SVG text."""
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = f"{cur} {word}".strip()
        if len(test) <= max_chars:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
