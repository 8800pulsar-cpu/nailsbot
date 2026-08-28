from __future__ import annotations

import logging
from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Master
from app.handlers.client import need_master
from app.keyboards.booking import (
    ConfirmCallback,
    DateCallback,
    ServiceCallback,
    SlotCallback,
    confirm_keyboard,
    dates_keyboard,
    services_keyboard,
    slots_keyboard,
)
from app.keyboards.client import main_menu
from app.services.booking_service import (
    BookingService,
    InactiveServiceError,
    SlotUnavailableError,
    format_booking_card,
)
from app.services.client_service import ClientService
from app.states.booking import BookingStates
from app.utils.format import decode_slot_callback, format_price, master_tz

logger = logging.getLogger(__name__)
router = Router(name="booking")


@router.message(F.text == "💅 Записаться")
async def start_booking(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    error = need_master(master)
    if error or master is None:
        await message.answer(error or "Произошла ошибка. Попробуйте ещё раз.")
        return
    if message.from_user:
        await ClientService(session).ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    await _send_services(message, state, session, master)


@router.callback_query(F.data == "book:services")
async def back_to_services(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    await _send_services(callback.message, state, session, master)


async def _send_services(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master,
) -> None:
    services = await BookingService(session).list_client_services(master.id)
    if not services:
        await message.answer("Пока нет доступных услуг. Попробуйте позже.")
        await state.clear()
        return
    await state.set_state(BookingStates.choosing_service)
    lines = ["Выберите услугу:"]
    for service in services:
        lines.append(
            f"\n💅 {service.name}\n"
            f"{format_price(service.price)} · {service.duration_minutes} мин"
        )
    await message.answer("\n".join(lines), reply_markup=services_keyboard(services))


@router.callback_query(ServiceCallback.filter(), BookingStates.choosing_service)
async def choose_service(
    callback: CallbackQuery,
    callback_data: ServiceCallback,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    booking_service = BookingService(session)
    try:
        service = await booking_service.get_bookable_service(callback_data.service_id, master.id)
    except InactiveServiceError:
        await callback.message.answer("Эта услуга недоступна. Выберите другую.")
        return
    await state.update_data(service_id=service.id)
    await _send_dates(callback.message, state, booking_service, master, service)


@router.callback_query(F.data == "book:dates")
async def back_to_dates(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    data = await state.get_data()
    service_id = data.get("service_id")
    if service_id is None:
        await _send_services(callback.message, state, session, master)
        return
    booking_service = BookingService(session)
    try:
        service = await booking_service.get_bookable_service(service_id, master.id)
    except InactiveServiceError:
        await callback.message.answer("Услуга больше недоступна.")
        return
    await _send_dates(callback.message, state, booking_service, master, service)


async def _send_dates(message, state, booking_service, master, service) -> None:
    days = await booking_service.list_available_dates(master, service)
    if not days:
        await message.answer("На ближайшие дни свободных слотов нет.")
        return
    await state.set_state(BookingStates.choosing_date)
    await message.answer("Выберите дату:", reply_markup=dates_keyboard(days))


@router.callback_query(DateCallback.filter(), BookingStates.choosing_date)
async def choose_date(
    callback: CallbackQuery,
    callback_data: DateCallback,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    day = date.fromisoformat(callback_data.day)
    data = await state.get_data()
    booking_service = BookingService(session)
    try:
        service = await booking_service.get_bookable_service(data["service_id"], master.id)
    except (InactiveServiceError, KeyError):
        await callback.message.answer("Не удалось выбрать услугу. Начните запись заново.")
        await state.clear()
        return
    await state.update_data(day=day.isoformat())
    slots = await booking_service.list_available_slots(master, service, day)
    if not slots:
        await callback.message.answer("На эту дату свободного времени нет. Выберите другую.")
        return
    await state.set_state(BookingStates.choosing_time)
    await callback.message.answer("Выберите время:", reply_markup=slots_keyboard(slots))


@router.callback_query(SlotCallback.filter(), BookingStates.choosing_time)
async def choose_slot(
    callback: CallbackQuery,
    callback_data: SlotCallback,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    data = await state.get_data()
    booking_service = BookingService(session)
    try:
        service = await booking_service.get_bookable_service(data["service_id"], master.id)
        day = date.fromisoformat(data["day"])
    except (InactiveServiceError, KeyError, ValueError):
        await callback.message.answer("Данные записи устарели. Начните заново.")
        await state.clear()
        return
    try:
        hhmm = decode_slot_callback(callback_data.hhmm)
        hour, minute = map(int, hhmm.split(":"))
    except ValueError:
        await callback.message.answer("Данные записи устарели. Начните заново.")
        await state.clear()
        return
    tz = master_tz(master)
    start = datetime.combine(day, time(hour, minute), tzinfo=tz)
    slots = await booking_service.list_available_slots(master, service, day)
    if start not in slots:
        await callback.message.answer("Это время уже недоступно. Выберите другое.")
        return
    await state.update_data(hhmm=hhmm)
    await state.set_state(BookingStates.confirming)
    text = (
        "Проверьте запись:\n\n"
        f"💅 {service.name}\n"
        f"📅 {day.strftime('%d.%m.%Y')}\n"
        f"🕒 {hhmm}\n"
        f"💰 {format_price(service.price)}"
    )
    await callback.message.answer(text, reply_markup=confirm_keyboard())


@router.callback_query(ConfirmCallback.filter(), BookingStates.confirming)
async def confirm_booking(
    callback: CallbackQuery,
    callback_data: ConfirmCallback,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
    settings: Settings,
) -> None:
    await callback.answer()
    if callback.message is None:
        return
    if callback_data.action != "yes":
        await state.clear()
        await callback.message.answer("Запись отменена.", reply_markup=main_menu())
        return
    if master is None or callback.from_user is None:
        await callback.message.answer("Не удалось создать запись.")
        return

    data = await state.get_data()
    user = await ClientService(session).ensure_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    booking_service = BookingService(session)
    try:
        service = await booking_service.get_bookable_service(data["service_id"], master.id)
        day = date.fromisoformat(data["day"])
        hour, minute = map(int, data["hhmm"].split(":"))
        start = datetime.combine(day, time(hour, minute), tzinfo=master_tz(master))
        booking = await booking_service.create_booking(
            master=master,
            user_id=user.id,
            service_id=service.id,
            start_local=start,
        )
    except InactiveServiceError:
        await state.clear()
        await callback.message.answer("Услуга больше недоступна.")
        return
    except SlotUnavailableError:
        await state.clear()
        await callback.message.answer(
            "Это время только что заняли. Выберите другой слот.",
            reply_markup=main_menu(),
        )
        return
    except (KeyError, ValueError):
        await state.clear()
        await callback.message.answer("Данные записи устарели. Начните заново.")
        return

    await state.clear()
    tz = master_tz(master)
    await callback.message.answer(
        "Запись создана!\n\n" + format_booking_card(booking, tz),
        reply_markup=main_menu(),
    )
    username = f"@{callback.from_user.username}" if callback.from_user.username else "без username"
    client_name = callback.from_user.first_name or "Клиент"
    try:
        await callback.bot.send_message(
            settings.admin_id,
            "Новая запись\n\n"
            f"{format_booking_card(booking, tz)}\n"
            f"👤 {client_name} ({username})",
        )
    except Exception:
        logger.exception("Failed to notify admin about new booking")
