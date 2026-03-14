"""Админ-панель: статистика, рассылка, бан, жалобы."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import config
from database.db import (
    get_admin_stats,
    get_all_telegram_ids,
    ban_user_by_telegram_id,
    get_user_by_telegram_id,
    get_profile_by_user_id,
    get_telegram_id_by_user_id,
    get_pending_reports,
    resolve_report,
    unban_user,
    get_daily_stats,
)
from keyboards.inline import AdminReportCallback

router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in config.ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_admin_stats()
    text = (
        "🔧 <b>Админ-панель</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📋 Анкет: {stats['total_profiles']}\n"
        f"❤️ Лайков всего: {stats['total_likes']}\n"
        f"🚩 Жалоб: {stats['total_reports']}\n"
        f"⛔ Забанено: {stats['total_banned']}\n\n"
        "Команды:\n"
        "/admin_broadcast - Рассылка\n"
        "/admin_ban [id] - Забанить\n"
        "/admin_unban [id] - Разбанить\n"
        "/admin_reports - Жалобы\n"
        "/admin_stats - Статистика по дням"
    )
    await message.answer(text)


@router.message(Command("admin_reports"))
async def cmd_reports(message: Message):
    if not is_admin(message.from_user.id):
        return

    reports = await get_pending_reports()
    if not reports:
        await message.answer("Нет новых жалоб")
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    for r in reports[:10]:
        text = (
            f"🚩 Жалоба #{r['id']}\n"
            f"На: {r['reported_nick']} (id {r['reported_user_id']})\n"
            f"От: {r['reporter_nick']}\n"
            f"Причина: {r['reason'] or '—'}\n"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Пропустить", callback_data=AdminReportCallback(action="skip", report_id=r["id"]).pack())
        builder.button(text="⛔ Забанить", callback_data=AdminReportCallback(action="ban", report_id=r["id"]).pack())
        builder.adjust(2)
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(AdminReportCallback.filter())
async def process_admin_report(callback: CallbackQuery, callback_data: AdminReportCallback):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    reports = await get_pending_reports()
    r = next((x for x in reports if x["id"] == callback_data.report_id), None)
    if not r:
        await callback.answer("Жалоба уже обработана")
        return

    await resolve_report(callback_data.report_id, callback_data.action)
    if callback_data.action == "ban":
        tid = await get_telegram_id_by_user_id(r["reported_user_id"])
        if tid:
            await ban_user_by_telegram_id(tid, f"По жалобе #{callback_data.report_id}")
    await callback.message.edit_text(callback.message.text + "\n\n✅ Обработано")
    await callback.answer()


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_daily_stats()
    lines = ["📊 <b>Статистика по дням</b>\n"]
    for d, count in stats:
        lines.append(f"{d}: +{count} пользователей")
    await message.answer("\n".join(lines))


@router.message(Command("admin_unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /admin_unban 123456789")
        return

    try:
        tid = int(parts[1])
    except ValueError:
        await message.answer("telegram_id — число")
        return

    if await unban_user(tid):
        await message.answer(f"✅ Пользователь {tid} разбанен")
    else:
        await message.answer("Пользователь не найден")


@router.message(Command("admin_broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Отправь текст рассылки: /admin_broadcast Ваш текст")
        return

    text = args[1]
    ids = await get_all_telegram_ids()
    ok, fail = 0, 0
    for tid in ids:
        try:
            await message.bot.send_message(tid, text)
            ok += 1
        except Exception:
            fail += 1

    await message.answer(f"✅ Отправлено: {ok}\n❌ Ошибок: {fail}")


@router.message(Command("admin_ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /admin_ban 123456789")
        return

    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id должен быть числом")
        return

    reason = " ".join(parts[2:]) if len(parts) > 2 else ""

    if await ban_user_by_telegram_id(telegram_id, reason):
        await message.answer(f"⛔ Пользователь {telegram_id} забанен")
    else:
        await message.answer("Пользователь не найден")
