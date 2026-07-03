"""스레드 자동 게시 (재도전용) — Threads Graph API.

⚠️ 지난 계정 정지 이력. 새 인스타 계정 + 새 앱으로만. 자동 게시만(답글 X).
2단계: container 생성 → publish.
"""
from __future__ import annotations

import time

import requests

from .. import config

BASE = "https://graph.threads.net/v1.0"


def post(text: str) -> str:
    uid = config.THREADS_PROMO_USER_ID
    token = config.THREADS_PROMO_TOKEN

    r = requests.post(
        f"{BASE}/{uid}/threads",
        data={"media_type": "TEXT", "text": text, "access_token": token},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Threads container 실패 {r.status_code}: {r.text[:300]}")
    creation_id = r.json()["id"]

    time.sleep(3)  # container 준비 대기
    r2 = requests.post(
        f"{BASE}/{uid}/threads_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    if r2.status_code >= 400:
        raise RuntimeError(f"Threads publish 실패 {r2.status_code}: {r2.text[:300]}")
    return r2.json().get("id", "")
