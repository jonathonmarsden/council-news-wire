"""Render a branded link-card image for councils whose sites expose no og:image.

Most small-shire CMSs publish no OpenGraph image at all - in a sample of the 50
most recent WA articles, none did. Those stories would otherwise post as a bare
text link while metro stories get a rich thumbnail, so the feed looks uneven and
the majority of posts are easy to scroll past.

This module composes a card in the same visual language as the account banners
and avatars: navy field, cream serif headline, a state-coloured spine, and the
council name set in tracked caps. The output is a PNG suitable for uploading as
an app.bsky.embed.external thumbnail.

Rendering is best-effort: every failure path returns None so the caller falls
back to the plain text post rather than publishing a broken card.
"""
from __future__ import annotations

import io
import os
from typing import List, Optional

CARD_W, CARD_H = 1200, 630

# Palette shared with the v4 banners/avatars.
NAVY = (30, 58, 95)
CREAM = (247, 244, 239)
MUTED = (139, 163, 189)

# Per-state accent, matching each account's banner colour.
STATE_COLOURS = {
    "VIC": (223, 132, 43), "NSW": (43, 122, 178), "QLD": (155, 32, 58),
    "SA": (196, 122, 48), "WA": (138, 109, 31), "TAS": (34, 102, 68),
    "NT": (176, 84, 40), "ACT": (48, 96, 168),
}
DEFAULT_ACCENT = (223, 132, 43)

# DejaVu ships in the image via fonts-dejavu-core (see Dockerfile). The serif
# face sets the headline; the sans face sets the small tracked caps.
_SERIF_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",  # local dev (macOS)
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]
_SANS_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _find_font(candidates: List[str]) -> Optional[str]:
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _load(path: Optional[str], size: int):
    from PIL import ImageFont
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int, max_lines: int) -> List[str]:
    """Greedy word wrap to a pixel width.

    Council headlines are not tidy: some are a single 40-character word, others
    run past 120 characters. Over-long single words are hard-split so they can
    never overflow the card, and the last kept line is ellipsised if the text
    does not fit in max_lines.
    """
    def width(s: str) -> int:
        return int(draw.textlength(s, font=font))

    words, lines, cur = text.split(), [], ""
    for word in words:
        while width(word) > max_width and len(word) > 1:
            cut = len(word)
            while cut > 1 and width(word[:cut] + "-") > max_width:
                cut -= 1
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(word[:cut] + "-")
            word = word[cut:]
            if len(lines) >= max_lines:
                return _ellipsise(lines[:max_lines], draw, font, max_width)
        candidate = f"{cur} {word}".strip()
        if width(candidate) <= max_width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines:
                return _ellipsise(lines[:max_lines], draw, font, max_width)
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        return _ellipsise(lines[:max_lines], draw, font, max_width)
    return lines


def _ellipsise(lines: List[str], draw, font, max_width: int) -> List[str]:
    if not lines:
        return lines
    last = lines[-1]
    while last and int(draw.textlength(last + "...", font=font)) > max_width:
        last = last[:-1].rstrip()
    lines[-1] = (last + "...") if last else "..."
    return lines


def render_card(title: str, council_name: str, state: str,
                date_str: str = "", subtitle: str = "") -> Optional[bytes]:
    """Render the card as PNG bytes, or None if rendering is not possible.

    subtitle (an article excerpt) is drawn under the headline when there is
    room for it, which fills the lower half and gives a reader some substance
    beyond the title alone.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None  # Pillow absent -> caller falls back to a text post

    try:
        accent = STATE_COLOURS.get((state or "").upper(), DEFAULT_ACCENT)
        serif_path = _find_font(_SERIF_CANDIDATES)
        sans_path = _find_font(_SANS_CANDIDATES)

        img = Image.new("RGB", (CARD_W, CARD_H), NAVY)
        draw = ImageDraw.Draw(img)

        # State-coloured spine down the left edge.
        draw.rectangle([0, 0, 13, CARD_H], fill=accent)

        left, right_margin = 80, 80
        max_w = CARD_W - left - right_margin

        # Council name, tracked caps.
        label_font = _load(sans_path, 26)
        label = " ".join((council_name or "").upper())  # letter-spacing
        if int(draw.textlength(label, font=label_font)) > max_w:
            label = (council_name or "").upper()
        draw.text((left, 96), label, font=label_font, fill=MUTED)

        # Headline: shrink to fit rather than truncate aggressively.
        for size, max_lines in ((76, 3), (66, 3), (58, 4), (50, 4)):
            headline_font = _load(serif_path, size)
            lines = _wrap(draw, title or "", headline_font, max_w, max_lines)
            if len(lines) <= max_lines:
                break
        line_h = int(size * 1.18)

        # Excerpt lines are measured before drawing so the whole text block can
        # be vertically centred; a short headline left a conspicuous gap above
        # the footer when the block was pinned to a fixed top.
        sub_font = _load(sans_path, 28)
        sub_lines: List[str] = []
        if subtitle:
            budget = (470 - 190 - len(lines) * line_h) // 38
            if budget >= 1:
                sub_lines = _wrap(draw, subtitle, sub_font, max_w, min(2, budget))

        block_h = len(lines) * line_h + (14 + len(sub_lines) * 38 if sub_lines else 0)
        top, bottom = 180, 500  # region between the council label and the rule
        y = max(top, top + ((bottom - top) - block_h) // 2)

        for line in lines:
            draw.text((left, y), line, font=headline_font, fill=CREAM)
            y += line_h
        if sub_lines:
            y += 14
            for sline in sub_lines:
                draw.text((left, y), sline, font=sub_font, fill=MUTED)
                y += 38

        # Footer: accent rule + attribution.
        draw.rectangle([left, 528, left + 120, 534], fill=accent)
        foot_font = _load(sans_path, 24)
        state_label = "Canberra & ACT News Wire" if (state or "").upper() == "ACT" \
            else f"{(state or '').upper()} Councils News Wire"
        footer = f"{date_str}  ·  {state_label}" if date_str else state_label
        draw.text((left, 566), footer, font=foot_font, fill=MUTED)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return None
