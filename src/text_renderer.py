"""
text_renderer.py — Renders text fields onto the biblical cover template.
Uses PIL/Pillow with EB Garamond font, auto-scaling to fit text zones.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Layout constants (finalized via visual editor)
# ---------------------------------------------------------------------------

W, H = 3884, 2777
SPINE_LEFT, SPINE_RIGHT = 1902, 1977
FRONT_W = W - SPINE_RIGHT  # 1907

# Text layout settings (from text_layout_editor.html)
TITLE_SIZE = 135
TITLE_Y = 310           # ~11% down (closer to Tim's 14.8%)
TITLE_MARGIN = 200

SUB_SIZE = 72
SUB_GAP = 50

AUTHOR_MAX_SIZE = 80
AUTHOR_Y = 2350          # ~85% down (closer to Tim's 89%)

SPINE_SIZE = 50

QUOTE_MAX_SIZE = 80
QUOTE_Y = 620
BACK_MARGIN = 120

BODY_MAX_SIZE = 80
BODY_GAP = 103
BODY_Y_END = 1820

# Derived
FRONT_CX = SPINE_RIGHT + FRONT_W // 2
BACK_CX = SPINE_LEFT // 2
BACK_TEXT_W = SPINE_LEFT - BACK_MARGIN * 2
MEDALLION_TOP = 830
MEDALLION_BOTTOM = 830 + 1353

# Colors (extracted from Tim's original Illustrator SVG)
GOLD = (240, 206, 70)         # #f0ce46 — titles, author (from SVG fill)
LIGHT_GOLD = (243, 207, 71)   # #f3cf47 — back cover quote, attribution
CREAM = (243, 207, 71)        # #f3cf47 — subtitle, back body text (same warm gold)

# Fonts (matched to Tim's original covers extracted from PDF)
# Title: Cinzel (free Trajan Pro 3 alternative) — classic display serif
# Author/Spine: Garamond Bold → EB Garamond
# Body/Quote: Georgia (system serif)
FONTS_DIR = Path(__file__).resolve().parent.parent / "config" / "fonts"

def _font_title(size):
    """Cinzel for titles — matches Trajan Pro 3 Bold from originals."""
    return ImageFont.truetype(str(FONTS_DIR / "Cinzel.ttf"), size)

def _font(size, italic=False):
    """Georgia for body text — matches originals. Falls back to EB Garamond."""
    if italic:
        for name in ("Georgiai.ttf", "EBGaramond-Italic.ttf"):
            path = FONTS_DIR / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    for name in ("Georgia.ttf", "EBGaramond.ttf"):
        path = FONTS_DIR / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.truetype(str(FONTS_DIR / "EBGaramond.ttf"), size)

def _font_bold(size):
    """Bold Garamond/Georgia for author — matches originals."""
    for name in ("Georgiab.ttf", "EBGaramond.ttf"):
        path = FONTS_DIR / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.truetype(str(FONTS_DIR / "EBGaramond.ttf"), size)

# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def _wrap(text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if font.getbbox(test)[2] - font.getbbox(test)[0] <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    return lines

def _fit(text, max_w, max_h, start_size, min_size=20, italic=False, font_func=None):
    _fn = font_func or (lambda sz: _font(sz, italic))
    for sz in range(start_size, min_size - 1, -2):
        f = _fn(sz)
        lines = _wrap(text, f, max_w)
        if len(lines) * int(sz * 1.35) <= max_h:
            return f, lines
    f = _fn(min_size)
    return f, _wrap(text, f, max_w)

def _draw_centered(draw, lines, font, cx, y, color, spacing=1.35):
    lh = int(font.size * spacing)
    for line in lines:
        bb = font.getbbox(line)
        draw.text((cx - (bb[2] - bb[0]) // 2, y), line, font=font, fill=color)
        y += lh
    return y

def _draw_justified(draw, lines, font, x_left, x_right, y, color, spacing=1.45):
    """Draw lines with justified alignment (last line left-aligned)."""
    lh = int(font.size * spacing)
    max_w = x_right - x_left
    for i, line in enumerate(lines):
        words = line.split()
        is_last = (i == len(lines) - 1)
        if len(words) <= 1 or is_last:
            draw.text((x_left, y), line, font=font, fill=color)
        else:
            word_widths = [font.getbbox(w)[2] - font.getbbox(w)[0] for w in words]
            total_words_w = sum(word_widths)
            total_space = max_w - total_words_w
            gap = total_space / (len(words) - 1) if len(words) > 1 else 0
            cx = x_left
            for j, w in enumerate(words):
                draw.text((cx, y), w, font=font, fill=color)
                cx += word_widths[j] + gap
        y += lh
    return y

# ---------------------------------------------------------------------------
# Quote/body splitter
# ---------------------------------------------------------------------------

def _split_quote_body(desc):
    if not desc:
        return "", "", ""

    # Normalize spaces but preserve newlines for structure
    text = re.sub(r"[^\S\n]+", " ", desc).strip()

    # Find closing quote mark
    close = -1
    for q in ['\u201d', '"']:
        p = text.find(q, 1)
        if p > 0 and (close < 0 or p < close):
            close = p + 1
    if close < 0:
        flat = text.replace("\n", " ").strip()
        return "", "", flat

    after = text[close:].lstrip(" \n")
    # Strip leading dash (em-dash, en-dash, hyphen)
    dm = re.match(r'^[\u2013\u2014\u2015\-]+\s*', after)
    if not dm:
        flat = text.replace("\n", " ").strip()
        return "", "", flat

    remaining = after[dm.end():]

    # Attribution = short line(s) before the body paragraphs.
    # Attribution names are typically < 50 chars; body prose lines are longer.
    lines = remaining.split("\n")
    attrib_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and len(stripped) >= 50:
            body_start = i
            break
        if stripped:
            attrib_lines.append(stripped)
        body_start = i + 1
    attrib = " ".join(attrib_lines).strip()
    body = " ".join(l.strip() for l in lines[body_start:]).strip()

    quote = text[:close].replace("\n", " ").strip()
    return quote, attrib, body

# ---------------------------------------------------------------------------
# Render functions
# ---------------------------------------------------------------------------

def render_text_on_template(template, title, subtitle="", author="", back_description=""):
    img = template.copy()
    draw = ImageDraw.Draw(img)

    title_w = FRONT_W - TITLE_MARGIN * 2

    # --- Front title (Cinzel — matches Trajan Pro 3 from originals) ---
    font_t, lines_t = _fit(title.upper(), title_w, MEDALLION_TOP - TITLE_Y - 100, TITLE_SIZE, 50, font_func=_font_title)
    y = _draw_centered(draw, lines_t, font_t, FRONT_CX, TITLE_Y, GOLD, 1.15)

    # --- Front subtitle (Georgia Italic — matches originals) ---
    if subtitle:
        sub_y = y + SUB_GAP
        avail = MEDALLION_TOP - sub_y - 20
        if avail > 30:
            font_s, lines_s = _fit(subtitle, title_w, avail, SUB_SIZE, 24, italic=True)
            _draw_centered(draw, lines_s, font_s, FRONT_CX, sub_y, CREAM, 1.3)

    # --- Front author (Cinzel — same as title, matches Trajan Pro 3 from originals) ---
    # Double-render: white shadow behind gold text for depth effect (same as Tim's SVG)
    author_w = FRONT_W - 540 - 80
    author_max_h = H - AUTHOR_Y - 200
    font_a, lines_a = _fit(author.upper(), author_w, author_max_h, AUTHOR_MAX_SIZE, 24, font_func=_font_title)
    _draw_centered(draw, lines_a, font_a, FRONT_CX, AUTHOR_Y + 2, (255, 255, 255), 1.25)  # white shadow
    _draw_centered(draw, lines_a, font_a, FRONT_CX, AUTHOR_Y, GOLD, 1.25)  # gold on top

    # --- Spine ---
    # --- Spine (white, bold, uppercase, title only — matches classic covers) ---
    spine_w = SPINE_RIGHT - SPINE_LEFT
    spine_text = title.upper()
    spine_h = H - 240
    SPINE_WHITE = (255, 255, 255)

    for sz in range(SPINE_SIZE, 12, -1):
        sf = _font_bold(sz)
        bb = sf.getbbox(spine_text)
        if bb[3] - bb[1] <= spine_w - 10 and bb[2] - bb[0] <= spine_h:
            break

    tmp = Image.new("RGBA", (spine_h, spine_w), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    bb = sf.getbbox(spine_text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    td.text(((spine_h - tw) // 2, (spine_w - th) // 2), spine_text, font=sf, fill=SPINE_WHITE)
    rotated = tmp.rotate(90, expand=True)
    px = SPINE_LEFT + (spine_w - rotated.size[0]) // 2
    img.paste(rotated, (px, 120), rotated.split()[3])

    # --- Back cover ---
    if back_description:
        quote, attrib, body = _split_quote_body(back_description)
        y_cur = QUOTE_Y

        # Quote (auto-fit: larger font for shorter quotes)
        if quote:
            quote_max_h = 300
            fq, lq = _fit(quote, BACK_TEXT_W - 40, quote_max_h, QUOTE_MAX_SIZE, 22, italic=True)
            y_cur = _draw_centered(draw, lq, fq, BACK_CX, y_cur, LIGHT_GOLD)

            if attrib:
                y_cur += 10
                attr_sz = max(int(fq.size * 0.75), 20)
                fa = _font(attr_sz, italic=True)
                attr_text = f"\u2014 {attrib}"
                attr_lines = _wrap(attr_text, fa, BACK_TEXT_W - 40)
                y_cur = _draw_centered(draw, attr_lines, fa, BACK_CX, y_cur, LIGHT_GOLD)

            y_cur += BODY_GAP

        # Body (justified, auto-fit to fill available space)
        if body:
            body_max_h = BODY_Y_END - y_cur
            fb, lb = _fit(body, BACK_TEXT_W, body_max_h, BODY_MAX_SIZE, 20)
            _draw_justified(draw, lb, fb, BACK_MARGIN, SPINE_LEFT - BACK_MARGIN, y_cur, CREAM)

    return img
