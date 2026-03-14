import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user_by_telegram_id,
    get_profile_by_user_id,
    get_next_candidate,
    add_interaction,
    check_mutual_like,
    get_telegram_id_by_user_id,
    get_telegram_ids_by_user_ids,
    increment_daily_view,
    get_daily_views_count,
    add_report,
    update_last_seen,
)
from keyboards.inline import (
    get_action_keyboard,
    get_response_keyboard,
    get_match_keyboard,
    ActionCallback,
    ResponseCallback,
    ReportCallback,
    HideMatchCallback,
)
from states import ReportStates
from utils import escape_html

import config

router = Router()

EXP_NAMES = {1: "🌱 Новичок", 2: "📖 Мало часов", 3: "⚖️ Средний", 4: "⭐ Опытный", 5: "🏆 Ветеран"}


def format_match_contact(profile, username: str | None) -> str:
    """Полная карточка для матча с контактами."""
    exp = EXP_NAMES.get(profile.world_level, str(profile.world_level))
    contact = f"✉️ Написать: @{username}\n🔗 t.me/{username}" if username else "⚠️ У пользователя нет @username. Пусть напишет первым."
    return (
        "💕 <b>Матч! Контакт тиммейта:</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 <b>{escape_html(profile.nickname)}</b>\n"
        f"📊 {exp} · 🌍 {escape_html(profile.main_dps)}\n"
        f"🎮 {escape_html(profile.server)}\n"
        f"📝 {escape_html(profile.description or '—')}\n\n"
        f"{contact}"
    )


def format_profile_card(profile) -> str:
    exp = EXP_NAMES.get(profile.world_level, str(profile.world_level))
    return (
        "🎖 <b>Кандидат</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 <b>{escape_html(profile.nickname)}</b>\n"
        f"📊 {exp}\n"
        f"🌍 {escape_html(profile.main_dps)}\n"
        f"🎮 {escape_html(profile.server)}\n"
        f"📝 {escape_html(profile.description or '—')}"
    )


async def send_candidate(message_or_callback, user_id: int, server_filter: str | None = None):
    """Send next candidate or 'no one left' message."""
    from aiogram.types import Message, CallbackQuery

    async def _update_callback_message(text: str, reply_markup=None) -> None:
        """Safely update callback source message regardless of content type."""
        msg = message_or_callback.message
        if msg is None:
            await message_or_callback.bot.send_message(chat_id, text, reply_markup=reply_markup)
            return

        try:
            if msg.text is not None:
                await msg.edit_text(text, reply_markup=reply_markup)
            elif msg.caption is not None:
                await msg.edit_caption(caption=text, reply_markup=reply_markup)
            else:
                await msg.delete()
                await message_or_callback.bot.send_message(chat_id, text, reply_markup=reply_markup)
        except Exception:
            await message_or_callback.bot.send_message(chat_id, text, reply_markup=reply_markup)

    views_today = await get_daily_views_count(user_id)
    if views_today >= config.DAILY_VIEW_LIMIT:
        text = (
            f"⏱ <b>Лимит на сегодня</b>\n\n"
            f"Ты просмотрел {views_today} анкет. Лимит: {config.DAILY_VIEW_LIMIT}. Загляни завтра! 🌅"
        )
        if isinstance(message_or_callback, CallbackQuery):
            chat_id = message_or_callback.message.chat.id
            await _update_callback_message(text)
        else:
            await message_or_callback.answer(text)
        return

    candidate = await get_next_candidate(user_id, server_filter)
    is_callback = isinstance(message_or_callback, CallbackQuery)
    chat_id = message_or_callback.message.chat.id if is_callback else message_or_callback.chat.id

    if candidate:
        await increment_daily_view(user_id)

    if not candidate:
        text = (
            "🔍 <b>Пока никого нет</b>\n\n"
            "Ты просмотрел всех! Загляни позже или позови друзей 🎖"
        )
        if is_callback:
            await _update_callback_message(text)
        else:
            await message_or_callback.answer(text)
        return

    text = format_profile_card(candidate)
    kb = get_action_keyboard(candidate.user_id)

    if is_callback:
        if candidate.photo_file_id:
            await message_or_callback.message.delete()
            await message_or_callback.message.answer_photo(
                candidate.photo_file_id,
                caption=text,
                reply_markup=kb
            )
        else:
            await _update_callback_message(text, reply_markup=kb)
    else:
        if candidate.photo_file_id:
            await message_or_callback.answer_photo(
                candidate.photo_file_id,
                caption=text,
                reply_markup=kb
            )
        else:
            await message_or_callback.answer(text, reply_markup=kb)


