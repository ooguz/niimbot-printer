"""Render label text to a 1-bit bitmap for the B1."""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

__all__ = ["render_name_label"]

# Extra margin at bottom of bitmap — printers often clip the last rows; keep room
# for descenders (e.g. g, j, ş, ğ).
_BOTTOM_SAFE_PX = 32


def _try_truetype(paths: list[str], size: int) -> ImageFont.FreeTypeFont | None:
    for path in paths:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return None


def _load_font(font_path: str | None, font_size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(8, int(font_size))
    candidates: list[str] = []
    if font_path:
        if bold:
            root, ext = os.path.splitext(font_path)
            if ext.lower() in (".ttf", ".otf"):
                candidates.append(f"{root}-Bold{ext}")
        candidates.append(font_path)
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "DejaVuSans.ttf",
        ]
    )
    font = _try_truetype(candidates, size)
    if font is not None:
        return font
    return ImageFont.load_default()


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    text = text.strip()
    if not text:
        return [""]
    lines: list[str] = []
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            lines.append("")
            continue
        words = raw_line.split()
        current: list[str] = []
        for word in words:
            trial = " ".join(current + [word]) if current else word
            bbox = draw.textbbox((0, 0), trial, font=font, anchor="lt")
            line_w = bbox[2] - bbox[0]
            if line_w <= max_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
    return lines if lines else [""]


def _ink_extents_rgb(im: Image.Image) -> tuple[int, int, int, int] | None:
    """Bounding box of non-white pixels, or None if empty."""
    px = im.load()
    w, h = im.size
    minx, miny, maxx, maxy = w, h, -1, -1
    for yy in range(h):
        for xx in range(w):
            if px[xx, yy] != (255, 255, 255):
                minx = min(minx, xx)
                miny = min(miny, yy)
                maxx = max(maxx, xx)
                maxy = max(maxy, yy)
    if maxx < 0:
        return None
    return (minx, miny, maxx, maxy)


def render_name_label(
    text: str,
    width_px: int = 384,
    height_px: int = 240,
    *,
    font_path: str | None = None,
    font_size: int = 36,
    bold: bool = False,
    margin: int = 8,
) -> Image.Image:
    """
    Produce a white background, black text, mode ``'1'`` image.
    ``width_px`` must be a multiple of 8 (niimctl constraint).

    Each line is drawn with ``anchor=\"lt\"`` so ``textbbox`` matches placement.
    A small bottom guard band avoids clipping on printers that skip the last rows.
    """
    w = int(width_px)
    h = int(height_px)
    if w % 8:
        raise ValueError("width_px must be a multiple of 8")
    m = max(0, int(margin))

    inner_w = w - 2 * m
    inner_h = h - 2 * m
    usable_h = max(1, inner_h - _BOTTOM_SAFE_PX)

    size = max(8, int(font_size))
    while size >= 8:
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = _load_font(font_path, size, bold)
        lines = _wrap_lines(draw, text, font, inner_w)
        line_gap = max(2, size // 12)

        line_bbs: list[tuple[int, int, int, int]] = []
        for line in lines:
            if not line:
                line_bbs.append((0, 0, 0, line_gap))
            else:
                line_bbs.append(draw.textbbox((0, 0), line, font=font, anchor="lt"))

        line_heights = [b[3] - b[1] for b in line_bbs]
        line_widths = [b[2] - b[0] for b in line_bbs]
        if not line_heights:
            line_heights = [getattr(font, "size", 10) or 10]
            line_widths = [0]

        total_h = sum(line_heights) + max(0, len(lines) - 1) * line_gap
        max_line_w = max(line_widths) if line_widths else 0

        if total_h > usable_h or max_line_w > inner_w:
            size -= 2
            continue

        y = m + (usable_h - total_h) // 2
        for i, line in enumerate(lines):
            lw = line_widths[i]
            lh = line_heights[i]
            if line:
                x = m + (inner_w - lw) // 2
                draw.text((x, y), line, font=font, fill=(0, 0, 0), anchor="lt")
            y += lh + line_gap

        ink = _ink_extents_rgb(img)
        if ink is not None and ink[3] > h - 1 - _BOTTOM_SAFE_PX:
            size -= 2
            continue

        return img.convert("1")

    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_path, 8, bold)
    lines = _wrap_lines(draw, text, font, inner_w)
    line_gap = 2
    line_bbs = [
        (0, 0, 0, line_gap) if not line else draw.textbbox((0, 0), line, font=font, anchor="lt")
        for line in lines
    ]
    line_heights = [b[3] - b[1] for b in line_bbs]
    line_widths = [b[2] - b[0] for b in line_bbs]
    total_h = sum(line_heights) + max(0, len(lines) - 1) * line_gap
    y = m + (usable_h - min(total_h, usable_h)) // 2
    for i, line in enumerate(lines):
        lw = line_widths[i]
        lh = line_heights[i]
        if line:
            x = m + (inner_w - lw) // 2
            draw.text((x, y), line, font=font, fill=(0, 0, 0), anchor="lt")
        y += lh + line_gap
    return img.convert("1")
