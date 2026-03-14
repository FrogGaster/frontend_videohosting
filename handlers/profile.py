from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_user_by_telegram_id, get_profile_by_user_id, update_profile, update_last_seen
from keyboards.reply import get_main_menu, get_skip_keyboard
from keyboards.inline import get_edit_profile_keyboard, get_exp_keyboard, EditProfileCallback, ExpCallback
from states import EditProfileStates
from utils import escape_html

router = Router()

EXP_NAMES = {1: "🌱 Новичок", 2: "📖 Мало часов", 3: "⚖️ Средний", 4: "⭐ Опытный", 5: "🏆 Ветеран"}


def format_profile_text(profile) -> str:
    exp = EXP_NAMES.get(profile.world_level, str(profile.world_level))
    return (
        "🎖 <b>Твой профиль</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 Ник: <b>{escape_html(profile.nickname)}</b>\n"
        f"📊 Опыт: {exp}\n"
        f"🌍 Любимая нация: {escape_html(profile.main_dps)}\n"
        f"🎮 Режим/моды: {escape_html(profile.server)}\n"
        f"📝 О себе: {escape_html(profile.description or '—')}\n\n"
        "✏️ Что изменить?"
    )


async def send_profile_with_edit(message_or_callback, profile):
    """Отправить профиль с кнопками редактирования."""
    text = format_profile_text(profile)
    kb = get_edit_profile_keyboard()
    is_callback = isinstance(message_or_callback, CallbackQuery)
    target = message_or_callback.message if is_callback else message_or_callback

    if profile.photo_file_id:
        await target.answer_photo(profile.photo_file_id, caption=text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.message(Command("profile"))
@router.message(F.text == "👤 Мой профиль")
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start")
        return

    await update_last_seen(message.from_user.id)
    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала пройди регистрацию через /start")
        return

    text = format_profile_text(profile)
    if profile.photo_file_id:
        await message.answer_photo(profile.photo_file_id, caption=text, reply_markup=get_edit_profile_keyboard())
    else:
        await message.answer(text, reply_markup=get_edit_profile_keyboard())


@router.callback_query(EditProfileCallback.filter())
async def edit_profile_field(callback: CallbackQuery, callback_data: EditProfileCallback, state: FSMContext):
    """Выбор поля для редактирования."""
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка")
        return

    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await callback.answer("Профиль не найден")
        return

    field = callback_data.field
    await state.update_data(edit_user_id=user.id)
    await state.set_state(EditProfileStates.choosing_field)

    prompts = {
        "nickname": "👤 Введи новый ник (до 50 символов):",
        "world_level": "📊 Выбери уровень опыта:",
        "main_dps": "🌍 Введи любимую нацию (до 50 символов):",
        "server": "🎮 Введи режим/моды (Vanilla, Kaiserreich и т.д.):",
        "description": "📝 Введи описание или нажми «⏭ Пропустить»:",
        "photo": "📸 Отправь новое фото или нажми «⏭ Пропустить»:",
    }
    prompt = prompts.get(field, "Введи новое значение:")

    if field == "world_level":
        await callback.message.answer(prompt, reply_markup=get_exp_keyboard())
    elif field == "description":
        await callback.message.answer(prompt, reply_markup=get_skip_keyboard())
    elif field == "photo":
        await callback.message.answer(prompt, reply_markup=get_skip_keyboard())
    else:
        await callback.message.answer(prompt)

    await state.update_data(edit_field=field)
    await state.set_state(getattr(EditProfileStates, field))
    await callback.answer()


@router.callback_query(EditProfileStates.world_level, ExpCallback.filter())
async def edit_exp(callback: CallbackQuery, callback_data: ExpCallback, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await callback.answer("Ошибка")
        return

    await update_profile(user_id, world_level=callback_data.level)
    await state.clear()
    await callback.message.edit_text("✅ Опыт обновлён!", reply_markup=None)
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(callback, profile)
    await callback.answer()


@router.message(EditProfileStates.nickname, F.text)
async def edit_nickname(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    text = message.text.strip()
    if len(text) > 50:
        await message.answer("⚠️ Ник до 50 символов.")
        return

    await update_profile(user_id, nickname=text)
    await state.clear()
    await message.answer("✅ Ник обновлён!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.main_dps, F.text)
async def edit_main_dps(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    text = message.text.strip()
    if len(text) > 50:
        await message.answer("⚠️ До 50 символов.")
        return

    await update_profile(user_id, main_dps=text)
    await state.clear()
    await message.answer("✅ Нация обновлена!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.server, F.text)
async def edit_server(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    await update_profile(user_id, server=message.text.strip())
    await state.clear()
    await message.answer("✅ Режим обновлён!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.description, F.text, F.text.in_({"/skip", "⏭ Пропустить"}))
async def edit_description_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    await update_profile(user_id, description=None)
    await state.clear()
    await message.answer("✅ Описание очищено!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.description, F.text)
async def edit_description(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    text = message.text.strip()
    if len(text) > 300:
        await message.answer("⚠️ Описание до 300 символов.")
        return

    await update_profile(user_id, description=text)
    await state.clear()
    await message.answer("✅ Описание обновлено!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.photo, F.text, F.text.in_({"/skip", "⏭ Пропустить"}))
async def edit_photo_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    await update_profile(user_id, photo_file_id=None)
    await state.clear()
    await message.answer("✅ Фото удалено!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.photo, F.photo)
async def edit_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await state.clear()
        return

    photo_file_id = message.photo[-1].file_id
    await update_profile(user_id, photo_file_id=photo_file_id)
    await state.clear()
    await message.answer("✅ Фото обновлено!")
    profile = await get_profile_by_user_id(user_id)
    if profile:
        await send_profile_with_edit(message, profile)


@router.message(EditProfileStates.photo)
async def edit_photo_wrong(message: Message):
    await message.answer("⚠️ Отправь фото или нажми «⏭ Пропустить»")
