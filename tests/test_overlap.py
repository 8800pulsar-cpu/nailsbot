from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.overlap import ranges_overlap

TZ = ZoneInfo("Europe/Moscow")


def _at(hour: int) -> datetime:
    return datetime(2026, 8, 24, hour, 0, tzinfo=TZ)


def test_overlapping_ranges_detected():
    assert ranges_overlap(_at(12), _at(14), _at(13), _at(15))
    assert ranges_overlap(_at(13), _at(15), _at(12), _at(14))
    assert ranges_overlap(_at(12), _at(14), _at(12), _at(14))


def test_adjacent_ranges_do_not_overlap():
    assert not ranges_overlap(_at(12), _at(14), _at(14), _at(16))
    assert not ranges_overlap(_at(14), _at(16), _at(12), _at(14))


def test_separate_ranges_do_not_overlap():
    assert not ranges_overlap(_at(10), _at(11), _at(12), _at(13))
