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

W, H = 2898, 2114

# Bounding boxes from visual editor (exact pixel coordinates at 2898x2114)
# Text will NEVER overflow these boxes.
BOX = {
    'title':    {'x': 1691, 'y': 213,  'w': 1005, 'h': 278},
    'subtitle': {'x': 1622, 'y': 523,  'w': 1174, 'h': 200},
    'author':   {'x': 1800, 'y': 1753, 'w': 851,  'h': 178},
    'spine':    {'x': 1379, 'y': 100,  'w': 130,  'h': 1914},
    'quote':    {'x': 114,  'y': 464,  'w': 1149, 'h': 214},
    'attrib':   {'x': 116,  'y': 691,  'w': 1149, 'h': 60},
    'body':     {'x': 120,  'y': 784,  'w': 1152, 'h': 680},
}

# Derived from boxes
SPINE_LEFT = BOX['spine']['x']
SPINE_RIGHT = BOX['spine']['x'] + BOX['spine']['w']
FRONT_W = W - SPINE_RIGHT


    # No more _dynamic_sizes — _fit() handles everything using BOX dimensions

# Derived
FRONT_CX = BOX['title']['x'] + BOX['title']['w'] // 2
BACK_CX = BOX['quote']['x'] + BOX['quote']['w'] // 2

# Colors (extracted from Tim's SVG)
TITLE_GOLD = (243, 207, 71)   # #f3cf47 — front title
AUTHOR_GOLD = (242, 207, 70)  # #f2cf46 — author gold layer
QUOTE_GOLD = (240, 206, 70)   # #f0ce46 — back quote
WHITE = (255, 255, 255)       # subtitle, spine, author shadow, back body

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

def _fit(text, max_w, max_h, start_size, min_size=20, italic=False, font_func=None, spacing=1.35):
    _fn = font_func or (lambda sz: _font(sz, italic))
    for sz in range(start_size, min_size - 1, -2):
        f = _fn(sz)
        lines = _wrap(text, f, max_w)
        if len(lines) * int(sz * spacing) <= max_h:
            return f, lines
    f = _fn(min_size)
    return f, _wrap(text, f, max_w)

def _draw_centered(draw, lines, font, cx, y, color, spacing=1.35, box_h=0, valign="top"):
    """Draw centered text. valign='bottom' pushes text to bottom of box_h."""
    lh = int(font.size * spacing)
    total_h = len(lines) * lh
    if valign == "bottom" and box_h > 0 and total_h < box_h:
        y = y + box_h - total_h  # push to bottom edge
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
    """Render all text into bounding boxes. Text auto-fits — never overflows."""
    img = template.copy()
    draw = ImageDraw.Draw(img)

    b = BOX  # shorthand

    # Max font sizes from Tim's Illustrator (45pt, 21pt, 34pt, 25pt, 15pt, 12pt × 3.26px/pt)
    TITLE_MAX = 146
    SUB_MAX = 68
    AUTH_MAX = 110
    SPINE_MAX = 81
    QUOTE_MAX = 48
    BODY_MAX = 60

    # --- TITLE: Cinzel bold, gold, bottom-aligned so it's always close to subtitle ---
    title_cx = b['title']['x'] + b['title']['w'] // 2
    ft, lt = _fit(title.upper(), b['title']['w'], b['title']['h'], TITLE_MAX, 40, font_func=_font_title)
    _draw_centered(draw, lt, ft, title_cx, b['title']['y'], TITLE_GOLD, 1.15, box_h=b['title']['h'], valign="bottom")

    # --- SUBTITLE: Georgia regular (NOT italic), white, centered in box ---
    if subtitle:
        sub_cx = b['subtitle']['x'] + b['subtitle']['w'] // 2
        fs, ls = _fit(subtitle, b['subtitle']['w'], b['subtitle']['h'], SUB_MAX, 20, italic=False)
        _draw_centered(draw, ls, fs, sub_cx, b['subtitle']['y'], WHITE, 1.25)

    # --- AUTHOR: Cinzel bold, white shadow + gold, centered in box ---
    auth_cx = b['author']['x'] + b['author']['w'] // 2
    fa, la = _fit(author.upper(), b['author']['w'], b['author']['h'], AUTH_MAX, 24, font_func=_font_title)
    _draw_centered(draw, la, fa, auth_cx, b['author']['y'] + 2, WHITE, 1.15)
    _draw_centered(draw, la, fa, auth_cx, b['author']['y'], AUTHOR_GOLD, 1.15)

    # --- SPINE: Cinzel bold, white, rotated ---
    spine_text = title.upper()
    sw = b['spine']['w']
    sh = b['spine']['h']

    for sz in range(SPINE_MAX, 15, -1):
        sf = _font_title(sz)
        bb = sf.getbbox(spine_text)
        if bb[3] - bb[1] <= sw - 6 and bb[2] - bb[0] <= sh:
            break

    tmp = Image.new("RGBA", (sh, sw), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    bb = sf.getbbox(spine_text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    td.text(((sh - tw) // 2, (sw - th) // 2), spine_text, font=sf, fill=WHITE)
    rotated = tmp.rotate(-90, expand=True)
    img.paste(rotated, (b['spine']['x'], b['spine']['y']), rotated.split()[3])

    # --- BACK COVER ---
    if back_description:
        quote, attrib, body = _split_quote_body(back_description)

        quote_cx = b['quote']['x'] + b['quote']['w'] // 2

        # Quote: regular Georgia, gold, bottom-aligned so it's close to attribution
        if quote:
            fq, lq = _fit(quote, b['quote']['w'], b['quote']['h'], QUOTE_MAX, 18, italic=False)
            _draw_centered(draw, lq, fq, quote_cx, b['quote']['y'], QUOTE_GOLD, box_h=b['quote']['h'], valign="bottom")

        # Attribution: italic Georgia, gold, centered
        if attrib:
            attrib_cx = b['attrib']['x'] + b['attrib']['w'] // 2
            fa_attr, la_attr = _fit(f"\u2014 {attrib}", b['attrib']['w'], b['attrib']['h'], 36, 16, italic=True)
            _draw_centered(draw, la_attr, fa_attr, attrib_cx, b['attrib']['y'], QUOTE_GOLD)

        # Body: Georgia regular, white + gold shadow, justified
        if body:
            fb, lb = _fit(body, b['body']['w'], b['body']['h'], BODY_MAX, 18, spacing=1.45)
            bx = b['body']['x']
            bx_right = b['body']['x'] + b['body']['w']
            by = b['body']['y']
            _draw_justified(draw, lb, fb, bx, bx_right, by + 1, QUOTE_GOLD)
            _draw_justified(draw, lb, fb, bx, bx_right, by, WHITE)

    return img
