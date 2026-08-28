from __future__ import annotations

import logging
from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Master
from app.keyboards.booking import MyBookingCallback, cancel_one_keyboard
from app.keyboards.client import main_menu
from app.middlewares import MASTER_ERROR
from app.repositories.bookings import BookingRepository
from app.services.booking_service import BookingService, SlotUnavailableError, format_booking_card
from app.services.client_service import ClientService
from app.utils.format import master_tz, now_in_tz

logger = logging.getLogger(__name__)
router = Router(name="client")


def need_master(master: Master | None) -> str | None:
    if master is None:
        return MASTER_ERROR
    return None


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    master: Master | None,
) -> None:
    if message.from_user:
        await ClientService(session).ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    name = master.name if master else "мастеру"
    await message.answer(
        f"Здравствуйте! Это бот записи к мастеру: {name}.\n"
        "Выберите действие на клавиатуре.",
        reply_markup=main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())


@router.callback_query(F.data == "client:home")
async def callback_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer("Главное меню.", reply_markup=main_menu())


@router.message(F.text == "ℹ️ Информация")
async def show_info(message: Message, master: Master | None) -> None:
    error = need_master(master)
    if error or master is None:
        await message.answer(error or MASTER_ERROR)
        return
    text = (
        f"💅 {master.name}\n\n"
        f"{master.description}\n\n"
        f"📞 {master.contact}\n"
        f"📍 {master.address}"
    )
    await message.answer(text, reply_markup=main_menu())


@router.message(F.text == "📅 Моя запись")
async def my_bookings(
    message: Message,
    session: AsyncSession,
    master: Master | None,
) -> None:
    error = need_master(master)
    if error or master is None:
        await message.answer(error or MASTER_ERROR)
        return
    if message.from_user is None:
        return
    user = await ClientService(session).ensure_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    tz = master_tz(master)
    bookings = await BookingRepository(session).list_user_upcoming(
        user.id, master.id, now_in_tz(tz)
    )
    if not bookings:
        await message.answer("У вас нет активных записей.", reply_markup=main_menu())
        return
    for booking in bookings:
        await message.answer(
            format_booking_card(booking, tz),
            reply_markup=cancel_one_keyboard(booking.id),
        )


@router.callback_query(MyBookingCallback.filter(F.action == "cancel"))
async def cancel_my_booking(
    callback: CallbackQuery,
    callback_data: MyBookingCallback,
    session: AsyncSession,
    master: Master | None,
    settings: Settings,
) -> None:
    await callback.answer()
    if master is None or callback.from_user is None or callback.message is None:
        return
    user = await ClientService(session).ensure_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    repo = BookingRepository(session)
    booking = await repo.get_by_id(callback_data.booking_id)
    if booking is None:
        await callback.message.answer("Запись не найдена.")
        return
    try:
        await BookingService(session).cancel_booking(booking, master.id, user.id)
    except SlotUnavailableError:
        await callback.message.answer("Нельзя отменить эту запись.")
        return
    await callback.message.answer("Запись отменена. Слот снова свободен.", reply_markup=main_menu())
    try:
        await callback.bot.send_message(
            settings.admin_id,
            f"Клиент отменил запись #{booking.id}.",
        )
    except Exception:
        logger.exception("Failed to notify admin about cancellation")
