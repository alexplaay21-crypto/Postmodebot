# -*- coding: utf-8 -*-
"""Simple JSON persistence for users and saved posts."""

import json
import os
import secrets
import string
from threading import Lock

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_FILE = os.path.join(DATA_DIR, "users.json")
POSTS_FILE = os.path.join(DATA_DIR, "posts.json")

_lock = Lock()


def _ensure_file(path: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def _read(path: str) -> dict:
    _ensure_file(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
        code = "".join(secrets.choice(alphabet) for _ in range(6))
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

    result.sort(key=lambda item: item.get("name", "").lower())
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
        post = posts.get(code.upper())

        if not post:
            return False

        if int(post.get("user_id", 0)) != int(user_id):
            return False

        del posts[code.upper()]
        _write(POSTS_FILE, posts)
        return True