@router.message(Command("search"))
@router.message(F.text == "🔍 Поиск тиммейта")
async def cmd_search(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start")
        return

    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала пройди регистрацию через /start")
        return

    await update_last_seen(message.from_user.id)
    await send_candidate(message, user.id)


@router.callback_query(ActionCallback.filter())
async def process_action(callback: CallbackQuery, callback_data: ActionCallback):
    if callback.from_user is None:
        return

    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка. Нажми /start")
        return

    from_user_id = user.id
    to_user_id = callback_data.user_id

    if callback_data.action not in ("like", "dislike"):
        await callback.answer("Неизвестное действие")
        return

    await add_interaction(from_user_id, to_user_id, callback_data.action)
    await update_last_seen(callback.from_user.id)

    if callback_data.action == "like":
        from database.db import get_preferences
        prefs, target_telegram_id, liker_profile = await asyncio.gather(
            get_preferences(to_user_id),
            get_telegram_id_by_user_id(to_user_id),
            get_profile_by_user_id(from_user_id),
        )
        if prefs.get("like_notifications_on", True) and target_telegram_id:
            liker_username = callback.from_user.username
            name = f"@{liker_username}" if liker_username else liker_profile.nickname
            text = (
                f"💕 <b>{name} лайкнул тебя!</b>\n\n"
                f"👤 {liker_profile.nickname} · {liker_profile.main_dps}\n"
                f"Поставь взаимный лайк или откажись:"
            )
            kb = get_response_keyboard(from_user_id)
            if liker_profile.photo_file_id:
                await callback.bot.send_photo(
                    target_telegram_id,
                    liker_profile.photo_file_id,
                    caption=text,
                    reply_markup=kb
                )
            else:
                await callback.bot.send_message(target_telegram_id, text, reply_markup=kb)

    await callback.answer()
    await send_candidate(callback, user.id)


@router.callback_query(ReportCallback.filter())
async def process_report_start(callback: CallbackQuery, callback_data: ReportCallback, state: FSMContext):
    """Начало жалобы — запрашиваем причину."""
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка")
        return

    await state.update_data(report_target_user_id=callback_data.user_id)
    await state.set_state(ReportStates.reason)
    await callback.message.answer(
        "🚩 <b>Жалоба</b>\n\nОпиши причину жалобы (спам, оскорбления, фейк и т.д.):"
    )
    await callback.answer()


@router.message(ReportStates.reason, F.text)
async def process_report_reason(message: Message, state: FSMContext):
    """Сохраняем жалобу."""
    data = await state.get_data()
    target_id = data.get("report_target_user_id")
    await state.clear()

    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or not target_id:
        await message.answer("Ошибка. Попробуй снова.")
        return

    await add_report(user.id, target_id, message.text[:500])
    await message.answer("✅ Жалоба отправлена. Спасибо за бдительность! 🛡")

    reported_profile = await get_profile_by_user_id(target_id)
    if reported_profile and message.bot:
        import config
        for admin_id in config.ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"🚩 <b>Новая жалоба</b>\n"
                    f"На: {reported_profile.nickname} (id {target_id})\n"
                    f"Причина: {message.text[:200]}"
                )
            except Exception:
                pass


