from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class ActionCallback(CallbackData, prefix="act"):
    action: str  # "like" | "dislike"
    user_id: int


class ResponseCallback(CallbackData, prefix="resp"):
    """Ответ на лайк: взаимный лайк или отказ."""
    action: str  # "like" | "dislike"
    user_id: int  # кто тебя лайкнул


class ExpCallback(CallbackData, prefix="exp"):
    level: int


class ReportCallback(CallbackData, prefix="report"):
    user_id: int  # кого репортим


class EditProfileCallback(CallbackData, prefix="edit"):
    field: str


class HideMatchCallback(CallbackData, prefix="hide"):
    user_id: int


class AdminReportCallback(CallbackData, prefix="admrep"):
    action: str  # skip | ban
    report_id: int


def get_response_keyboard(liker_user_id: int) -> InlineKeyboardMarkup:
    """Кнопки ответа на лайк: взаимный лайк или отказ."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="❤️ Взаимный лайк",
            callback_data=ResponseCallback(action="like", user_id=liker_user_id).pack()
        ),
        InlineKeyboardButton(
            text="👎 Нет, спасибо",
            callback_data=ResponseCallback(action="dislike", user_id=liker_user_id).pack()
        )
    )
    builder.adjust(2)
    return builder.as_markup()


def get_action_keyboard(candidate_user_id: int) -> InlineKeyboardMarkup:
    """Кнопки лайк / дизлайк / жалоба."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="❤️ Нравится",
            callback_data=ActionCallback(action="like", user_id=candidate_user_id).pack()
        ),
        InlineKeyboardButton(
            text="➡️ Дальше",
            callback_data=ActionCallback(action="dislike", user_id=candidate_user_id).pack()
        ),
        InlineKeyboardButton(
            text="🚩 Жалоба",
            callback_data=ReportCallback(user_id=candidate_user_id).pack()
        )
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def get_edit_profile_keyboard() -> InlineKeyboardMarkup:
    """Кнопки редактирования профиля."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="👤 Ник", callback_data=EditProfileCallback(field="nickname").pack()),
        InlineKeyboardButton(text="📊 Опыт", callback_data=EditProfileCallback(field="world_level").pack()),
        InlineKeyboardButton(text="🌍 Нация", callback_data=EditProfileCallback(field="main_dps").pack()),
        InlineKeyboardButton(text="🎮 Режим", callback_data=EditProfileCallback(field="server").pack()),
        InlineKeyboardButton(text="📝 О себе", callback_data=EditProfileCallback(field="description").pack()),
        InlineKeyboardButton(text="📸 Фото", callback_data=EditProfileCallback(field="photo").pack()),
    )
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def get_match_keyboard(profile_user_id: int, username: str | None) -> InlineKeyboardMarkup:
    """Кнопки под матчем: Написать + Убрать."""
    builder = InlineKeyboardBuilder()
    if username:
        builder.add(
            InlineKeyboardButton(text="✉️ Написать в Telegram", url=f"https://t.me/{username}")
        )
    builder.add(
        InlineKeyboardButton(
            text="🚫 Убрать из матчей",
            callback_data=HideMatchCallback(user_id=profile_user_id).pack()
        )
    )
    builder.adjust(1)
    return builder.as_markup()


def get_exp_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора опыта (1-5)."""
    builder = InlineKeyboardBuilder()
    labels = [
        (1, "🌱 Новичок"),
        (2, "📖 Мало часов"),
        (3, "⚖️ Средний"),
        (4, "⭐ Опытный"),
        (5, "🏆 Ветеран"),
    ]
    for level, label in labels:
        builder.button(text=label, callback_data=ExpCallback(level=level).pack())
    builder.adjust(2, 2, 1)  # 2 + 2 + 1
    return builder.as_markup()
