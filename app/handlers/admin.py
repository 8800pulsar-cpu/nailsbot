from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Master
from app.keyboards.admin import (
    AdminClientCB,
    AdminClosedCB,
    AdminMenu,
    AdminServiceCB,
    AdminSettingCB,
    AdminWeekdayCB,
    admin_menu,
    back_to_admin,
    clients_keyboard,
    closed_date_item_keyboard,
    closed_dates_keyboard,
    schedule_keyboard,
    service_edit_keyboard,
    services_admin_keyboard,
    settings_keyboard,
    weekday_edit_keyboard,
)
from app.repositories.bookings import BookingRepository
from app.repositories.schedules import ClosedDateRepository, ScheduleRepository
from app.repositories.services import ServiceRepository
from app.repositories.users import UserRepository
from app.services.booking_service import format_booking_card
from app.services.client_service import ClientService
from app.services.master_service import MasterService
from app.states.admin import (
    AdminClosedAdd,
    AdminMasterEdit,
    AdminScheduleEdit,
    AdminServiceAdd,
    AdminServiceEdit,
)
from app.utils.format import (
    WEEKDAY_FULL,
    format_price,
    format_time,
    master_tz,
    now_in_tz,
    parse_duration,
    parse_hhmm,
    parse_price,
)

logger = logging.getLogger(__name__)
router = Router(name="admin")


class AdminOnly(BaseFilter):
    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id == settings.admin_id


router.message.filter(AdminOnly())
router.callback_query.filter(AdminOnly())


def _admin_text() -> str:
    return "Админ-панель. Выберите раздел:"


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, master: Master | None) -> None:
    await state.clear()
    if master is None:
        await message.answer(
            "Мастер ещё не создан. На сервере выполните:\n"
            "python -m app.bootstrap"
        )
        return
    await message.answer(_admin_text(), reply_markup=admin_menu())


@router.callback_query(AdminMenu.filter(F.action == "home"))
async def admin_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer(_admin_text(), reply_markup=admin_menu())


def _booking_admin_line(booking, tz) -> str:
    local = booking.start_time.astimezone(tz)
    user = booking.user
    name = user.first_name if user and user.first_name else "Клиент"
    username = f" @{user.username}" if user and user.username else ""
    service_name = booking.service.name if booking.service else "услуга"
    return f"{local.strftime('%d.%m %H:%M')} — {name}{username} — {service_name}"


@router.callback_query(AdminMenu.filter(F.action == "today"))
async def bookings_today(
    callback: CallbackQuery,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    tz = master_tz(master)
    today = now_in_tz(tz).date()
    start = datetime.combine(today, time.min, tzinfo=tz)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz)
    rows = await BookingRepository(session).list_for_day(master.id, start, end)
    if not rows:
        await callback.message.answer("На сегодня записей нет.", reply_markup=back_to_admin())
        return
    lines = ["Записи на сегодня:\n"] + [_booking_admin_line(item, tz) for item in rows]
    await callback.message.answer("\n".join(lines), reply_markup=back_to_admin())


