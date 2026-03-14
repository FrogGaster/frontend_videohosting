import aiosqlite
from datetime import datetime
from typing import Optional
from .models import User, Profile, Interaction
import config


async def init_db(db_path: str = config.DB_PATH) -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                nickname TEXT NOT NULL,
                world_level INTEGER NOT NULL,
                main_dps TEXT NOT NULL,
                server TEXT NOT NULL,
                description TEXT,
                photo_file_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (from_user_id) REFERENCES users (id),
                FOREIGN KEY (to_user_id) REFERENCES users (id),
                UNIQUE (from_user_id, to_user_id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_from ON interactions(from_user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_to ON interactions(to_user_id)")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_user_id INTEGER NOT NULL,
                reported_user_id INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (reporter_user_id) REFERENCES users (id),
                FOREIGN KEY (reported_user_id) REFERENCES users (id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at TEXT NOT NULL,
                reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_views (
                user_id INTEGER NOT NULL,
                view_date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, view_date),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_seen_at TEXT")
        except aiosqlite.OperationalError:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                digest_on INTEGER DEFAULT 1,
                like_notifications_on INTEGER DEFAULT 1,
                reminders_on INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hidden_matches (
                user_id INTEGER NOT NULL,
                hidden_user_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, hidden_user_id)
            )
        """)
        try:
            await db.execute("ALTER TABLE reports ADD COLUMN status TEXT DEFAULT 'pending'")
        except aiosqlite.OperationalError:
            pass

        await db.commit()


def get_db_path() -> str:
    return config.DB_PATH


async def get_or_create_user(telegram_id: int) -> User:
    """Get user by telegram_id or create new one."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        created_at = datetime.utcnow().isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, created_at) VALUES (?, ?)",
            (telegram_id, created_at)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id, telegram_id, created_at FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise RuntimeError(f"Failed to get or create user with telegram_id={telegram_id}")
        return User(id=row["id"], telegram_id=row["telegram_id"], created_at=row["created_at"])


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Get user by telegram_id."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, telegram_id, created_at FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            return User(id=row["id"], telegram_id=row["telegram_id"], created_at=row["created_at"])
        return None


async def get_user_and_ban_status(telegram_id: int) -> tuple[Optional[User], bool]:
    """Get user and ban status in one query (for middleware)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT u.id, u.telegram_id, u.created_at, b.user_id as banned
               FROM users u
               LEFT JOIN banned_users b ON b.user_id = u.id
               WHERE u.telegram_id = ?""",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None, False
        user = User(id=row["id"], telegram_id=row["telegram_id"], created_at=row["created_at"])
        return user, row["banned"] is not None


async def get_profile_by_user_id(user_id: int) -> Optional[Profile]:
    """Get profile by user_id."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, user_id, nickname, world_level, main_dps, server, description, photo_file_id
               FROM profiles WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return Profile(
                id=row["id"],
                user_id=row["user_id"],
                nickname=row["nickname"],
                world_level=row["world_level"],
                main_dps=row["main_dps"],
                server=row["server"],
                description=row["description"],
                photo_file_id=row["photo_file_id"]
            )
        return None


async def get_telegram_id_by_user_id(user_id: int) -> Optional[int]:
    """Get telegram_id by internal user_id."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT telegram_id FROM users WHERE id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_telegram_ids_by_user_ids(user_ids: list[int]) -> dict[int, int]:
    """Batch: user_id -> telegram_id for many users."""
    if not user_ids:
        return {}
    async with aiosqlite.connect(config.DB_PATH) as db:
        placeholders = ",".join("?" * len(user_ids))
        cursor = await db.execute(
            f"SELECT id, telegram_id FROM users WHERE id IN ({placeholders})",
            user_ids
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}


async def create_profile(user_id: int, nickname: str, world_level: int, main_dps: str,
                        server: str, description: Optional[str] = None,
                        photo_file_id: Optional[str] = None) -> Profile:
    """Create new profile."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO profiles (user_id, nickname, world_level, main_dps, server, description, photo_file_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, nickname, world_level, main_dps, server, description or "", photo_file_id or "")
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id, user_id, nickname, world_level, main_dps, server, description, photo_file_id FROM profiles WHERE id = ?",
            (cursor.lastrowid,)
        )
        row = await cursor.fetchone()
        return Profile(
            id=row["id"],
            user_id=row["user_id"],
            nickname=row["nickname"],
            world_level=row["world_level"],
            main_dps=row["main_dps"],
            server=row["server"],
            description=row["description"] or None,
            photo_file_id=row["photo_file_id"] or None
        )


async def update_profile(user_id: int, **kwargs) -> None:
    """Update profile fields. Allowed: nickname, world_level, main_dps, server, description, photo_file_id."""
    allowed = {"nickname", "world_level", "main_dps", "server", "description", "photo_file_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE profiles SET {set_clause} WHERE user_id = ?",
            values
        )
        await db.commit()


async def update_last_seen(telegram_id: int) -> None:
    """Обновить время последней активности."""
    from datetime import datetime
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_seen_at = ? WHERE telegram_id = ?",
            (datetime.utcnow().isoformat(), telegram_id)
        )
        await db.commit()


async def get_user_stats(user_id: int) -> dict:
    """Статистика пользователя (один запрос)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """SELECT u.created_at, u.last_seen_at,
               (SELECT COUNT(*) FROM interactions WHERE from_user_id = ? AND action = 'like'),
               (SELECT COUNT(*) FROM interactions WHERE to_user_id = ? AND action = 'like'),
               (SELECT COUNT(*) FROM interactions WHERE from_user_id = ? AND action = 'dislike'),
               (SELECT COUNT(*) FROM interactions WHERE to_user_id = ?)
               FROM users u WHERE u.id = ?""",
            (user_id, user_id, user_id, user_id, user_id)
        )
        row = await cursor.fetchone()
        if not row:
            return {"reg_date": "—", "last_seen": "—", "likes_given": 0, "likes_received": 0,
                    "dislikes_given": 0, "profile_views": 0}
        return {
            "reg_date": (row[0][:10] if row[0] else "—"),
            "last_seen": (str(row[1])[:10] if row[1] else "—"),
            "likes_given": row[2], "likes_received": row[3],
            "dislikes_given": row[4], "profile_views": row[5],
        }


async def add_report(reporter_user_id: int, reported_user_id: int, reason: str = "") -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (reporter_user_id, reported_user_id, reason, created_at) VALUES (?, ?, ?, ?)",
            (reporter_user_id, reported_user_id, reason, datetime.utcnow().isoformat())
        )
        await db.commit()


