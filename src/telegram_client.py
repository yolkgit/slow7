"""Telegram Bot API 클라이언트 — 검수 알림 + 사용자 응답 수신.

봇 생성: BotFather에서 /newbot → 토큰
chat_id: 봇과 대화 시작 후 getUpdates로 확인 (scripts/tg_check.py)
"""
from __future__ import annotations

from typing import Any

import requests

from . import config


class TelegramError(RuntimeError):
    pass


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"


def send_message(text: str, chat_id: str | None = None, parse_mode: str = "HTML") -> dict:
    """메시지 전송. parse_mode HTML 지원 (<b>, <a> 등)."""
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if config.DRY_RUN:
        print(f"[DRY_RUN] telegram send: {text[:120]}")
        return {"ok": True}
    resp = requests.post(
        _api("sendMessage"),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise TelegramError(f"sendMessage 실패: {data}")
    return data["result"]


def get_updates(offset: int | None = None, timeout: int = 0) -> list[dict]:
    """새 메시지 폴링. offset = 마지막으로 처리한 update_id + 1."""
    params: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(_api("getUpdates"), params=params, timeout=timeout + 30)
    data = resp.json()
    if not data.get("ok"):
        raise TelegramError(f"getUpdates 실패: {data}")
    return data.get("result", [])


def get_me() -> dict:
    resp = requests.get(_api("getMe"), timeout=30)
    data = resp.json()
    if not data.get("ok"):
        raise TelegramError(f"getMe 실패: {data}")
    return data["result"]
