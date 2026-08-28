from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Service
from app.utils.format import encode_slot_callback, format_date_ru, format_price, format_time


class ServiceCallback(CallbackData, prefix="svc"):
    service_id: int


class DateCallback(CallbackData, prefix="dt"):
    day: str


class SlotCallback(CallbackData, prefix="slot"):
    hhmm: str


class ConfirmCallback(CallbackData, prefix="cf"):
    action: str


class MyBookingCallback(CallbackData, prefix="mb"):
    booking_id: int
    action: str


def services_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in services:
        builder.row(
            InlineKeyboardButton(
                text=f"💅 {service.name} · {format_price(service.price)} · {service.duration_minutes} мин",
                callback_data=ServiceCallback(service_id=service.id).pack(),
            )
        )
    builder.row(InlineKeyboardButton(text="↩️ В меню", callback_data="client:home"))
    return builder.as_markup()


def dates_keyboard(days: list[date]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for day in days:
        builder.row(
            InlineKeyboardButton(
                text=format_date_ru(day),
                callback_data=DateCallback(day=day.isoformat()).pack(),
            )
        )
    builder.row(InlineKeyboardButton(text="↩️ К услугам", callback_data="book:services"))
    return builder.as_markup()


def slots_keyboard(slots: list[datetime]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row: list[InlineKeyboardButton] = []
    for slot in slots:
        row.append(
            InlineKeyboardButton(
                text=format_time(slot),
                callback_data=SlotCallback(hhmm=encode_slot_callback(slot)).pack(),
            )
        )
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="↩️ К датам", callback_data="book:dates"))
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=ConfirmCallback(action="yes").pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=ConfirmCallback(action="no").pack(),
                ),
            ]
        ]
    )


def my_bookings_keyboard(bookings: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for booking in bookings:
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=MyBookingCallback(booking_id=booking.id, action="cancel").pack(),
            )
        )
    return builder.as_markup()


def cancel_one_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=MyBookingCallback(booking_id=booking_id, action="cancel").pack(),
                )
            ]
        ]
    )
