"""Events from the Event Calendar, and what each day's Plate is about."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

ART_HINT = re.compile(r"^\s*art\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Event:
    name: str
    day: date
    art_hint: str = ""

    @property
    def artwork_key(self) -> str:
        """Same title and Art Hint means the same Artwork, so a Recurring Event
        reuses it every year and editing the hint makes a new one."""
        raw = f"{self.name.strip().lower()}|{self.art_hint.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class DayPlan:
    """What the Plate for one day shows."""
    day: date
    featured: tuple[Event, ...]       # empty means Idle
    up_next: tuple[Event, ...] = ()

    @property
    def idle(self) -> bool:
        return not self.featured

    @property
    def days_left(self) -> int:
        return (self.featured[0].day - self.day).days

    @property
    def title(self) -> str:
        return " & ".join(e.name for e in self.featured)


def art_hint(description: str) -> str:
    m = ART_HINT.search(TAG.sub("\n", description or ""))
    return m.group(1) if m else ""


def _yearly_or_single(component) -> bool:
    rrule = component.get("RRULE")
    if rrule is None:
        return True
    return [f.upper() for f in rrule.get("FREQ", [])] == ["YEARLY"]


def _local_day(value, tz: ZoneInfo) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return value.astimezone(tz).date()
    return value


def parse_events(ics: bytes, start: date, end: date, tz: ZoneInfo) -> list[Event]:
    """Every Event occurring between start and end (inclusive), by its first day.

    Recurring entries count only if they repeat yearly; any other repeat
    pattern is ignored, so a careless weekly entry can't take over the Frame.
    """
    cal = icalendar.Calendar.from_ical(ics)
    for comp in list(cal.walk("VEVENT")):
        if not _yearly_or_single(comp):
            cal.subcomponents.remove(comp)
    occurrences = recurring_ical_events.of(cal).between(start, end + timedelta(days=1))
    events = set()
    for occ in occurrences:
        name = str(occ.get("SUMMARY", "")).strip()
        if not name:
            continue
        day = _local_day(occ.decoded("DTSTART"), tz)
        if start <= day <= end:
            events.add(Event(name, day, art_hint(str(occ.get("DESCRIPTION", "")))))
    return sorted(events, key=lambda e: (e.day, e.name.lower()))


def plan_day(events: list[Event], day: date) -> DayPlan:
    upcoming = [e for e in events if e.day >= day]
    if not upcoming:
        return DayPlan(day, ())
    first = upcoming[0].day
    featured = tuple(e for e in upcoming if e.day == first)
    later = [e for e in upcoming if e.day > first]
    up_next = tuple(e for e in later if e.day == later[0].day) if later else ()
    return DayPlan(day, featured, up_next)
