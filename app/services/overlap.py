from __future__ import annotations

from datetime import datetime, timedelta


def ranges_overlap(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    """Half-open intervals [start, end). Adjacent ranges do not overlap."""
    return start_a < end_b and start_b < end_a


def slot_fits_workday(
    slot_start: datetime,
    duration: timedelta,
    work_start: datetime,
    work_end: datetime,
) -> bool:
    slot_end = slot_start + duration
    return slot_start >= work_start and slot_end <= work_end
