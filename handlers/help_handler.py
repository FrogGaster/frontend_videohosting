"""Справка по командам."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 <b>Справка</b>\n\n"
        "🔍 /search — Поиск тиммейта\n"
        "👤 /profile — Мой профиль\n"
        "💕 /matches — Мои матчи\n"
        "📊 /stats — Статистика\n"
        "📜 /history — История лайков\n"
        "📤 /share — Поделиться анкетой\n"
        "⚙️ /settings — Настройки уведомлений\n"
        "🗑 /delete — Удалить аккаунт\n"
        "❓ /help — Эта справка"
    )
    await message.answer(text)
