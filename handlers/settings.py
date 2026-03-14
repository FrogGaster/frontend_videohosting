"""Настройки уведомлений."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_user_by_telegram_id, get_profile_by_user_id, get_preferences, set_preference
from keyboards.reply import get_main_menu
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала /start")
        return

    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала заполни профиль")
        return

    prefs = await get_preferences(user.id)
    digest = "✅" if prefs["digest_on"] else "❌"
    likes = "✅" if prefs["like_notifications_on"] else "❌"
    rem = "✅" if prefs["reminders_on"] else "❌"

    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"📬 Еженедельный дайджест {digest}",
        callback_data="set_digest"
    )
    builder.button(
        text=f"💕 Уведомления о лайках {likes}",
        callback_data="set_likes"
    )
    builder.button(
        text=f"🔔 Напоминания «новые анкеты» {rem}",
        callback_data="set_reminders"
    )
    builder.adjust(1)

    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Включить/выключить:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("set_"))
async def toggle_setting(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer()
        return

    key = {"set_digest": "digest_on", "set_likes": "like_notifications_on", "set_reminders": "reminders_on"}.get(callback.data)
    if not key:
        await callback.answer()
        return

    prefs = await get_preferences(user.id)
    current = prefs[key]
    await set_preference(user.id, key, not current)
    await callback.answer(f"{'Выключено' if current else 'Включено'}")

    prefs = await get_preferences(user.id)
    digest = "✅" if prefs["digest_on"] else "❌"
    likes = "✅" if prefs["like_notifications_on"] else "❌"
    rem = "✅" if prefs["reminders_on"] else "❌"
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📬 Еженедельный дайджест {digest}", callback_data="set_digest")
    builder.button(text=f"💕 Уведомления о лайках {likes}", callback_data="set_likes")
    builder.button(text=f"🔔 Напоминания «новые анкеты» {rem}", callback_data="set_reminders")
    builder.adjust(1)
    await callback.message.edit_text("⚙️ <b>Настройки</b>\n\nВключить/выключить:", reply_markup=builder.as_markup())
