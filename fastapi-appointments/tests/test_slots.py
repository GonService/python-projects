from datetime import date, datetime, time

import pytest

from app.slots import available_starts, day_slots, overlaps

DAY = date(2026, 3, 3)  # a Tuesday
MORNING_AND_AFTERNOON = [(time(13), time(18)), (time(8), time(12))]
YESTERDAY = datetime(2026, 3, 2, 12, 0)


def at(hhmm: str) -> datetime:
    return datetime.combine(DAY, time.fromisoformat(hhmm))


def test_overlaps_uses_half_open_intervals():
    assert overlaps((at("09:00"), at("10:00")), (at("09:30"), at("10:30")))
    assert not overlaps((at("09:00"), at("10:00")), (at("10:00"), at("11:00")))


def test_slots_fit_inside_each_opening_range_and_respect_lunch_break():
    starts = available_starts(DAY, 50, MORNING_AND_AFTERNOON, [], YESTERDAY)
    hhmm = [s.strftime("%H:%M") for s in starts]
    assert hhmm[0] == "08:00"
    assert "11:00" in hhmm and "11:30" not in hhmm  # 11:30 + 50 min would end after 12:00
    assert "12:00" not in hhmm and "12:30" not in hhmm
    assert hhmm[-1] == "17:00"


def test_busy_interval_blocks_every_overlapping_start():
    busy = [(at("09:00"), at("10:00"))]
    slots = {s.start.strftime("%H:%M"): s for s in day_slots(DAY, 60, [(time(8), time(12))], busy, YESTERDAY)}
    assert slots["08:00"].available  # ends exactly when the booking starts
    assert not slots["08:30"].available and slots["08:30"].reason == "taken"
    assert not slots["09:30"].available
    assert slots["10:00"].available


def test_past_slots_are_not_available():
    now = at("10:10")
    slots = day_slots(DAY, 30, [(time(8), time(12))], [], now)
    assert [s.reason for s in slots if s.start <= now] == ["past"] * 5
    assert next(s for s in slots if s.available).start == at("10:30")


def test_closed_day_has_no_slots():
    assert day_slots(DAY, 30, [], [], YESTERDAY) == []


def test_invalid_duration():
    with pytest.raises(ValueError):
        day_slots(DAY, 0, MORNING_AND_AFTERNOON, [], YESTERDAY)
