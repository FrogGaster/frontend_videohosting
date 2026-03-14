"""Удаление аккаунта, шаринг анкеты."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_user_by_telegram_id, get_profile_by_user_id, delete_user_completely
from keyboards.reply import get_main_menu
from aiogram.utils.keyboard import InlineKeyboardBuilder
from states import DeleteAccountStates

router = Router()

def format_share_text(profile, bot_username: str) -> str:
    from utils import escape_html
    exp = {1: "Новичок", 2: "Мало часов", 3: "Средний", 4: "Опытный", 5: "Ветеран"}.get(profile.world_level, "")
    return (
        f"🎖 Анкета: {escape_html(profile.nickname)}\n"
        f"Опыт: {exp} · {escape_html(profile.main_dps)} · {escape_html(profile.server)}\n"
        f"О себе: {escape_html(profile.description or '—')}\n\n"
        f"Найди тиммейта: https://t.me/{bot_username}"
    )


@router.message(Command("delete"))
async def cmd_delete(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала /start")
        return

    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Профиль не найден")
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="delete_confirm")
    builder.button(text="❌ Отмена", callback_data="delete_cancel")

    await state.set_state(DeleteAccountStates.confirm)
    await message.answer(
        "⚠️ <b>Удаление аккаунта</b>\n\n"
        "Удалится профиль и вся история. Это нельзя отменить.\n"
        "Подтвердить?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "delete_confirm")
async def delete_confirm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer()
        return

    await delete_user_completely(user.id)
    await callback.message.edit_text("Аккаунт удалён. До встречи! 👋")
    await callback.answer()


@router.callback_query(F.data == "delete_cancel")
async def delete_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.message(Command("share"))
@router.message(F.text == "📤 Поделиться")
async def cmd_share(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала /start")
        return

    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала заполни профиль /start")
        return

    import config
    username = config.BOT_USERNAME
    text = format_share_text(profile, username)
    if profile.photo_file_id:
        await message.answer_photo(profile.photo_file_id, caption=text)
    else:
        await message.answer(text)
    await message.answer("Скопируй и отправь друзьям 👆")
