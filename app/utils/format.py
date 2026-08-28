from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
WEEKDAY_FULL = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

MONTH_NAMES = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def master_tz(master: object) -> ZoneInfo:
    try:
        return ZoneInfo(getattr(master, "timezone", "Europe/Moscow"))
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def now_in_tz(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def format_price(price: Decimal) -> str:
    quantized = price.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral_value():
        return f"{int(quantized)} ₽"
    return f"{quantized} ₽"


def parse_price(raw: str) -> Decimal:
    text = raw.strip().replace(" ", "").replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Некорректная цена") from exc
    if value <= 0:
        raise ValueError("Цена должна быть больше нуля")
    return value.quantize(Decimal("0.01"))


def parse_duration(raw: str) -> int:
    minutes = int(raw.strip())
    if minutes <= 0 or minutes > 24 * 60:
        raise ValueError("Некорректная длительность")
    return minutes


def parse_hhmm(raw: str) -> time:
    parts = raw.strip().replace(".", ":").split(":")
    if len(parts) != 2:
        raise ValueError("Введите время как ЧЧ:ММ")
    hour, minute = int(parts[0]), int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Некорректное время")
    return time(hour, minute)


def format_date_ru(day) -> str:
    weekday = WEEKDAY_NAMES[day.weekday()]
    return f"{weekday} {day.day} {MONTH_NAMES[day.month]}"


def format_time(value: time | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    return value.strftime("%H:%M")


def encode_slot_callback(value: time | datetime) -> str:
    """Callback-safe HHMM without ':' (Telegram CallbackData separator)."""
    return format_time(value).replace(":", "")


def decode_slot_callback(raw: str) -> str:
    """Convert callback HHMM back to display form HH:MM."""
    text = raw.strip()
    if len(text) == 4 and text.isdigit():
        return f"{text[:2]}:{text[2:]}"
    raise ValueError("Некорректное время слота")


def format_dt_local(value: datetime, tz: ZoneInfo) -> str:
    local = value.astimezone(tz)
    return f"{format_date_ru(local.date())} {local.strftime('%H:%M')}"
