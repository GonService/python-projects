"""Slot calculation: which start times are free for a service on a given day.

Pure functions with no database access, so the rules are easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    available: bool
    reason: str = ""  # "past" or "taken" when not available


def overlaps(a: Interval, b: Interval) -> bool:
    """Half-open intervals: a booking ending at 10:00 does not clash with one starting at 10:00."""
    return a[0] < b[1] and b[0] < a[1]


def day_slots(
    day: date,
    duration_minutes: int,
    opening: list[tuple[time, time]],
    busy: list[Interval],
    now: datetime,
    step_minutes: int = 30,
) -> list[Slot]:
    """Every candidate start time inside the opening hours, flagged as available or not.

    A slot fits only if the whole service ends before the opening range closes, starts after
    `now`, and does not overlap any confirmed booking.
    """
    if duration_minutes <= 0 or step_minutes <= 0:
        raise ValueError("duration and step must be positive")
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=step_minutes)
    slots: list[Slot] = []
    for opens, closes in sorted(opening):
        start = datetime.combine(day, opens)
        end_of_range = datetime.combine(day, closes)
        while start + duration <= end_of_range:
            interval = (start, start + duration)
            if start <= now:
                slots.append(Slot(start, interval[1], False, "past"))
            elif any(overlaps(interval, b) for b in busy):
                slots.append(Slot(start, interval[1], False, "taken"))
            else:
                slots.append(Slot(start, interval[1], True))
            start += step
    return slots


def available_starts(*args, **kwargs) -> list[datetime]:
    return [s.start for s in day_slots(*args, **kwargs) if s.available]
