from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню с кнопками."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Поиск тиммейта")
    builder.button(text="👤 Мой профиль")
    builder.button(text="💕 Мои матчи")
    builder.button(text="📊 Статистика")
    builder.button(text="📜 История")
    builder.button(text="📤 Поделиться")
    builder.button(text="⚙️ Настройки")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_skip_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка Пропустить для регистрации."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏭ Пропустить")
    return builder.as_markup(resize_keyboard=True)


def get_registration_keyboard() -> ReplyKeyboardMarkup:
    """Убрать лишние кнопки при вводе текста."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)
