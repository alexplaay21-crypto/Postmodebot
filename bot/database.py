# -*- coding: utf-8 -*-

import json
import os
import secrets
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bot.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'en',
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                posts_created INTEGER NOT NULL DEFAULT 0,
                posts_sent INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS posts (
                code TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                media_json TEXT,
                buttons_json TEXT,
                target TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_posts_user_id
                ON posts(user_id);

            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                type TEXT,
                title TEXT,
                username TEXT,
                status TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_user_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                type TEXT NOT NULL,
                user_id INTEGER,
                chat_id INTEGER,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_events_time
                ON events(time);

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                error TEXT NOT NULL,
                user_id INTEGER,
                chat_id INTEGER,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_errors_time
                ON errors(time);

            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                target TEXT,
                total INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0
            );

            INSERT OR IGNORE INTO settings(key, value)
            VALUES('maintenance_mode', 'false');
            """
        )


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _from_json(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def ensure_user(
    user_id: int,
    language: str = "en",
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> None:
    now = now_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(
                user_id, language, username, first_name,
                last_name, first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_seen = excluded.last_seen
            """,
            (
                int(user_id),
                language,
                username,
                first_name,
                last_name,
                now,
                now,
            ),
        )


def get_user_language(user_id: int, fallback: str = "en") -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()

    if not row or not row["language"]:
        return fallback

    return row["language"]


def set_user_language(user_id: int, lang: str) -> None:
    now = now_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(
                user_id, language, first_seen, last_seen
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                language = excluded.language,
                last_seen = excluded.last_seen
            """,
            (
                int(user_id),
                lang,
                now,
                now,
            ),
        )


def _generate_post_code(conn: sqlite3.Connection) -> str:
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(
            secrets.choice(alphabet)
            for _ in range(6)
        )

        exists = conn.execute(
            "SELECT 1 FROM posts WHERE code = ?",
            (code,),
        ).fetchone()

        if not exists:
            return code


def save_post(
    user_id,
    name,
    caption,
    media,
    buttons,
    target,
) -> dict:
    with connect() as conn:
        code = _generate_post_code(conn)

        post = {
            "code": code,
            "user_id": int(user_id),
            "name": name,
            "caption": caption or "",
            "media": media,
            "buttons": buttons,
            "target": target,
        }

        conn.execute(
            """
            INSERT INTO posts(
                code,
                user_id,
                name,
                caption,
                media_json,
                buttons_json,
                target,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code,
                int(user_id),
                name,
                caption or "",
                _json(media),
                _json(buttons),
                str(target) if target is not None else None,
                now_iso(),
            ),
        )

    return post


def _row_to_post(row: sqlite3.Row) -> dict:
    return {
        "code": row["code"],
        "user_id": int(row["user_id"]),
        "name": row["name"],
        "caption": row["caption"] or "",
        "media": _from_json(row["media_json"]),
        "buttons": _from_json(row["buttons_json"]),
        "target": row["target"],
        "created_at": row["created_at"],
    }


def get_user_posts(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM posts
            WHERE user_id = ?
            ORDER BY LOWER(name)
            """,
            (int(user_id),),
        ).fetchall()

    return [_row_to_post(row) for row in rows]


def get_post(user_id: int, code: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM posts
            WHERE code = ?
              AND user_id = ?
            """,
            (
                code.upper(),
                int(user_id),
            ),
        ).fetchone()

    return _row_to_post(row) if row else None


def delete_post(user_id: int, code: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM posts
            WHERE code = ?
              AND user_id = ?
            """,
            (
                code.upper(),
                int(user_id),
            ),
        )

    return cursor.rowcount > 0


def increment_posts_created(user_id: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(
                user_id,
                first_seen,
                last_seen,
                posts_created
            )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                posts_created = posts_created + 1,
                last_seen = excluded.last_seen
            """,
            (
                int(user_id),
                now_iso(),
                now_iso(),
            ),
        )


