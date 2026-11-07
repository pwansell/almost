"""Artwork: generated once per Event in the House Style, else Art Library, else Default."""

from __future__ import annotations

import io
import json
import os
from datetime import date

from PIL import Image

from .events import Event
from .store import LocalStore, R2Store

HOUSE_STYLE = """\
An ink and wash painting in the Japanese sumi-e tradition, portrait 3:4.
Subject: {subject}.
Composition: an arch. Motifs fill the top and run down both sides, densest in \
the top corners, thinning and dissolving as they descend. The centre and the \
lower half are open plain white paper; the bottom fifth is almost empty.
Technique: bold, confident black brush strokes with only two or three flat grey \
wash tones. Strong contrast. No fine hatching, no smooth gradients, no paper texture.
The painting fills the whole canvas edge to edge: no scroll, rods, mount, frame, \
border lines or visible paper edges.
Absolutely no text, letters, numbers, signatures, seals or stamps."""

# Art Library themes: keyword -> subject. Generated once with `make-library`.
LIBRARY = {
    "default": "a celebration: festive garlands, stars, confetti and streamers",
    "birthday": "a birthday: balloons, a cake with candles, bunting",
    "anniversary": "an anniversary: two intertwined flowering branches, doves",
    "wedding": "a wedding: blossoms, rings, a garland of roses",
    "christmas": "Christmas: pine branches, baubles, holly, falling snow",
    "newyear": "New Year's Eve: fireworks over a night sky, champagne glasses",
    "easter": "Easter: spring blossoms, painted eggs, rabbits in the grass",
    "holiday": "a holiday: a suitcase, a winding road, palm trees, distant hills",
    "beach": "the beach: waves, shells, palm fronds, a sun low on the horizon",
    "cruise": "a cruise: an ocean liner on waves, gulls, celebration",
    "flight": "travel by air: a plane among clouds and birds",
    "mountains": "the mountains: peaks, pines, mist, a winding trail",
    "snow": "a snow trip: snowy peaks, pines laden with snow, skis",
    "camping": "camping: a tent under tall trees, a campfire, stars",
    "city": "a city trip: rooftops, a bridge, lamp posts, birds",
    "japan": "Japan: cherry blossoms, Mount Fuji, a pagoda roof",
    "garden": "a garden: flowers, leaves, butterflies and bees",
    "concert": "a concert: musical instruments, swirling notes, stage lights",
    "sport": "a sporting day: a stadium, pennants, a ball in flight",
    "graduation": "a graduation: mortarboards tossed in the air, laurels",
    "baby": "a new baby: a crib mobile, stars, a moon, soft clouds",
    "home": "a new home: a cottage, a garden path, a tree, birds",
}


class GenerationCapReached(Exception):
    pass


def _generate(subject: str, model: str) -> Image.Image:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
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
            return Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
    raise RuntimeError("no image in response")


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _load(store: LocalStore | R2Store, key: str) -> Image.Image | None:
    data = store.get(key)
    return Image.open(io.BytesIO(data)).convert("RGB") if data else None


def _take_generation(store, cap: int, today: date) -> None:
    month = today.strftime("%Y-%m")
    counts = json.loads(store.get("state/generations.json") or b"{}")
    if counts.get(month, 0) >= cap:
        raise GenerationCapReached(month)
    counts[month] = counts.get(month, 0) + 1
    store.put("state/generations.json", json.dumps(counts).encode(), "application/json")


def artwork_for(event: Event, store, model: str, cap: int, today: date, log) -> Image.Image:
    key = f"artwork/{event.artwork_key}.png"
    if img := _load(store, key):
        return img
    try:
        _take_generation(store, cap, today)
        subject = event.name + (f" ({event.art_hint})" if event.art_hint else "")
        img = _generate(subject, model)
        store.put(key, _png(img), "image/png")
        log("generated Artwork")
        return img
    except Exception as e:  # cap, no key, API error: fall back, never fail the run
        log(f"Artwork generation unavailable ({type(e).__name__}); using the Art Library")
    if event.art_hint:
        for word in event.art_hint.lower().replace(",", " ").split():
            if img := _load(store, f"library/{word}.png"):
                return img
    return default_artwork(store)


def default_artwork(store) -> Image.Image:
    return _load(store, "library/default.png") or Image.new("RGB", (768, 1024), "white")


def idle_artwork(store) -> Image.Image:
    return _load(store, "idle/idle.png") or default_artwork(store)


def make_library(store, model: str, log, only: list[str] | None = None) -> None:
    for keyword, subject in LIBRARY.items():
        if only and keyword not in only:
            continue
        key = f"library/{keyword}.png"
        if store.get(key):
            continue
        store.put(key, _png(_generate(subject, model)), "image/png")
        log(f"library: made {keyword}")