async def get_daily_views_count(user_id: int) -> int:
    """Сколько раз пользователь просмотрел карточки сегодня."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT count FROM daily_views WHERE user_id = ? AND view_date = ?",
            (user_id, today)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def increment_daily_view(user_id: int) -> None:
    """Увеличить счётчик просмотров за сегодня."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_views (user_id, view_date, count) VALUES (?, ?, 1)
               ON CONFLICT(user_id, view_date) DO UPDATE SET count = count + 1""",
            (user_id, today)
        )
        await db.commit()


async def is_banned(user_id: int) -> bool:
    """Забанен ли пользователь."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None


async def ban_user_by_telegram_id(telegram_id: int, reason: str = "") -> bool:
    """Забанить по telegram_id. Возвращает True если забанили."""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return False
    await ban_user(user.id, reason)
    return True


async def ban_user(user_id: int, reason: str = "") -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO banned_users (user_id, banned_at, reason) VALUES (?, ?, ?)",
            (user_id, datetime.utcnow().isoformat(), reason)
        )
        await db.commit()


async def get_next_candidate(from_user_id: int, server_filter: Optional[str] = None) -> Optional[Profile]:
    """Get next candidate: not self, not interacted, optional server filter, prioritize same server."""
    my_profile = await get_profile_by_user_id(from_user_id)
    my_server = my_profile.server if my_profile else None

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        base_sql = """
            SELECT p.id, p.user_id, p.nickname, p.world_level, p.main_dps, p.server, p.description, p.photo_file_id
            FROM profiles p
            WHERE p.user_id != ?
              AND p.user_id NOT IN (SELECT to_user_id FROM interactions WHERE from_user_id = ?)
              AND p.user_id NOT IN (SELECT user_id FROM banned_users)
        """
        params = [from_user_id, from_user_id]

        if server_filter:
            base_sql += " AND p.server LIKE ?"
            params.append(f"%{server_filter}%")

        base_sql += " ORDER BY "
        if my_server:
            base_sql += "CASE WHEN p.server LIKE ? THEN 0 ELSE 1 END, "
            params.append(f"%{my_server}%")
        base_sql += "RANDOM() LIMIT 1"

        cursor = await db.execute(base_sql, params)
        row = await cursor.fetchone()
        if row:
            return Profile(
                id=row["id"],
                user_id=row["user_id"],
                nickname=row["nickname"],
                world_level=row["world_level"],
                main_dps=row["main_dps"],
                server=row["server"],
                description=row["description"] or None,
                photo_file_id=row["photo_file_id"] or None
            )
        return None