@router.callback_query(AdminMenu.filter(F.action == "upcoming"))
async def bookings_upcoming(
    callback: CallbackQuery,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    tz = master_tz(master)
    rows = await BookingRepository(session).list_upcoming(master.id, now_in_tz(tz))
    if not rows:
        await callback.message.answer("Ближайших записей нет.", reply_markup=back_to_admin())
        return
    lines = ["Ближайшие записи:\n"] + [_booking_admin_line(item, tz) for item in rows]
    await callback.message.answer("\n".join(lines), reply_markup=back_to_admin())


@router.callback_query(AdminMenu.filter(F.action == "services"))
async def admin_services(
    callback: CallbackQuery,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    services = await ServiceRepository(session).list_by_master(master.id)
    await callback.message.answer(
        "Услуги. Неактивные скрыты от клиентов, но остаются в истории записей.",
        reply_markup=services_admin_keyboard(services),
    )


@router.callback_query(AdminMenu.filter(F.action == "service_add"))
async def service_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminServiceAdd.name)
    if callback.message:
        await callback.message.answer("Введите название услуги. /cancel для отмены.")


@router.message(AdminServiceAdd.name)
async def service_add_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не должно быть пустым.")
        return
    await state.update_data(name=name)
    await state.set_state(AdminServiceAdd.duration)
    await message.answer("Длительность в минутах, например 60.")


@router.message(AdminServiceAdd.duration)
async def service_add_duration(message: Message, state: FSMContext) -> None:
    try:
        duration = parse_duration(message.text or "")
    except (ValueError, TypeError):
        await message.answer("Введите целое число минут, например 90.")
        return
    await state.update_data(duration=duration)
    await state.set_state(AdminServiceAdd.price)
    await message.answer("Цена в рублях, например 1500.")


@router.message(AdminServiceAdd.price)
async def service_add_price(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    if master is None:
        await message.answer("Мастер не настроен.")
        return
    try:
        price = parse_price(message.text or "")
    except ValueError:
        await message.answer("Введите цену числом, например 1500 или 1500.50.")
        return
    data = await state.get_data()
    service = await ServiceRepository(session).create(
        master_id=master.id,
        name=data["name"],
        duration_minutes=data["duration"],
        price=price,
    )
    await state.clear()
    await message.answer(
        f"Услуга добавлена: {service.name}, {format_price(service.price)}, "
        f"{service.duration_minutes} мин.",
        reply_markup=admin_menu(),
    )


@router.callback_query(AdminServiceCB.filter(F.action == "view"))
async def service_view(
    callback: CallbackQuery,
    callback_data: AdminServiceCB,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    service = await ServiceRepository(session).get_for_master(callback_data.service_id, master.id)
    if service is None:
        await callback.message.answer("Услуга не найдена.")
        return
    status = "активна" if service.is_active else "отключена"
    await callback.message.answer(
        f"{service.name}\n"
        f"{format_price(service.price)} · {service.duration_minutes} мин\n"
        f"Статус: {status}",
        reply_markup=service_edit_keyboard(service),
    )


@router.callback_query(AdminServiceCB.filter(F.action.in_({"name", "price", "duration"})))
async def service_edit_start(
    callback: CallbackQuery,
    callback_data: AdminServiceCB,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.set_state(AdminServiceEdit.waiting_value)
    await state.update_data(service_id=callback_data.service_id, field=callback_data.action)
    prompts = {
        "name": "Новое название:",
        "price": "Новая цена в рублях:",
        "duration": "Новая длительность в минутах:",
    }
    if callback.message:
        await callback.message.answer(prompts[callback_data.action])


@router.message(AdminServiceEdit.waiting_value)
async def service_edit_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    if master is None:
        return
    data = await state.get_data()
    repo = ServiceRepository(session)
    service = await repo.get_for_master(data["service_id"], master.id)
    if service is None:
        await state.clear()
        await message.answer("Услуга не найдена.", reply_markup=admin_menu())
        return
    field = data["field"]
    raw = message.text or ""
    try:
        if field == "name":
            name = raw.strip()
            if not name:
                raise ValueError
            service.name = name
        elif field == "price":
            service.price = parse_price(raw)
        else:
            service.duration_minutes = parse_duration(raw)
    except (ValueError, TypeError):
        await message.answer("Некорректное значение, попробуйте ещё раз.")
        return
    await repo.save(service)
    await state.clear()
    await message.answer("Услуга обновлена.", reply_markup=service_edit_keyboard(service))


@router.callback_query(AdminServiceCB.filter(F.action == "toggle"))
async def service_toggle(
    callback: CallbackQuery,
    callback_data: AdminServiceCB,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    repo = ServiceRepository(session)
    service = await repo.get_for_master(callback_data.service_id, master.id)
    if service is None:
        return
    service.is_active = not service.is_active
    await repo.save(service)
    status = "включена" if service.is_active else "отключена"
    await callback.message.answer(
        f"Услуга {status}.",
        reply_markup=service_edit_keyboard(service),
    )


@router.callback_query(AdminMenu.filter(F.action == "schedule"))
async def admin_schedule(
    callback: CallbackQuery,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    rows = await ScheduleRepository(session).ensure_week(master.id)
    await callback.message.answer("Расписание по дням недели:", reply_markup=schedule_keyboard(rows))


@router.callback_query(AdminWeekdayCB.filter())
async def weekday_selected(
    callback: CallbackQuery,
    callback_data: AdminWeekdayCB,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(weekday=callback_data.weekday)
    if callback.message:
        await callback.message.answer(
            f"{WEEKDAY_FULL[callback_data.weekday]}. Рабочий день или выходной?",
            reply_markup=weekday_edit_keyboard(callback_data.weekday),
        )


@router.callback_query(F.data.startswith("awork:"))
async def weekday_working(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    _, weekday_raw, flag = callback.data.split(":")
    weekday = int(weekday_raw)
    repo = ScheduleRepository(session)
    if flag == "off":
        current = await repo.get_weekday(master.id, weekday)
        start = current.start_time if current else time(10, 0)
        end = current.end_time if current else time(20, 0)
        await repo.upsert_weekday(
            master_id=master.id,
            weekday=weekday,
            start_time=start,
            end_time=end,
            is_working=False,
        )
        await state.clear()
        rows = await repo.list_for_master(master.id)
        await callback.message.answer("День отмечен как выходной.", reply_markup=schedule_keyboard(rows))
        return
    await state.set_state(AdminScheduleEdit.waiting_hours)
    await state.update_data(weekday=weekday)
    await callback.message.answer("Введите рабочие часы как 10:00-20:00")


@router.message(AdminScheduleEdit.waiting_hours)
async def weekday_hours(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    if master is None:
        return
    raw = (message.text or "").replace("–", "-").replace("—", "-")
    parts = raw.split("-")
    if len(parts) != 2:
        await message.answer("Формат: 10:00-20:00")
        return
    try:
        start = parse_hhmm(parts[0])
        end = parse_hhmm(parts[1])
    except ValueError:
        await message.answer("Некорректное время. Пример: 10:00-20:00")
        return
    if start >= end:
        await message.answer("Время окончания должно быть позже начала.")
        return
    data = await state.get_data()
    repo = ScheduleRepository(session)
    await repo.upsert_weekday(
        master_id=master.id,
        weekday=int(data["weekday"]),
        start_time=start,
        end_time=end,
        is_working=True,
    )
    await state.clear()
    rows = await repo.list_for_master(master.id)
    await message.answer("Расписание обновлено.", reply_markup=schedule_keyboard(rows))


@router.callback_query(AdminMenu.filter(F.action == "closed"))
async def admin_closed(
    callback: CallbackQuery,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    tz = master_tz(master)
    rows = await ClosedDateRepository(session).list_for_master(master.id, now_in_tz(tz).date())
    await callback.message.answer(
        "Закрытые даты. Клиенты не смогут записаться на эти дни.",
        reply_markup=closed_dates_keyboard(rows),
    )


@router.callback_query(AdminMenu.filter(F.action == "closed_add"))
async def closed_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminClosedAdd.waiting_date)
    if callback.message:
        await callback.message.answer("Введите дату как ДД.ММ.ГГГГ, например 30.08.2026")


@router.message(AdminClosedAdd.waiting_date)
async def closed_add_date(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        day = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Некорректная дата. Пример: 30.08.2026")
        return
    await state.update_data(day=day.isoformat())
    await state.set_state(AdminClosedAdd.waiting_reason)
    await message.answer("Причина (или «-», если без причины):")


@router.message(AdminClosedAdd.waiting_reason)
async def closed_add_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
) -> None:
    if master is None:
        return
    data = await state.get_data()
    day = date.fromisoformat(data["day"])
    reason_raw = (message.text or "").strip()
    reason = None if reason_raw in {"-", "нет", ""} else reason_raw
    repo = ClosedDateRepository(session)
    if await repo.get_on_date(master.id, day):
        await state.clear()
        await message.answer("Эта дата уже закрыта.", reply_markup=admin_menu())
        return
    await repo.add(master_id=master.id, day=day, reason=reason)
    await state.clear()
    rows = await repo.list_for_master(master.id)
    await message.answer("Дата закрыта.", reply_markup=closed_dates_keyboard(rows))


@router.callback_query(AdminClosedCB.filter(F.action == "view"))
async def closed_view(
    callback: CallbackQuery,
    callback_data: AdminClosedCB,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    repo = ClosedDateRepository(session)
    rows = await repo.list_for_master(master.id)
    item = next((row for row in rows if row.id == callback_data.closed_id), None)
    if item is None:
        await callback.message.answer("Дата не найдена.", reply_markup=back_to_admin())
        return
    reason = item.reason or "без причины"
    await callback.message.answer(
        f"{item.date.strftime('%d.%m.%Y')} — {reason}",
        reply_markup=closed_date_item_keyboard(item.id),
    )


@router.callback_query(AdminClosedCB.filter(F.action == "delete"))
async def closed_delete(
    callback: CallbackQuery,
    callback_data: AdminClosedCB,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    repo = ClosedDateRepository(session)
    rows = await repo.list_for_master(master.id)
    item = next((row for row in rows if row.id == callback_data.closed_id), None)
    if item is None:
        await callback.message.answer("Дата не найдена.")
        return
    await repo.delete(item)
    rows = await repo.list_for_master(master.id)
    await callback.message.answer("Закрытая дата удалена.", reply_markup=closed_dates_keyboard(rows))


@router.callback_query(AdminMenu.filter(F.action == "clients"))
async def admin_clients(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    await callback.answer()
    if callback.message is None:
        return
    users = await ClientService(session).list_clients()
    if not users:
        await callback.message.answer("Клиентов пока нет.", reply_markup=back_to_admin())
        return
    await callback.message.answer("Клиенты:", reply_markup=clients_keyboard(users))


@router.callback_query(AdminClientCB.filter())
async def admin_client_history(
    callback: CallbackQuery,
    callback_data: AdminClientCB,
    session: AsyncSession,
    master: Master | None,
) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    user = await UserRepository(session).get_by_id(callback_data.user_id)
    if user is None:
        await callback.message.answer("Клиент не найден.")
        return
    tz = master_tz(master)
    bookings = await BookingRepository(session).list_user_history(user.id, master.id)
    username = f"@{user.username}" if user.username else "нет"
    header = (
        f"{user.first_name or 'Без имени'}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"username: {username}\n"
        f"Первый визит: {user.created_at.astimezone(tz).strftime('%d.%m.%Y')}\n"
    )
    if not bookings:
        await callback.message.answer(header + "\nЗаписей нет.", reply_markup=back_to_admin())
        return
    lines = [header, "История записей:"]
    for booking in bookings:
        local = booking.start_time.astimezone(tz)
        service_name = booking.service.name if booking.service else "услуга"
        lines.append(
            f"{local.strftime('%d.%m.%Y %H:%M')} — {service_name} — {booking.status}"
        )
    await callback.message.answer("\n".join(lines), reply_markup=back_to_admin())


@router.callback_query(AdminMenu.filter(F.action == "settings"))
async def admin_settings(callback: CallbackQuery, master: Master | None) -> None:
    await callback.answer()
    if master is None or callback.message is None:
        return
    text = (
        f"Имя: {master.name}\n"
        f"Описание: {master.description}\n"
        f"Контакт: {master.contact}\n"
        f"Адрес: {master.address}\n"
        f"Часовой пояс: {master.timezone}"
    )
    await callback.message.answer(text, reply_markup=settings_keyboard())


@router.callback_query(AdminSettingCB.filter())
async def setting_start(
    callback: CallbackQuery,
    callback_data: AdminSettingCB,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.set_state(AdminMasterEdit.waiting_value)
    await state.update_data(field=callback_data.field)
    prompts = {
        "name": "Новое имя мастера:",
        "description": "Новое описание:",
        "contact": "Новый контакт (телефон или Telegram):",
        "address": "Новый адрес:",
        "timezone": "Часовой пояс, например Europe/Moscow:",
    }
    if callback.message:
        await callback.message.answer(prompts[callback_data.field])


@router.message(AdminMasterEdit.waiting_value)
async def setting_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    master: Master | None,
    settings: Settings,
) -> None:
    if master is None:
        return
    data = await state.get_data()
    value = (message.text or "").strip()
    if not value:
        await message.answer("Значение не должно быть пустым.")
        return
    field = data["field"]
    if field == "timezone":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            await message.answer("Некорректный часовой пояс. Пример: Europe/Moscow")
            return
    await MasterService(session, settings).update(master, **{field: value})
    await state.clear()
    await message.answer("Настройки обновлены.", reply_markup=settings_keyboard())
