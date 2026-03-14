from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, TelegramObject

import config
from database.db import get_user_and_ban_status


def get_subscribe_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой подписки и проверки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{config.CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
    ])


async def check_subscription(bot, user_id: int) -> bool:
    """Проверить, подписан ли пользователь на канал."""
    try:
        member = await bot.get_chat_member(
            chat_id=f"@{config.CHANNEL_USERNAME}",
            user_id=user_id
        )
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception:
        return False


class SubscriptionMiddleware(BaseMiddleware):
    """Проверяет подписку на канал перед обработкой."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if not hasattr(event, "from_user") or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        bot = event.bot if hasattr(event, "bot") else data.get("bot")
        if not bot:
            return await handler(event, data)

        user, is_banned_user = await get_user_and_ban_status(user_id)
        if user and is_banned_user:
            text = "⛔ Доступ запрещён. Ты заблокирован."
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return

        if await check_subscription(bot, user_id):
            return await handler(event, data)

        text = (
            "📢 <b>Подписка на канал</b>\n\n"
            "Для использования бота необходимо подписаться на наш канал.\n"
            "После подписки нажми кнопку ниже 👇"
        )

        if isinstance(event, Message):
            await event.answer(text, reply_markup=get_subscribe_keyboard())
        elif isinstance(event, CallbackQuery) and event.message:
            await event.answer()
            await event.message.answer(text, reply_markup=get_subscribe_keyboard())

        return
