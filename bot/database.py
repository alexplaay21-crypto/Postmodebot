# -*- coding: utf-8 -*-

import json
import os
import secrets
import string
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv("DATABASE_URL", "")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Add PostgreSQL DATABASE_URL to environment."
        )

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'en',
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TIMESTAMPTZ NOT NULL,
                last_seen TIMESTAMPTZ NOT NULL,
                posts_created INTEGER NOT NULL DEFAULT 0,
                posts_sent INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS posts (
                code TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                media_json TEXT,
                buttons_json TEXT,
                target TEXT,
                entities_json TEXT,
                created_at TIMESTAMPTZ NOT NULL
            );

            ALTER TABLE posts
                ADD COLUMN IF NOT EXISTS entities_json TEXT;

            CREATE INDEX IF NOT EXISTS idx_posts_user_id
                ON posts(user_id);

            CREATE TABLE IF NOT EXISTS chats (
                chat_id BIGINT PRIMARY KEY,
                type TEXT,
                title TEXT,
                username TEXT,
                status TEXT,
                first_seen TIMESTAMPTZ NOT NULL,
                last_seen TIMESTAMPTZ NOT NULL,
                last_user_id BIGINT
            );

            CREATE TABLE IF NOT EXISTS events (
                id BIGSERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                type TEXT NOT NULL,
                user_id BIGINT,
                chat_id BIGINT,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_events_time
                ON events(time);

            CREATE TABLE IF NOT EXISTS errors (
                id BIGSERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                error TEXT NOT NULL,
                user_id BIGINT,
                chat_id BIGINT,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_errors_time
                ON errors(time);

            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id BIGINT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS broadcasts (
                id BIGSERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                target TEXT,
                total INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0
            );

            INSERT INTO settings(key, value)
            VALUES ('maintenance_mode', 'false')
            ON CONFLICT(key) DO NOTHING;
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
                user_id,
                language,
                username,
                first_name,
                last_name,
                first_seen,
                last_seen
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_seen = EXCLUDED.last_seen
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


def get_user_language(
    user_id: int,
    fallback: str = "en",
) -> str:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT language
            FROM users
            WHERE user_id = %s
            """,
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
                user_id,
                language,
                first_seen,
                last_seen
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                language = EXCLUDED.language,
                last_seen = EXCLUDED.last_seen
            """,
            (
                int(user_id),
                lang,
                now,
                now,
            ),
        )


def _generate_post_code(conn) -> str:
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(
            secrets.choice(alphabet)
            for _ in range(6)
        )

        exists = conn.execute(
            "SELECT 1 FROM posts WHERE code = %s",
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
    entities=None,
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
            "entities": entities,
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
                entities_json,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                code,
                int(user_id),
                name,
                caption or "",
                _json(media),
                _json(buttons),
                str(target) if target is not None else None,
                _json(entities),
                now_iso(),
            ),
        )

    return post


def _row_to_post(row) -> dict:
    return {
        "code": row["code"],
        "user_id": int(row["user_id"]),
        "name": row["name"],
        "caption": row["caption"] or "",
        "media": _from_json(row["media_json"]),
        "buttons": _from_json(row["buttons_json"]),
        "target": row["target"],
        "entities": _from_json(row["entities_json"]) if "entities_json" in row else None,
        "created_at": row["created_at"],
    }


def get_user_posts(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM posts
            WHERE user_id = %s
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
            WHERE code = %s
              AND user_id = %s
            """,
            (
                code.upper(),
                int(user_id),
            ),
        ).fetchone()

    return _row_to_post(row) if row else None


def delete_post(user_id: int, code: str) -> bool:
    with connect() as conn:
        result = conn.execute(
            """
            DELETE FROM posts
            WHERE code = %s
              AND user_id = %s
            """,
            (
                code.upper(),
                int(user_id),
            ),
        )

    return result.rowcount > 0


def increment_posts_created(user_id: int) -> None:
    now = now_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(
                user_id,
                first_seen,
                last_seen,
                posts_created
            )
            VALUES (%s, %s, %s, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                posts_created = users.posts_created + 1,
                last_seen = EXCLUDED.last_seen
            """,
            (
                int(user_id),
                now,
                now,
            ),
        )


