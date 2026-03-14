"""Фоновые задачи: дайджест, напоминания, бэкап."""
import logging
import os
import shutil
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config

logger = logging.getLogger(__name__)


def setup_scheduled_tasks(bot, db_path: str):
    """Запуск всех фоновых задач."""
    from database.db import get_telegram_ids_for_digest, get_telegram_ids_for_reminders

    async def send_weekly_digest():
        try:
            ids = await get_telegram_ids_for_digest()
            for tid in ids:
                try:
                    await bot.send_message(
                        tid,
                        "📬 <b>Еженедельный дайджест</b>\n\n"
                        "Появились новые тиммейты! Загляни в поиск 🔍"
                    )
                except Exception as e:
                    logger.debug("Weekly digest skip %s: %s", tid, e)

        except Exception as e:
            logger.exception("Weekly digest error: %s", e)

    async def send_reminders():
        """Напоминание: новые анкеты."""
        try:
            ids = await get_telegram_ids_for_reminders()
            for tid in ids:
                try:
                    await bot.send_message(
                        tid,
                        "🔔 <b>Напоминание</b>\n\nЗаходи в поиск — возможно, появились новые тиммейты! 🔍"
                    )
                except Exception as e:
                    logger.debug("Reminder skip %s: %s", tid, e)
        except Exception as e:
            logger.exception("Reminders error: %s", e)

    def backup_db():
        try:
            os.makedirs(config.BACKUP_DIR, exist_ok=True)
            name = f"teammates_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.db"
            path = os.path.join(config.BACKUP_DIR, name)
            shutil.copy2(config.DB_PATH, path)
            logger.info("DB backup: %s", path)
            files = sorted(os.listdir(config.BACKUP_DIR))
            for f in files[:-10] if len(files) > 10 else []:
                try:
                    os.remove(os.path.join(config.BACKUP_DIR, f))
                except OSError:
                    pass
        except Exception as e:
            logger.exception("Backup error: %s", e)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_weekly_digest, "cron", day_of_week="sun", hour=12, minute=0, id="weekly_digest")
    scheduler.add_job(send_reminders, "cron", day_of_week="wed", hour=18, minute=0, id="reminders")
    scheduler.add_job(backup_db, "cron", hour=4, minute=0, id="backup")
    scheduler.start()
    return scheduler
