# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11", "google-genai>=1.0", "numpy>=2"]
# ///
"""Throwaway prototype: render sample Plates for Almost.

Usage:
  uv run render.py                # needs GEMINI_API_KEY (env or repo-root .env)
  uv run render.py --placeholder  # stand-in Artwork, no API call
"""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"
FONT = REPO / "studio" / "assets" / "fonts" / "BodoniModa[opsz,wght].ttf"
FONT_ITALIC = REPO / "studio" / "assets" / "fonts" / "BodoniModa-Italic[opsz,wght].ttf"

W, H = 1404, 1872  # reMarkable 2, portrait
MAT = 0.10  # Mat Margin, fraction of each dimension
MX, MY = int(W * MAT), int(H * MAT)
GREYS = 16

HOUSE_STYLE = """\
An ink and wash painting in the Japanese sumi-e tradition, portrait 3:4.
Subject: {subject}.
Composition: an arch. Motifs fill the top and run down both sides, densest in \
the top corners, thinning and dissolving as they descend. The centre and the \
lower half are open plain white paper; the bottom fifth is almost empty.
Technique: bold, confident black brush strokes with only two or three flat grey \
wash tones. Strong contrast. No fine hatching, no smooth gradients, no paper texture.
Absolutely no text, letters, numbers, signatures, seals or stamps."""


@dataclass
class Event:
    name: str
    day: date
    art_hint: str = ""


def days_until(event: Event, today: date) -> int:
    return (event.day - today).days


# ---------- Artwork ----------

def load_key() -> str | None:
    if k := os.environ.get("GEMINI_API_KEY"):
        return k
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def generate_artwork(event: Event, model: str | None) -> Image.Image:
    from google import genai
    from google.genai import types

    key = load_key()
    if not key:
        raise SystemExit("No GEMINI_API_KEY in env or .env; use --placeholder")
    client = genai.Client(api_key=key)
    if model is None:
        names = [m.name for m in client.models.list() if "image" in m.name and "gemini" in m.name]
        if not names:
            raise SystemExit("No Gemini image model available to this key")
        model = sorted(names)[-1].removeprefix("models/")
        print(f"using model {model} (from {names})")
    subject = event.name + (f" ({event.art_hint})" if event.art_hint else "")
    resp = client.models.generate_content(
        model=model,
        contents=HOUSE_STYLE.format(subject=subject),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="3:4"),
        ),
    )
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            from io import BytesIO
            return Image.open(BytesIO(part.inline_data.data)).convert("RGB")
    raise SystemExit(f"No image returned: {resp}")


def placeholder_artwork(seed: int = 7) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    for _ in range(260):
        # bias blobs toward edges and corners
        x = rnd.choice([rnd.uniform(0, W * 0.25), rnd.uniform(W * 0.75, W), rnd.uniform(0, W)])
        y = rnd.choice([rnd.uniform(0, H * 0.22), rnd.uniform(H * 0.8, H), rnd.uniform(0, H)])
        cx, cy = abs(x - W / 2) / (W / 2), abs(y - H / 2) / (H / 2)
        if max(cx, cy) < 0.55:
            continue
        r = rnd.uniform(8, 70) * max(cx, cy)
        d.ellipse([x - r, y - r * 0.4, x + r, y + r * 0.4], fill=rnd.choice([30, 110, 170, 210]))
    return img.filter(ImageFilter.GaussianBlur(3)).convert("RGB")


def whiten_paper(img: Image.Image) -> Image.Image:
    """Map the Artwork's paper tone (and any shading on it) to pure white.

    Generated images often look like photographed paper: off-white, with
    darker edges. The paper tone is the most common light value; anything
    near or above it becomes white, and the rest stretches to fill the range.
    """
    hist = img.histogram()
    paper = max(range(128, 256), key=lambda v: hist[v])
    cut = max(150, paper - 28)
    return img.point(lambda v: 255 if v >= cut else round(v * 255 / cut))


def cover(img: Image.Image) -> Image.Image:
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    l, t = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((l, t, l + W, t + H))