@router.callback_query(ResponseCallback.filter())
async def process_response(callback: CallbackQuery, callback_data: ResponseCallback):
    """Обработка ответа на лайк: взаимный лайк или отказ."""
    if callback.from_user is None:
        return

    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка. Нажми /start")
        return

    respondent_id = user.id  # кто отвечает (B)
    liker_id = callback_data.user_id  # кто лайкнул (A)

    if callback_data.action not in ("like", "dislike"):
        await callback.answer("Неизвестное действие")
        return

    await add_interaction(respondent_id, liker_id, callback_data.action)

    def _edit_notification(new_text: str):
        if callback.message.photo:
            return callback.message.edit_caption(caption=new_text, reply_markup=None)
        return callback.message.edit_text(new_text, reply_markup=None)

    if callback_data.action == "like":
        liker_telegram_id, liker_profile, respondent_profile = await asyncio.gather(
            get_telegram_id_by_user_id(liker_id),
            get_profile_by_user_id(liker_id),
            get_profile_by_user_id(respondent_id),
        )
        respondent_telegram_id = callback.from_user.id

        async def _get_chat_safe(bot, tid):
            if not tid:
                return None
            try:
                return await bot.get_chat(tid)
            except Exception:
                return None

        liker_chat, respondent_chat = await asyncio.gather(
            _get_chat_safe(callback.bot, liker_telegram_id),
            _get_chat_safe(callback.bot, respondent_telegram_id),
        )

        msg_for_liker = format_match_contact(
            respondent_profile,
            respondent_chat.username if respondent_chat else None
        )
        msg_for_respondent = format_match_contact(
            liker_profile,
            liker_chat.username if liker_chat else None
        )

        kb_liker = get_match_keyboard(respondent_id, respondent_chat.username if respondent_chat else None)
        kb_respondent = get_match_keyboard(liker_id, liker_chat.username if liker_chat else None)

        if liker_telegram_id:
            if respondent_profile.photo_file_id:
                await callback.bot.send_photo(
                    liker_telegram_id,
                    respondent_profile.photo_file_id,
                    caption=msg_for_liker,
                    reply_markup=kb_liker
                )
            else:
                await callback.bot.send_message(liker_telegram_id, msg_for_liker, reply_markup=kb_liker)

        if respondent_profile.photo_file_id:
            await callback.bot.send_photo(
                respondent_telegram_id,
                liker_profile.photo_file_id,
                caption=msg_for_respondent,
                reply_markup=kb_respondent
            )
        else:
            await callback.bot.send_message(respondent_telegram_id, msg_for_respondent, reply_markup=kb_respondent)

        await _edit_notification(
            "💕 <b>Матч!</b> Контакт твоего тиммейта — в сообщении ниже 👇"
        )
        await callback.answer("💕 Матч! Контакты отправлены обоим", show_alert=True)
    else:
        await _edit_notification("✅ Ответ записан. Спасибо! 👍")
        await callback.answer("Ответ отправлен")


@router.message(Command("matches"))
@router.message(F.text == "💕 Мои матчи")
async def cmd_matches(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start")
        return

    await update_last_seen(message.from_user.id)
    profile = await get_profile_by_user_id(user.id)
    if not profile:
        await message.answer("Сначала пройди регистрацию через /start")
        return

    from database.db import get_mutual_likes

    mutuals = await get_mutual_likes(user.id)
    if not mutuals:
        await message.answer(
            "💕 <b>Пока нет матчей</b>\n\n"
            "Ставь ❤️ тем, кто нравится — при взаимном лайке появится матч! 🔍"
        )
        return

    from keyboards.inline import get_match_keyboard

    tid_map = await get_telegram_ids_by_user_ids([p.user_id for p in mutuals])

    async def _username(tid):
        if not tid:
            return None
        try:
            chat = await message.bot.get_chat(tid)
            return chat.username
        except Exception:
            return None

    usernames = await asyncio.gather(*[_username(tid_map.get(p.user_id)) for p in mutuals])
    await message.answer("💕 <b>Твои матчи</b> 👇")

    for p, username in zip(mutuals, usernames):
        kb = get_match_keyboard(p.user_id, username)
        text = f"👤 <b>{escape_html(p.nickname)}</b> — {escape_html(p.main_dps)}"
        await message.answer(text, reply_markup=kb)


@router.callback_query(HideMatchCallback.filter())
async def hide_match(callback: CallbackQuery, callback_data: HideMatchCallback):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer()
        return

    from database.db import hide_match as db_hide_match
    await db_hide_match(user.id, callback_data.user_id)
    await callback.message.edit_text("✅ Убрано из матчей", reply_markup=None)
    await callback.answer("Скрыто")
