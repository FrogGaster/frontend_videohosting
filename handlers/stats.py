from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_user_by_telegram_id, get_profile_by_user_id, get_user_stats, update_last_seen
from keyboards.reply import get_main_menu

router = Router()


@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def cmd_stats(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start")
        return

    await update_last_seen(message.from_user.id)
    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала пройди регистрацию через /start")
        return

    stats = await get_user_stats(user.id)
    text = (
        "📊 <b>Твоя статистика</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"📅 Регистрация: {stats['reg_date']}\n"
        f"🕐 Был в сети: {stats['last_seen']}\n"
        f"👁 Просмотров профиля: {stats['profile_views']}\n"
        f"❤️ Лайков отправлено: {stats['likes_given']}\n"
        f"💕 Лайков получено: {stats['likes_received']}\n"
        f"➡️ Пропущено: {stats['dislikes_given']}\n"
    )
    await message.answer(text, reply_markup=get_main_menu())
