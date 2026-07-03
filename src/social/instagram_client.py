"""인스타그램 비즈니스 자동 게시 — Graph API.

⚠️ 인스타는 이미지 필수 + 캡션 링크 클릭 안 됨 (유입엔 약함).
image_url이 있어야 게시 가능. 2단계: media container → publish.
"""
from __future__ import annotations

import time

import requests

from .. import config

GRAPH = "https://graph.facebook.com/v21.0"


def post(text: str, image_url: str | None = None) -> str:
    if not image_url:
        raise RuntimeError("인스타는 이미지 필수 — image_url 없음 (스킵)")

    uid = config.IG_USER_ID
    token = config.IG_ACCESS_TOKEN

    r = requests.post(
        f"{GRAPH}/{uid}/media",
        data={"image_url": image_url, "caption": text, "access_token": token},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"IG container 실패 {r.status_code}: {r.text[:300]}")
    creation_id = r.json()["id"]

    time.sleep(5)
    r2 = requests.post(
        f"{GRAPH}/{uid}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    if r2.status_code >= 400:
        raise RuntimeError(f"IG publish 실패 {r2.status_code}: {r2.text[:300]}")
    return r2.json().get("id", "")
