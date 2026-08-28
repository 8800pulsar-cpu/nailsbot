from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💅 Записаться")],
            [KeyboardButton(text="📅 Моя запись")],
            [KeyboardButton(text="ℹ️ Информация")],
        ],
        resize_keyboard=True,
    )
