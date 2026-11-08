"""Rendering Plates: Artwork, Countdown, Banner and marks, dithered for e-ink."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .events import DayPlan

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT = FONTS / "BodoniModa[opsz,wght].ttf"
FONT_ITALIC = FONTS / "BodoniModa-Italic[opsz,wght].ttf"


@dataclass(frozen=True)
class Layout:
    width: int = 1404
    height: int = 1872
    greys: int = 16
    top: int = 187
    bottom: int = 187
    left: int = 140
    right: int = 140
    banner_height: int = 250

    @classmethod
    def from_settings(cls, s: dict) -> "Layout":
        return cls(width=s["frame"]["width"], height=s["frame"]["height"], greys=s["frame"]["greys"],
                   **s["mat_margin"])

    @property
    def safe_width(self) -> int:
        return self.width - self.left - self.right

    @property
    def banner_top(self) -> int:
        return self.height - self.bottom - self.banner_height


# ---------- Typography ----------

def font(path: Path, size: int, wght: int = 500, opsz: int = 11) -> ImageFont.FreeTypeFont:
    # Small optical sizes keep the Didone hairlines sturdy enough for e-ink.
    f = ImageFont.truetype(str(path), size)
    f.set_variation_by_axes([wght, opsz])  # axes: wght, opsz
    return f


def _width(draw, text, f, tracking=0.0):
    return sum(draw.textlength(c, font=f) for c in text) + tracking * (len(text) - 1)


def fit(draw, text, path, max_w, start, minimum, tracking_ratio=0.0, wght=500, opsz=11):
    """Largest size from start down to minimum that fits; then an ellipsis."""
    for size in range(start, minimum - 1, -2):
        f = font(path, size, wght, opsz)
        if _width(draw, text, f, size * tracking_ratio) <= max_w:
            return f, text
    f = font(path, minimum, wght, opsz)
    while text and _width(draw, text + "…", f, minimum * tracking_ratio) > max_w:
        text = text[:-1]
    return f, text.rstrip() + "…"


def tracked(draw, cx, y, text, f, tracking, fill=0):
    x = cx - _width(draw, text, f, tracking) / 2
    for c in text:
        draw.text((x, y), c, font=f, fill=fill, anchor="ls")
        x += draw.textlength(c, font=f) + tracking


# ---------- Artwork preparation ----------

def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def whiten_paper(img: Image.Image) -> Image.Image:
    """Generated images often look like photographed paper: off-white with darker
    edges. Map the paper tone, and anything near it, to pure white."""
    hist = img.histogram()
    paper = max(range(128, 256), key=lambda v: hist[v])
    cut = max(150, paper - 28)
    return img.point(lambda v: 255 if v >= cut else round(v * 255 / cut))


def dither(img: Image.Image, greys: int) -> Image.Image:
    pal = Image.new("P", (1, 1))
    levels = [round(i * 255 / (greys - 1)) for i in range(greys)]
    pal.putpalette(sum(([v, v, v] for v in levels), []) + [0] * 3 * (256 - greys))
    return img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")


# ---------- Countdown ----------

def countdown_block(days_left: int, L: Layout) -> Image.Image:
    """The numeral and its word, as a tight white-on-black mask."""
    canvas = Image.new("L", (L.width, 900), 0)
    d = ImageDraw.Draw(canvas)
    if days_left >= 2:
        f_num = font(FONT, 560 if days_left < 100 else 430, 500, opsz=28)
        d.text((L.width / 2, 560), str(days_left), font=f_num, fill=255, anchor="ms")
        d.text((L.width / 2, 690), "days", font=font(FONT_ITALIC, 96, 400, opsz=16), fill=255, anchor="ms")
    else:
        word = "Today" if days_left == 0 else "Tomorrow"
        f_word, _ = fit(d, word, FONT_ITALIC, L.safe_width - 80, 260, 120)
        d.text((L.width / 2, 500), word, font=f_word, fill=255, anchor="ms")
    return canvas.crop(canvas.getbbox())


def place_block(block: Image.Image, art: Image.Image, region, pad: int = 40, step: int = 8):
    """The height and size at which the horizontally centred block overlaps least ink."""
    w, h = art.size
    ink = (255 - np.asarray(art, dtype=np.float64) > 40).astype(np.float64)
    ink = ink[: h - h % step, : w - w % step].reshape(h // step, step, w // step, step).max(axis=(1, 3))
    integ = np.pad(ink.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    rx0, ry0, rx1, ry1 = region
    cx, cy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
    best = None
    for scale in (1.0, 0.92, 0.84, 0.76, 0.68, 0.6):
        bw, bh = round(block.width * scale) + 2 * pad, round(block.height * scale) + 2 * pad
        if bw > rx1 - rx0 or bh > ry1 - ry0:
            continue
        gw, gh = bw // step, bh // step
        x = round((cx - bw / 2) / step)
        ys = np.arange(ry0 // step, (ry1 - bh) // step + 1)
        box = integ[ys + gh, x + gw] - integ[ys, x + gw] - integ[ys + gh, x] + integ[ys, x]
        cost = 1000 * box / (gw * gh) + 60 * np.abs(ys * step + bh / 2 - cy) / h + 40 * (1 - scale)
        i = int(cost.argmin())
        if best is None or cost[i] < best[0]:
            best = (cost[i], round(cx - bw / 2) + pad, int(ys[i]) * step + pad, scale)
    if best is None:  # region too small: fall back to centred, scaled to fit
        scale = min((rx1 - rx0) / block.width, (ry1 - ry0) / block.height, 1.0)
        best = (0, round(cx - block.width * scale / 2), round(cy - block.height * scale / 2), scale)
    _, x, y, scale = best
    if scale != 1.0:
        block = block.resize((max(1, round(block.width * scale)), max(1, round(block.height * scale))), Image.LANCZOS)
    return int(x), int(y), block


def paste_with_halo(base: Image.Image, block: Image.Image, xy, spread: int = 26):
    mask = Image.new("L", base.size, 0)
    mask.paste(block, xy)
    glow = mask.filter(ImageFilter.MaxFilter(spread | 1)).filter(ImageFilter.GaussianBlur(spread))
    base.paste(255, (0, 0), glow.point(lambda v: min(255, v * 2)))
    base.paste(0, (0, 0), mask)


# ---------- Marks ----------

def low_battery_mark(d: ImageDraw.ImageDraw, x: int, y: int):
    d.rounded_rectangle([x, y, x + 70, y + 34], radius=5, outline=0, width=4, fill=255)
    d.rectangle([x + 70, y + 10, x + 77, y + 24], fill=0)
    d.rectangle([x + 8, y + 8, x + 18, y + 26], fill=0)


def charged_mark(d: ImageDraw.ImageDraw, x: int, y: int):
    """A full battery and the word, so a glance across the room says unplug me."""
    d.rounded_rectangle([x - 150, y - 12, x + 92, y + 46], radius=10, fill=255)
    d.text((x - 16, y + 30), "charged", font=font(FONT_ITALIC, 34, 500), fill=0, anchor="rs")
    d.rounded_rectangle([x, y, x + 70, y + 34], radius=5, outline=0, width=4, fill=0)
    d.rectangle([x + 70, y + 10, x + 77, y + 24], fill=0)


def offline_mark(d: ImageDraw.ImageDraw, x: int, y: int):
    cx, cy = x + 38, y + 44
    d.ellipse([x - 4, y - 4, x + 80, y + 52], fill=255)
    for r in (34, 22):
        d.arc([cx - r, cy - r, cx + r, cy + r], 220, 320, fill=0, width=5)
    d.ellipse([cx - 5, cy - 9, cx + 5, cy + 1], fill=0)
    d.line([x + 6, y + 2, x + 70, y + 46], fill=0, width=5)


def _marks(img: Image.Image, L: Layout, low_battery: bool, offline: bool, charged: bool = False):
    d = ImageDraw.Draw(img)
    if charged:  # replaces the Low Battery Mark: a full battery outranks an old low report
        charged_mark(d, L.width - L.right - 110, L.top + 30)
    elif low_battery:
        low_battery_mark(d, L.width - L.right - 110, L.top + 30)
    if offline:
        offline_mark(d, L.left + 30, L.top + 24)


# ---------- Plates ----------

def render_plate(plan: DayPlan, art: Image.Image, L: Layout, low_battery=False, offline=False,
                 charged=False) -> Image.Image:
    img = whiten_paper(cover(art, L.width, L.height).convert("L"))
    if plan.idle:  # Idle: the Idle Artwork alone, no text
        _marks(img, L, low_battery, offline, charged)
        return dither(img, L.greys)

    d = ImageDraw.Draw(img)
    top = L.banner_top
    d.rectangle([L.left, top, L.width - L.right, L.height - L.bottom], fill=255)
    d.line([L.left + 40, top + 22, L.width - L.right - 40, top + 22], fill=0, width=2)
    f_name, name = fit(d, plan.title.upper(), FONT, L.safe_width - 120, 70, 40, tracking_ratio=0.18, wght=600)
    tracked(d, L.width / 2, top + (120 if plan.up_next else 150), name, f_name, f_name.size * 0.18)
    if plan.up_next:
        n = (plan.up_next[0].day - plan.day).days
        nxt = " & ".join(e.name for e in plan.up_next)
        f_up, line = fit(d, f"then {nxt} · {n} days", FONT_ITALIC, L.safe_width - 120, 40, 28, wght=400)
        d.text((L.width / 2, top + 195), line, font=f_up, fill=60, anchor="ms")

    block = countdown_block(plan.days_left, L)
    x, y, block = place_block(block, img, (L.left, L.top, L.width - L.right, top - 20))
    paste_with_halo(img, block, (x, y))
    _marks(img, L, low_battery, offline, charged)
    return dither(img, L.greys)


def render_charge_me(L: Layout) -> Image.Image:
    img = Image.new("L", (L.width, L.height), 255)
    d = ImageDraw.Draw(img)
    cx, cy = L.width // 2, L.height // 2 - 120
    d.rounded_rectangle([cx - 220, cy - 100, cx + 200, cy + 100], radius=24, outline=0, width=12)
    d.rectangle([cx + 200, cy - 40, cx + 236, cy + 40], fill=0)
    d.rectangle([cx - 190, cy - 70, cx - 150, cy + 70], fill=0)
    f, _ = fit(d, "Please charge me", FONT_ITALIC, L.safe_width - 80, 120, 60, wght=500)
    d.text((cx, cy + 320), "Please charge me", font=f, fill=0, anchor="ms")
    return dither(img, L.greys)
