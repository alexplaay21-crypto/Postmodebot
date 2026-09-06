# -*- coding: utf-8 -*-
"""
Minimal persistence layer — no database required.
Stores each user's chosen interface language in data/users.json.
"""
import json
import os
from threading import Lock

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_FILE = os.path.join(DATA_DIR, "users.json")
_lock = Lock()


def _ensure_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _read() -> dict:
    _ensure_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_language(user_id: int, fallback: str) -> str:
    with _lock:
        data = _read()
        return data.get(str(user_id), fallback)


def set_user_language(user_id: int, lang: str) -> None:
    with _lock:
        data = _read()
        data[str(user_id)] = lang
        _write(data)