def increment_posts_sent(user_id: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(
                user_id,
                first_seen,
                last_seen,
                posts_sent
            )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                posts_sent = posts_sent + 1,
                last_seen = excluded.last_seen
            """,
            (
                int(user_id),
                now_iso(),
                now_iso(),
            ),
        )


def record_event(
    event_type: str,
    user_id: int | None = None,
    chat_id: int | None = None,
    details: dict | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO events(
                time,
                type,
                user_id,
                chat_id,
                details
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                now_iso(),
                event_type,
                user_id,
                chat_id,
                _json(details or {}),
            ),
        )


def record_error(
    error,
    user_id: int | None = None,
    chat_id: int | None = None,
    details: dict | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO errors(
                time,
                error,
                user_id,
                chat_id,
                details
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                now_iso(),
                str(error),
                user_id,
                chat_id,
                _json(details or {}),
            ),
        )


def track_chat(
    chat,
    user_id: int | None = None,
    status: str | None = None,
) -> None:
    if not chat:
        return

    now = now_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chats(
                chat_id,
                type,
                title,
                username,
                status,
                first_seen,
                last_seen,
                last_user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                type = excluded.type,
                title = excluded.title,
                username = excluded.username,
                status = COALESCE(
                    excluded.status,
                    chats.status
                ),
                last_seen = excluded.last_seen,
                last_user_id = COALESCE(
                    excluded.last_user_id,
                    chats.last_user_id
                )
            """,
            (
                int(chat.id),
                str(chat.type),
                getattr(chat, "title", None),
                getattr(chat, "username", None),
                status,
                now,
                now,
                user_id,
            ),
        )

    record_event(
        "chat_updated",
        user_id=user_id,
        chat_id=chat.id,
        details={
            "type": str(chat.type),
            "status": status,
        },
    )


def set_blocked(user_id: int, blocked: bool = True) -> None:
    with connect() as conn:
        if blocked:
            conn.execute(
                """
                INSERT OR IGNORE INTO blocked_users(user_id)
                VALUES (?)
                """,
                (int(user_id),),
            )
        else:
            conn.execute(
                """
                DELETE FROM blocked_users
                WHERE user_id = ?
                """,
                (int(user_id),),
            )


def is_blocked(user_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM blocked_users
            WHERE user_id = ?
            """,
            (int(user_id),),
        ).fetchone()

    return row is not None


def get_setting(name: str, default=None):
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (name,),
        ).fetchone()

    if not row:
        return default

    value = row["value"]

    if isinstance(default, bool):
        return value.lower() == "true"

    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default

    return value


def set_setting(name: str, value) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value
            """,
            (name, str(value)),
        )


def get_users() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY last_seen DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_all_user_ids() -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users ORDER BY user_id"
        ).fetchall()

    return [int(row["user_id"]) for row in rows]


def get_posts() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM posts
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [_row_to_post(row) for row in rows]


def get_chats() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM chats
            ORDER BY last_seen DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_events(limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    return [dict(row) for row in rows]


def get_errors(limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM errors
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    return [dict(row) for row in rows]


def get_blocked_users() -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id
            FROM blocked_users
            ORDER BY user_id
            """
        ).fetchall()

    return [int(row["user_id"]) for row in rows]


def get_language_stats() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT language, COUNT(*) AS count
            FROM users
            GROUP BY language
            ORDER BY count DESC
            """
        ).fetchall()

    return {
        row["language"]: int(row["count"])
        for row in rows
    }


def add_broadcast(
    target: str,
    total: int,
    success: int,
    failed: int,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO broadcasts(
                time,
                target,
                total,
                success,
                failed
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                now_iso(),
                target,
                total,
                success,
                failed,
            ),
        )


def get_broadcasts(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM broadcasts
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    return [dict(row) for row in rows]


def get_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            "users": conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0],
            "posts": conn.execute(
                "SELECT COUNT(*) FROM posts"
            ).fetchone()[0],
            "chats": conn.execute(
                "SELECT COUNT(*) FROM chats"
            ).fetchone()[0],
            "events": conn.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()[0],
            "errors": conn.execute(
                "SELECT COUNT(*) FROM errors"
            ).fetchone()[0],
            "blocked": conn.execute(
                "SELECT COUNT(*) FROM blocked_users"
            ).fetchone()[0],
        }


def get_user(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (int(user_id),),
        ).fetchone()

    return dict(row) if row else None


def search_users(query: str) -> list[dict]:
    query = query.strip()

    with connect() as conn:
        if query.lstrip("-").isdigit():
            rows = conn.execute(
                """
                SELECT *
                FROM users
                WHERE user_id = ?
                """,
                (int(query),),
            ).fetchall()
        else:
            pattern = f"%{query.lower()}%"
            rows = conn.execute(
                """
                SELECT *
                FROM users
                WHERE LOWER(COALESCE(username, '')) LIKE ?
                   OR LOWER(COALESCE(first_name, '')) LIKE ?
                   OR LOWER(COALESCE(last_name, '')) LIKE ?
                ORDER BY last_seen DESC
                LIMIT 50
                """,
                (pattern, pattern, pattern),
            ).fetchall()

    return [dict(row) for row in rows]


def get_database_size() -> int:
    try:
        return os.path.getsize(DB_PATH)
    except OSError:
        return 0


def backup_database(destination: Path) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    source = connect()

    try:
        target = sqlite3.connect(destination)

        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


init_db()
