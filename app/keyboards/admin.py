from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import ClosedDate, Service, WorkingSchedule
from app.utils.format import WEEKDAY_NAMES, format_price, format_time


class AdminMenu(CallbackData, prefix="adm"):
    action: str


class AdminServiceCB(CallbackData, prefix="asvc"):
    service_id: int
    action: str


class AdminWeekdayCB(CallbackData, prefix="awd"):
    weekday: int


class AdminClosedCB(CallbackData, prefix="acd"):
    closed_id: int
    action: str


class AdminClientCB(CallbackData, prefix="acl"):
    user_id: int


class AdminSettingCB(CallbackData, prefix="aset"):
    field: str


def admin_menu() -> InlineKeyboardMarkup:
    items = [
        ("📅 Записи сегодня", "today"),
        ("📆 Ближайшие записи", "upcoming"),
        ("💅 Услуги", "services"),
        ("🕐 Расписание", "schedule"),
        ("🚫 Закрытые даты", "closed"),
        ("👥 Клиенты", "clients"),
        ("⚙️ Настройки мастера", "settings"),
    ]
    builder = InlineKeyboardBuilder()
    for text, action in items:
        builder.row(InlineKeyboardButton(text=text, callback_data=AdminMenu(action=action).pack()))
    return builder.as_markup()


def back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Админ-меню", callback_data=AdminMenu(action="home").pack())]
        ]
    )


def services_admin_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in services:
        status = "✅" if service.is_active else "🚫"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {service.name} · {format_price(service.price)} · {service.duration_minutes} мин",
                callback_data=AdminServiceCB(service_id=service.id, action="view").pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить услугу", callback_data=AdminMenu(action="service_add").pack())
    )
    builder.row(InlineKeyboardButton(text="↩️ Админ-меню", callback_data=AdminMenu(action="home").pack()))
    return builder.as_markup()


def service_edit_keyboard(service: Service) -> InlineKeyboardMarkup:
    toggle = "🚫 Отключить" if service.is_active else "✅ Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Название",
                    callback_data=AdminServiceCB(service_id=service.id, action="name").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Цена",
                    callback_data=AdminServiceCB(service_id=service.id, action="price").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏱ Длительность",
                    callback_data=AdminServiceCB(service_id=service.id, action="duration").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=toggle,
                    callback_data=AdminServiceCB(service_id=service.id, action="toggle").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ К услугам",
                    callback_data=AdminMenu(action="services").pack(),
                )
            ],
        ]
    )


def schedule_keyboard(rows: list[WorkingSchedule]) -> InlineKeyboardMarkup:
    by_day = {row.weekday: row for row in rows}
    builder = InlineKeyboardBuilder()
    for weekday in range(7):
        row = by_day.get(weekday)
        if row is None:
            label = f"{WEEKDAY_NAMES[weekday]} не задано"
        elif not row.is_working:
            label = f"{WEEKDAY_NAMES[weekday]} выходной"
        else:
            label = (
                f"{WEEKDAY_NAMES[weekday]} "
                f"{format_time(row.start_time)}–{format_time(row.end_time)}"
            )
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=AdminWeekdayCB(weekday=weekday).pack(),
            )
        )
    builder.row(InlineKeyboardButton(text="↩️ Админ-меню", callback_data=AdminMenu(action="home").pack()))
    return builder.as_markup()


def weekday_edit_keyboard(weekday: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Рабочий день",
                    callback_data=f"awork:{weekday}:on",
                ),
                InlineKeyboardButton(
                    text="Выходной",
                    callback_data=f"awork:{weekday}:off",
                ),
            ],
            [InlineKeyboardButton(text="↩️ Расписание", callback_data=AdminMenu(action="schedule").pack())],
        ]
    )


def closed_dates_keyboard(rows: list[ClosedDate]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in rows:
        reason = f" — {row.reason}" if row.reason else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{row.date.strftime('%d.%m.%Y')}{reason}",
                callback_data=AdminClosedCB(closed_id=row.id, action="view").pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить дату", callback_data=AdminMenu(action="closed_add").pack())
    )
    builder.row(InlineKeyboardButton(text="↩️ Админ-меню", callback_data=AdminMenu(action="home").pack()))
    return builder.as_markup()


def closed_date_item_keyboard(closed_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=AdminClosedCB(closed_id=closed_id, action="delete").pack(),
                )
            ],
            [InlineKeyboardButton(text="↩️ К датам", callback_data=AdminMenu(action="closed").pack())],
        ]
    )


def clients_keyboard(users: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in users[:50]:
        name = user.first_name or "Без имени"
        username = f" @{user.username}" if user.username else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{name}{username}",
                callback_data=AdminClientCB(user_id=user.id).pack(),
            )
        )
    builder.row(InlineKeyboardButton(text="↩️ Админ-меню", callback_data=AdminMenu(action="home").pack()))
    return builder.as_markup()


def settings_keyboard() -> InlineKeyboardMarkup:
    fields = [
        ("Имя", "name"),
        ("Описание", "description"),
        ("Контакт", "contact"),
        ("Адрес", "address"),
        ("Часовой пояс", "timezone"),
    ]
    builder = InlineKeyboardBuilder()
    for text, field in fields:
        builder.row(
            InlineKeyboardButton(text=text, callback_data=AdminSettingCB(field=field).pack())
        )
    builder.row(InlineKeyboardButton(text="↩️ Админ-меню", callback_data=AdminMenu(action="home").pack()))
    return builder.as_markup()