# ---------- Typography ----------

def font(path: Path, size: int, wght: int = 500, opsz: int = 11) -> ImageFont.FreeTypeFont:
    # Small optical sizes keep hairlines sturdy enough for e-ink.
    f = ImageFont.truetype(str(path), size)
    f.set_variation_by_axes([wght, opsz])  # axes: wght, opsz
    return f


def tracked(draw: ImageDraw.ImageDraw, xy, text, f, tracking, fill=0, anchor="ms"):
    widths = [draw.textlength(c, font=f) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=f, fill=fill, anchor="ls")
        x += w + tracking
    return total


def fit_size(draw, text, path, max_w, start, minimum, tracking_ratio=0.0, wght=500):
    size = start
    while size > minimum:
        f = font(path, size, wght)
        w = sum(draw.textlength(c, font=f) for c in text) + size * tracking_ratio * (len(text) - 1)
        if w <= max_w:
            return f, text
        size -= 2
    f = font(path, minimum, wght)
    while text and sum(draw.textlength(c, font=f) for c in text + "…") > max_w:
        text = text[:-1]
    return f, text.rstrip() + "…"


def countdown_block(n: int, safe_w: int) -> Image.Image:
    """The numeral and its word, as a tight white-on-black mask."""
    canvas = Image.new("L", (W, 900), 0)
    d = ImageDraw.Draw(canvas)
    if n >= 2:
        f_num = font(FONT, 560 if n < 100 else 430, 500, opsz=28)
        d.text((W / 2, 560), str(n), font=f_num, fill=255, anchor="ms")
        d.text((W / 2, 690), "days", font=font(FONT_ITALIC, 96, 400, opsz=16), fill=255, anchor="ms")
    else:
        word = "Today" if n == 0 else "Tomorrow"
        f_word, _ = fit_size(d, word, FONT_ITALIC, safe_w - 80, 260, 120, wght=500)
        d.text((W / 2, 500), word, font=f_word, fill=255, anchor="ms")
    return canvas.crop(canvas.getbbox())


