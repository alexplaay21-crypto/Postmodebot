# -*- coding: utf-8 -*-
"""JSON persistence for users and saved posts with safe atomic writes."""

import json
import os
import secrets
import shutil
import string
from json import JSONDecodeError
from threading import Lock

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

DATA_FILE = os.path.join(DATA_DIR, "users.json")
POSTS_FILE = os.path.join(DATA_DIR, "posts.json")

_lock = Lock()


def _ensure_file(path: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(path):
        _atomic_write(path, {})


def _atomic_write(path: str, data: dict) -> None:
    """
    Safely write JSON:
    1. write to temporary file
    2. flush data to disk
    3. replace original atomically
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    temp_path = f"{path}.tmp"
    backup_path = f"{path}.bak"

    # Keep a backup of the current valid file.
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)

            shutil.copy2(path, backup_path)
        except (OSError, JSONDecodeError):
            pass

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, path)


def _read(path: str) -> dict:
    _ensure_file(path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except JSONDecodeError:
        backup_path = f"{path}.bak"

        # Try recovering from the previous valid version.
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Restore the valid backup atomically.
                _atomic_write_without_backup(path, data)

                return data

            except (OSError, JSONDecodeError):
                pass

        # If there is no usable backup, fail explicitly.
        raise


def _atomic_write_without_backup(path: str, data: dict) -> None:
    """Atomic write used during recovery to avoid overwriting the backup."""
    os.makedirs(DATA_DIR, exist_ok=True)

    temp_path = f"{path}.recover.tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, path)


def _write(path: str, data: dict) -> None:
    _atomic_write(path, data)


def get_user_language(user_id: int, fallback: str) -> str:
    with _lock:
        data = _read(DATA_FILE)
        return data.get(str(user_id), fallback)


def set_user_language(user_id: int, lang: str) -> None:
    with _lock:
        data = _read(DATA_FILE)
        data[str(user_id)] = lang
        _write(DATA_FILE, data)


def _generate_post_code(posts: dict) -> str:
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(
            secrets.choice(alphabet)
            for _ in range(6)
        )

        if code not in posts:
            return code


def save_post(
    user_id: int,
    name: str,
    caption: str,
    media,
    buttons,
    target,
) -> dict:
    with _lock:
        posts = _read(POSTS_FILE)

        code = _generate_post_code(posts)

        post = {
            "code": code,
            "user_id": int(user_id),
            "name": name,
            "caption": caption or "",
            "media": media,
            "buttons": buttons,
            "target": target,
        }

        posts[code] = post

        _write(POSTS_FILE, posts)

        return post


def get_user_posts(user_id: int) -> list[dict]:
    with _lock:
        posts = _read(POSTS_FILE)

    result = [
        post
        for post in posts.values()
        if int(post.get("user_id", 0)) == int(user_id)
    ]

    result.sort(
        key=lambda item: item.get("name", "").lower()
    )

    return result


def get_post(user_id: int, code: str) -> dict | None:
    with _lock:
        posts = _read(POSTS_FILE)

    post = posts.get(code.upper())

    if not post:
        return None

    if int(post.get("user_id", 0)) != int(user_id):
        return None

    return post


def delete_post(user_id: int, code: str) -> bool:
    with _lock:
        posts = _read(POSTS_FILE)

        code = code.upper()
        post = posts.get(code)

        if not post:
            return False

        if int(post.get("user_id", 0)) != int(user_id):
            return False

        del posts[code]

        _write(POSTS_FILE, posts)

        return True