def increment_posts_sent(user_id: int) -> None:
    now = now_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(
                user_id,
                first_seen,
                last_seen,
                posts_sent
            )
            VALUES (%s, %s, %s, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                posts_sent = users.posts_sent + 1,
                last_seen = EXCLUDED.last_seen
            """,
            (
                int(user_id),
                now,
                now,
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
            VALUES (%s, %s, %s, %s, %s)
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
            VALUES (%s, %s, %s, %s, %s)
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(chat_id) DO UPDATE SET
                type = EXCLUDED.type,
                title = EXCLUDED.title,
                username = EXCLUDED.username,
                status = COALESCE(
                    EXCLUDED.status,
                    chats.status
                ),
                last_seen = EXCLUDED.last_seen,
                last_user_id = COALESCE(
                    EXCLUDED.last_user_id,
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


def set_blocked(
    user_id: int,
    blocked: bool = True,
) -> None:
    with connect() as conn:
        if blocked:
            conn.execute(
                """
                INSERT INTO blocked_users(user_id)
                VALUES (%s)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (int(user_id),),
            )
        else:
            conn.execute(
                """
                DELETE FROM blocked_users
                WHERE user_id = %s
                """,
                (int(user_id),),
            )


def is_blocked(user_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM blocked_users
            WHERE user_id = %s
            """,
            (int(user_id),),
        ).fetchone()

    return row is not None


def get_setting(name: str, default=None):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT value
            FROM settings
            WHERE key = %s
            """,
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
            VALUES (%s, %s)
            ON CONFLICT(key) DO UPDATE SET
                value = EXCLUDED.value
            """,
            (
                name,
                str(value),
            ),
        )


def get_users(limit: int | None = None) -> list[dict]:
    query = """
        SELECT *
        FROM users
        ORDER BY last_seen DESC
    """

    params = ()

    if limit is not None:
        query += " LIMIT %s"
        params = (int(limit),)

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_all_user_ids() -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id
            FROM users
            ORDER BY user_id
            """
        ).fetchall()

    return [int(row["user_id"]) for row in rows]


def get_posts(limit: int | None = None) -> list[dict]:
    query = """
        SELECT *
        FROM posts
        ORDER BY created_at DESC
    """

    params = ()

    if limit is not None:
        query += " LIMIT %s"
        params = (int(limit),)

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_post(row) for row in rows]


def get_chats(limit: int | None = None) -> list[dict]:
    query = """
        SELECT *
        FROM chats
        ORDER BY last_seen DESC
    """

    params = ()

    if limit is not None:
        query += " LIMIT %s"
        params = (int(limit),)

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_events(limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM events
            ORDER BY id DESC
            LIMIT %s
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
            LIMIT %s
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
            VALUES (%s, %s, %s, %s, %s)
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
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()

    return [dict(row) for row in rows]


def get_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            "users": conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()["count"],
            "posts": conn.execute(
                "SELECT COUNT(*) FROM posts"
            ).fetchone()["count"],
            "chats": conn.execute(
                "SELECT COUNT(*) FROM chats"
            ).fetchone()["count"],
            "events": conn.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()["count"],
            "errors": conn.execute(
                "SELECT COUNT(*) FROM errors"
            ).fetchone()["count"],
            "blocked": conn.execute(
                "SELECT COUNT(*) FROM blocked_users"
            ).fetchone()["count"],
        }


def get_user(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = %s
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
                WHERE user_id = %s
                """,
                (int(query),),
            ).fetchall()
        else:
            pattern = f"%{query.lower()}%"

            rows = conn.execute(
                """
                SELECT *
                FROM users
                WHERE LOWER(COALESCE(username, '')) LIKE %s
                   OR LOWER(COALESCE(first_name, '')) LIKE %s
                   OR LOWER(COALESCE(last_name, '')) LIKE %s
                ORDER BY last_seen DESC
                LIMIT 50
                """,
                (
                    pattern,
                    pattern,
                    pattern,
                ),
            ).fetchall()

    return [dict(row) for row in rows]


def get_database_size() -> int:
    try:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT pg_database_size(current_database())
                """
            ).fetchone()

        return int(row["pg_database_size"])

    except Exception:
        return 0
