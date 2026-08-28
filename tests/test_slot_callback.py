from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.keyboards.booking import SlotCallback, slots_keyboard
from app.utils.format import decode_slot_callback, encode_slot_callback


def test_encode_slot_callback_has_no_colon():
    assert encode_slot_callback(time(10, 0)) == "1000"
    assert encode_slot_callback(time(9, 30)) == "0930"
    assert ":" not in encode_slot_callback(time(18, 0))


def test_decode_slot_callback_restores_display_time():
    assert decode_slot_callback("1000") == "10:00"
    assert decode_slot_callback("0930") == "09:30"


def test_slot_callback_pack_unpack_roundtrip():
    packed = SlotCallback(hhmm=encode_slot_callback(time(10, 0))).pack()
    assert packed == "slot:1000"
    parsed = SlotCallback.unpack(packed)
    assert parsed.hhmm == "1000"
    assert decode_slot_callback(parsed.hhmm) == "10:00"


def test_slots_keyboard_uses_safe_callback_and_shows_colon():
    tz = ZoneInfo("Europe/Moscow")
    slot = datetime(2026, 8, 24, 10, 0, tzinfo=tz)
    markup = slots_keyboard([slot])
    button = markup.inline_keyboard[0][0]
    assert button.text == "10:00"
    assert "10:00" not in (button.callback_data or "")
    parsed = SlotCallback.unpack(button.callback_data or "")
    assert parsed.hhmm == "1000"
    assert decode_slot_callback(parsed.hhmm) == "10:00"
