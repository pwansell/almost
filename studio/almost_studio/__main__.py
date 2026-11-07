"""The Studio.

  python -m almost_studio render [--local DIR] [--ics FILE] [--today YYYY-MM-DD]
  python -m almost_studio make-library [--local DIR] [keyword ...]

Without --local, works against R2 (R2_* env vars). Without --ics, reads the
Event Calendar from ICAL_URL. Logs only counts and statuses, never Event names:
the workflow logs are public.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tomllib
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import artwork
from .events import parse_events, plan_day
from .plate import Layout, render_charge_me, render_plate
from .store import LocalStore, R2Store

SETTINGS = Path(__file__).resolve().parents[1] / "settings.toml"


def log(msg: str) -> None:
    print(f"[studio] {msg}", flush=True)


def png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def fetch_ics(path: str | None) -> bytes:
    if path:
        return Path(path).read_bytes()
    url = os.environ.get("ICAL_URL")
    if not url:
        sys.exit("No --ics file and no ICAL_URL set")
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def render(store, settings: dict, ics: bytes, today: date) -> None:
    tz = ZoneInfo(settings["home_time_zone"])
    L = Layout.from_settings(settings)
    days = settings["days_ahead"]
    events = parse_events(ics, today, today + timedelta(days=days + 400), tz)
    log(f"{len(events)} upcoming Event occurrences in the next {days + 400} days")

    battery = json.loads(store.get("state/battery.json") or b"{}")
    low = battery.get("percent", 100) <= settings["battery"]["low_percent"]
    if low:
        log("battery reported low: adding the Low Battery Mark")

    art_cfg = settings["artwork"]
    cache = {}
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "plates": []}
    for i in range(days):
        day = today + timedelta(days=i)
        plan = plan_day(events, day)
        if plan.idle:
            art = cache.setdefault("idle", artwork.idle_artwork(store))
        else:
            ev = plan.featured[0]
            if ev.artwork_key not in cache:
                cache[ev.artwork_key] = artwork.artwork_for(
                    ev, store, art_cfg["model"], art_cfg["monthly_generation_cap"], today, log)
            art = cache[ev.artwork_key]
        offline = i + 1 >= settings["offline_mark_from_day"]
        data = png_bytes(render_plate(plan, art, L, low_battery=low, offline=offline))
        name = f"{day.isoformat()}.png"
        store.put(f"plates/{name}", data, "image/png")
        manifest["plates"].append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})

    data = png_bytes(render_charge_me(L))
    store.put("plates/charge-me.png", data, "image/png")
    manifest["charge_me"] = {"file": "charge-me.png", "sha256": hashlib.sha256(data).hexdigest()}

    keep = {f"plates/{p['file']}" for p in manifest["plates"]} | {"plates/charge-me.png", "plates/manifest.json", "plates/manifest.txt"}
    stale = [k for k in store.list("plates/") if k not in keep]
    for k in stale:
        store.delete(k)
    store.put("plates/manifest.json", json.dumps(manifest, indent=1).encode(), "application/json")
    # The same list for the Frame, whose shell has no JSON tools: sha256sum format.
    files = manifest["plates"] + [manifest["charge_me"]]
    store.put("plates/manifest.txt", "".join(f"{p['sha256']}  {p['file']}\n" for p in files).encode(), "text/plain")
    idle_days = sum(1 for i in range(days) if plan_day(events, today + timedelta(days=i)).idle)
    log(f"rendered {days} Plates ({idle_days} Idle) and the Charge Me Plate; removed {len(stale)} stale")


def main() -> None:
    ap = argparse.ArgumentParser(prog="almost_studio")
    ap.add_argument("command", choices=["render", "make-library"])
    ap.add_argument("keywords", nargs="*")
    ap.add_argument("--local", type=Path, help="use a local folder instead of R2")
    ap.add_argument("--ics", help="read the Event Calendar from a file")
    ap.add_argument("--today", type=date.fromisoformat)
    args = ap.parse_args()

    settings = tomllib.loads(SETTINGS.read_text())
    store = LocalStore(args.local) if args.local else R2Store()
    if args.command == "make-library":
        artwork.make_library(store, settings["artwork"]["model"], log, args.keywords or None)
        return
    today = args.today or datetime.now(ZoneInfo(settings["home_time_zone"])).date()
    render(store, settings, fetch_ics(args.ics), today)


if __name__ == "__main__":
    main()
