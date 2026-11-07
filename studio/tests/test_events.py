from datetime import date
from zoneinfo import ZoneInfo

from almost_studio.events import art_hint, parse_events, plan_day

MEL = ZoneInfo("Australia/Melbourne")

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:cruise
SUMMARY:40th Birthday Cruise
DTSTART;VALUE=DATE:20270128
DTEND;VALUE=DATE:20270204
DESCRIPTION:Can't wait!\\n<b>art:</b> ocean liner, waves, gulls
END:VEVENT
BEGIN:VEVENT
UID:bins
SUMMARY:Bin night
DTSTART;VALUE=DATE:20261103
RRULE:FREQ=WEEKLY
END:VEVENT
BEGIN:VEVENT
UID:mum
SUMMARY:Mum's birthday
DTSTART;VALUE=DATE:19600303
RRULE:FREQ=YEARLY
END:VEVENT
BEGIN:VEVENT
UID:flight
SUMMARY:Flight
DTSTART:20261130T224000Z
DTEND:20261201T010000Z
END:VEVENT
BEGIN:VEVENT
UID:party
SUMMARY:Sam's party
DTSTART;VALUE=DATE:20270128
END:VEVENT
END:VCALENDAR
"""


def events():
    return parse_events(ICS, date(2026, 11, 7), date(2028, 1, 1), MEL)


def test_weekly_repeats_are_ignored_but_yearly_repeat():
    names = [e.name for e in events()]
    assert "Bin night" not in names
    assert names.count("Mum's birthday") == 1  # 3 Mar 2027 only, within the window
    assert date(2027, 3, 3) in [e.day for e in events() if e.name == "Mum's birthday"]


def test_timed_entries_count_by_their_melbourne_date():
    flight = next(e for e in events() if e.name == "Flight")
    assert flight.day == date(2026, 12, 1)  # 22:40 UTC on 30 Nov is 09:40 on 1 Dec in Melbourne


def test_multi_day_entry_counts_to_its_first_day_only():
    assert [e.day for e in events() if e.name == "40th Birthday Cruise"] == [date(2027, 1, 28)]
    plan = plan_day(events(), date(2027, 1, 29))
    assert plan.featured[0].name == "Mum's birthday"  # the cruise is over as far as the Frame cares


def test_art_hint_found_even_through_html():
    cruise = next(e for e in events() if e.name == "40th Birthday Cruise")
    assert cruise.art_hint == "ocean liner, waves, gulls"
    assert art_hint("nothing here") == ""


def test_featured_is_next_upcoming_and_up_next_follows():
    plan = plan_day(events(), date(2026, 11, 7))
    assert [e.name for e in plan.featured] == ["Flight"]
    assert plan.days_left == 24
    assert {e.name for e in plan.up_next} == {"40th Birthday Cruise", "Sam's party"}


def test_same_day_events_are_featured_together():
    plan = plan_day(events(), date(2027, 1, 28))
    assert plan.days_left == 0
    assert plan.title == "40th Birthday Cruise & Sam's party"


def test_idle_when_nothing_upcoming():
    assert plan_day([], date(2026, 11, 7)).idle


def test_artwork_key_ignores_date_so_recurring_events_reuse_artwork():
    mums = [e for e in parse_events(ICS, date(2026, 11, 7), date(2029, 1, 1), MEL) if e.name == "Mum's birthday"]
    assert len(mums) == 2 and mums[0].artwork_key == mums[1].artwork_key
