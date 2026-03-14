import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "HoI4Match_bot")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")

DB_PATH = os.getenv("DB_PATH", "teammates.db")

# Канал, подписка на который обязательна
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "The_Club_of_the_Executed")

# Админы (telegram_id через запятую)
def _parse_admin_ids():
    ids = []
    for x in os.getenv("ADMIN_IDS", "").split(","):
        try:
            v = x.strip()
            if v:
                ids.append(int(v))
        except ValueError:
            pass
    return ids

ADMIN_IDS = _parse_admin_ids()

# Лимит просмотров в день
DAILY_VIEW_LIMIT = int(os.getenv("DAILY_VIEW_LIMIT", "50"))

# Логи и бэкапы
LOG_FILE = os.getenv("LOG_FILE", "bot.log")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