async def add_interaction(from_user_id: int, to_user_id: int, action: str) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO interactions (from_user_id, to_user_id, action, created_at)
               VALUES (?, ?, ?, ?)""",
            (from_user_id, to_user_id, action, datetime.utcnow().isoformat())
        )
        await db.commit()


async def check_mutual_like(user_id_a: int, user_id_b: int) -> bool:
    """Check if both users liked each other."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """SELECT 1 FROM interactions
               WHERE from_user_id = ? AND to_user_id = ? AND action = 'like'
               INTERSECT
               SELECT 1 FROM interactions
               WHERE from_user_id = ? AND to_user_id = ? AND action = 'like'""",
            (user_id_a, user_id_b, user_id_b, user_id_a)
        )
        return await cursor.fetchone() is not None


async def get_mutual_likes(user_id: int, exclude_hidden: bool = True) -> list[Profile]:
    """Get list of profiles that have mutual likes with user (excluding hidden)."""
    hidden_clause = " AND p.user_id NOT IN (SELECT hidden_user_id FROM hidden_matches WHERE user_id = ?)" if exclude_hidden else ""
    params = [user_id, user_id, user_id] if exclude_hidden else [user_id, user_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"""
            SELECT p.id, p.user_id, p.nickname, p.world_level, p.main_dps, p.server, p.description, p.photo_file_id
            FROM profiles p
            WHERE EXISTS (
                SELECT 1 FROM interactions i1
                WHERE i1.from_user_id = ? AND i1.to_user_id = p.user_id AND i1.action = 'like'
            )
            AND EXISTS (
                SELECT 1 FROM interactions i2
                WHERE i2.from_user_id = p.user_id AND i2.to_user_id = ? AND i2.action = 'like'
            )
            {hidden_clause}
        """, params)
        rows = await cursor.fetchall()
        return [
            Profile(
                id=row["id"],
                user_id=row["user_id"],
                nickname=row["nickname"],
                world_level=row["world_level"],
                main_dps=row["main_dps"],
                server=row["server"],
                description=row["description"] or None,
                photo_file_id=row["photo_file_id"] or None
            )
            for row in rows
        ]


async def get_admin_stats() -> dict:
    """Статистика для админ-панели (один запрос)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                (SELECT COUNT(*) FROM users),
                (SELECT COUNT(*) FROM profiles),
                (SELECT COUNT(*) FROM interactions WHERE action = 'like'),
                (SELECT COUNT(*) FROM reports),
                (SELECT COUNT(*) FROM banned_users)
        """)
        row = (await cursor.fetchone())
        return {
            "total_users": row[0], "total_profiles": row[1],
            "total_likes": row[2], "total_reports": row[3], "total_banned": row[4],
        }


async def delete_user_completely(user_id: int) -> None:
    """Полностью удалить пользователя и все связанные данные."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM hidden_matches WHERE user_id = ? OR hidden_user_id = ?", (user_id, user_id))
        await db.execute("DELETE FROM interactions WHERE from_user_id = ? OR to_user_id = ?", (user_id, user_id))
        await db.execute("DELETE FROM reports WHERE reporter_user_id = ? OR reported_user_id = ?", (user_id, user_id))
        await db.execute("DELETE FROM daily_views WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()


async def hide_match(user_id: int, hidden_user_id: int) -> None:
    """Скрыть матч из списка."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO hidden_matches (user_id, hidden_user_id) VALUES (?, ?)",
            (user_id, hidden_user_id)
        )
        await db.commit()


async def get_interaction_history(user_id: int) -> list[tuple[Profile, str]]:
    """История: (profile, action) — кому лайк/дизлайк."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT p.id, p.user_id, p.nickname, p.world_level, p.main_dps, p.server, p.description, p.photo_file_id, i.action
            FROM interactions i
            JOIN profiles p ON p.user_id = i.to_user_id
            WHERE i.from_user_id = ?
            ORDER BY i.created_at DESC
            LIMIT 50
        """, (user_id,))
        rows = await cursor.fetchall()
        return [
            (Profile(
                id=row["id"], user_id=row["user_id"], nickname=row["nickname"],
                world_level=row["world_level"], main_dps=row["main_dps"],
                server=row["server"], description=row["description"],
                photo_file_id=row["photo_file_id"]
            ), row["action"])
            for row in rows
        ]


async def get_preferences(user_id: int) -> dict:
    """Настройки уведомлений. По умолчанию всё вкл."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT digest_on, like_notifications_on, reminders_on FROM user_preferences WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"digest_on": bool(row[0]), "like_notifications_on": bool(row[1]), "reminders_on": bool(row[2])}
        return {"digest_on": True, "like_notifications_on": True, "reminders_on": True}


async def set_preference(user_id: int, key: str, value: bool) -> None:
    """Установить настройку."""
    if key not in ("digest_on", "like_notifications_on", "reminders_on"):
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO user_preferences (user_id, digest_on, like_notifications_on, reminders_on)
               VALUES (?, 1, 1, 1)""",
            (user_id,)
        )
        await db.execute(
            f"UPDATE user_preferences SET {key} = ? WHERE user_id = ?",
            (1 if value else 0, user_id)
        )
        await db.commit()


async def get_pending_reports() -> list[dict]:
    """Список необработанных жалоб."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("""
                SELECT r.id, r.reporter_user_id, r.reported_user_id, r.reason, r.created_at,
                       pr.nickname as reporter_nick, pp.nickname as reported_nick
                FROM reports r
                JOIN profiles pr ON pr.user_id = r.reporter_user_id
                JOIN profiles pp ON pp.user_id = r.reported_user_id
                WHERE r.status = 'pending' OR r.status IS NULL
                ORDER BY r.created_at
                LIMIT 20
            """)
        except aiosqlite.OperationalError:
            cursor = await db.execute("""
                SELECT r.id, r.reporter_user_id, r.reported_user_id, r.reason, r.created_at,
                       pr.nickname as reporter_nick, pp.nickname as reported_nick
                FROM reports r
                JOIN profiles pr ON pr.user_id = r.reporter_user_id
                JOIN profiles pp ON pp.user_id = r.reported_user_id
                ORDER BY r.created_at
                LIMIT 20
            """)
        return [dict(row) for row in await cursor.fetchall()]


async def resolve_report(report_id: int, action: str) -> bool:
    """Закрыть жалобу: skip или ban."""
    try:
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute("UPDATE reports SET status = ? WHERE id = ?", (action, report_id))
            await db.commit()
        return True
    except aiosqlite.OperationalError:
        return False


async def unban_user(telegram_id: int) -> bool:
    """Разбанить."""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return False
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user.id,))
        await db.commit()
    return True


async def get_daily_stats() -> list[tuple[str, int]]:
    """Статистика по дням за 14 дней: (date, new_users)."""
    from datetime import timedelta
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("""
            SELECT date(created_at) as d, COUNT(*) FROM users
            WHERE created_at >= date('now', '-14 days')
            GROUP BY d ORDER BY d
        """)
        user_rows = {str(r[0]): r[1] for r in await cursor.fetchall()}
    result = []
    for i in range(14):
        d = (datetime.utcnow() - timedelta(days=13 - i)).strftime("%Y-%m-%d")
        result.append((d, user_rows.get(d, 0)))
    return result


async def get_telegram_ids_for_digest() -> list[int]:
    """Telegram ID пользователей с включённым дайджестом."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("""
            SELECT u.telegram_id FROM users u
            JOIN profiles p ON p.user_id = u.id
            LEFT JOIN user_preferences up ON up.user_id = u.id
            WHERE u.id NOT IN (SELECT user_id FROM banned_users)
              AND (up.digest_on IS NULL OR up.digest_on = 1)
        """)
        return [row[0] for row in await cursor.fetchall()]


async def get_telegram_ids_for_reminders() -> list[int]:
    """Telegram ID для напоминаний."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("""
            SELECT u.telegram_id FROM users u
            JOIN profiles p ON p.user_id = u.id
            LEFT JOIN user_preferences up ON up.user_id = u.id
            WHERE u.id NOT IN (SELECT user_id FROM banned_users)
              AND (up.reminders_on IS NULL OR up.reminders_on = 1)
        """)
        return [row[0] for row in await cursor.fetchall()]


async def get_all_telegram_ids() -> list[int]:
    """Все telegram_id пользователей с профилями (для рассылки)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """SELECT u.telegram_id FROM users u
               JOIN profiles p ON p.user_id = u.id
               WHERE u.id NOT IN (SELECT user_id FROM banned_users)"""
        )
        return [row[0] for row in await cursor.fetchall()]