def place_block(block: Image.Image, art: Image.Image, region, pad: int = 40, step: int = 8):
    """Find the height and size at which the centred block overlaps the least ink.

    Returns (x, y, block) with the block possibly scaled down.
    """
    import numpy as np

    # 1 wherever there is any visible ink, so even a thin overlap counts fully.
    ink = (255 - np.asarray(art.filter(ImageFilter.MaxFilter(1)), dtype=np.float64) > 40).astype(np.float64)
    ink = ink.reshape(H // step, step, W // step, step).max(axis=(1, 3)) if H % step == 0 and W % step == 0 \
        else ink[::step, ::step]
    integ = np.pad(ink.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    rx0, ry0, rx1, ry1 = region
    cx, cy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
    best = None
    for scale in (1.0, 0.92, 0.84, 0.76, 0.68):
        bw, bh = round(block.width * scale) + 2 * pad, round(block.height * scale) + 2 * pad
        if bw > rx1 - rx0 or bh > ry1 - ry0:
            continue
        gw, gh = bw // step, bh // step
        ys = np.arange(ry0 // step, (ry1 - bh) // step + 1)
        # Always horizontally centred; only the height and size adapt to the art.
        xs = np.array([round((cx - bw / 2) / step)])
        Y, X = np.meshgrid(ys, xs, indexing="ij")
        box = integ[Y + gh, X + gw] - integ[Y, X + gw] - integ[Y + gh, X] + integ[Y, X]
        frac_ink = box / (gw * gh)
        dist = np.hypot((X * step + bw / 2 - cx) / W, (Y * step + bh / 2 - cy) / H)
        cost = 1000 * frac_ink + 60 * dist + 40 * (1 - scale)
        i = np.unravel_index(cost.argmin(), cost.shape)
        if best is None or cost[i] < best[0]:
            best = (cost[i], round(cx - bw / 2) + pad, Y[i] * step + pad, scale)
    _, x, y, scale = best
    if scale != 1.0:
        block = block.resize((round(block.width * scale), round(block.height * scale)), Image.LANCZOS)
    return int(x), int(y), block


def paste_with_halo(base: Image.Image, block: Image.Image, xy, spread: int = 26):
    """Draw the block in black with a soft white halo so it sits cleanly on the Artwork."""
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


def offline_mark(d: ImageDraw.ImageDraw, x: int, y: int):
    cx, cy = x + 38, y + 44
    d.ellipse([x - 4, y - 4, x + 80, y + 52], fill=255)
    for r in (34, 22):
        d.arc([cx - r, cy - r, cx + r, cy + r], 220, 320, fill=0, width=5)
    d.ellipse([cx - 5, cy - 9, cx + 5, cy + 1], fill=0)
    d.line([x + 6, y + 2, x + 70, y + 46], fill=0, width=5)


# ---------- Plate ----------

def render_plate(art: Image.Image, event: Event, today: date, up_next: Event | None = None,
                 low_battery=False, offline=False) -> Image.Image:
    # Paper to pure white so the Banner and open centre don't speckle when dithered.
    img = whiten_paper(cover(art).convert("L"))
    d = ImageDraw.Draw(img)
    safe_w = W - 2 * MX

    # Banner
    bh = 250
    top = H - MY - bh
    d.rectangle([MX, top, W - MX, H - MY], fill=255)
    d.line([MX + 40, top + 22, W - MX - 40, top + 22], fill=0, width=2)
    name = event.name.upper()
    f_name, name = fit_size(d, name, FONT, safe_w - 120, 70, 40, tracking_ratio=0.18, wght=600)
    name_y = top + (120 if up_next else 150)
    tracked(d, (W / 2, name_y), name, f_name, f_name.size * 0.18)
    if up_next:
        n = days_until(up_next, today)
        f_up = font(FONT_ITALIC, 40, 400)
        d.text((W / 2, top + 195), f"then {up_next.name} · {n} days", font=f_up, fill=60, anchor="ms")

    # Countdown: typeset as one block, then placed in the Artwork's open space.
    block = countdown_block(days_until(event, today), safe_w)
    x, y, block = place_block(block, img, (MX, MY, W - MX, top - 20))
    paste_with_halo(img, block, (x, y))

    d = ImageDraw.Draw(img)
    if low_battery:
        low_battery_mark(d, W - MX - 110, MY + 30)
    if offline:
        offline_mark(d, MX + 30, MY + 24)
    return dither(img)


def dither(img: Image.Image) -> Image.Image:
    pal = Image.new("P", (1, 1))
    levels = [round(i * 255 / (GREYS - 1)) for i in range(GREYS)]
    pal.putpalette(sum(([v, v, v] for v in levels), []) + [0] * 3 * (256 - GREYS))
    return img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placeholder", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--regenerate", action="store_true", help="ignore cached Artwork")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    cruise = Event("40th Birthday Cruise", date(2027, 1, 28), "ocean liner, waves, gulls, celebration")

    model = args.model or "gemini-3.1-flash-lite-image"  # pro showed no meaningful gain
    cache = OUT / f"artwork-cruise-{model}.png"
    if args.placeholder:
        art = placeholder_artwork()
    elif cache.exists() and not args.regenerate:
        art = Image.open(cache).convert("RGB")
    else:
        art = generate_artwork(cruise, model)
        art.save(cache)

    plates = {
        "1-countdown-2026-11-07": dict(today=date(2026, 11, 7)),
        "2-tomorrow-2027-01-27": dict(today=date(2027, 1, 27)),
        "3-event-day-2027-01-28": dict(today=date(2027, 1, 28)),
        "4-marks-2026-11-07": dict(today=date(2026, 11, 7), low_battery=True, offline=True),
    }
    for name, kw in plates.items():
        path = OUT / f"plate-{name}-{'placeholder' if args.placeholder else model}.png"
        render_plate(art, cruise, **kw).save(path)
        print(path)


if __name__ == "__main__":
    main()
