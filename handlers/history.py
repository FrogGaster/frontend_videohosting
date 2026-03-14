"""История лайков/дизлайков."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_user_by_telegram_id, get_profile_by_user_id, get_interaction_history, update_last_seen
from utils import escape_html

router = Router()


@router.message(Command("history"))
@router.message(F.text == "📜 История")
async def cmd_history(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала /start")
        return

    await update_last_seen(message.from_user.id)
    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала заполни профиль")
        return

    history = await get_interaction_history(user.id)
    if not history:
        await message.answer("📜 Пока пусто. Поставь лайки в /search!")
        return

    lines = ["📜 <b>История</b> (кого лайкнул/пропустил)\n━━━━━━━━━━━━━━\n"]
    for p, action in history[:30]:
        icon = "❤️" if action == "like" else "➡️"
        lines.append(f"{icon} {escape_html(p.nickname)} — {escape_html(p.main_dps)}")
    await message.answer("\n".join(lines))
