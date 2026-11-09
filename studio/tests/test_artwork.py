from datetime import date

from almost_studio.artwork import HOUSE_STYLES, STYLE_WORDS, house_style, requested_style
from almost_studio.events import Event, style_request


def test_style_request_found_even_through_html():
    assert style_request("Fun!\n<b>style:</b> Japanese woodblock") == "Japanese woodblock"
    assert style_request("art: cake") == ""


def test_style_request_names_a_house_style_loosely():
    assert requested_style("Sumi-e") == "sumie"
    assert requested_style("ink and wash") == "sumie"
    assert requested_style("Art Deco") == "deco"
    assert requested_style("watercolour") is None
    assert requested_style("") is None


def test_every_house_style_can_be_requested():
    assert set(STYLE_WORDS) == set(HOUSE_STYLES)


def test_requested_style_wins_and_unknown_falls_back_to_the_pick():
    plain = Event("Christmas Day", date(2026, 12, 25), "tree")
    assert house_style(Event("Christmas Day", date(2026, 12, 25), "tree", "deco")) == "deco"
    unknown = Event("Christmas Day", date(2026, 12, 25), "tree", "watercolour")
    assert house_style(unknown) in HOUSE_STYLES
    assert house_style(plain) in HOUSE_STYLES


def test_style_request_changes_the_artwork_key_only_when_set():
    plain = Event("Christmas Day", date(2026, 12, 25), "tree")
    blank = Event("Christmas Day", date(2026, 12, 25), "tree", "  ")
    styled = Event("Christmas Day", date(2026, 12, 25), "tree", "sumi-e")
    assert plain.artwork_key == blank.artwork_key != styled.artwork_key
