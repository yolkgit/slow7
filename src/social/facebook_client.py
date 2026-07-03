"""페이스북 페이지 자동 게시 — Graph API.

토큰 발급: developers.facebook.com → 앱 → 페이지 액세스 토큰 (장기)
필요 권한: pages_manage_posts, pages_read_engagement
페이지 게시는 자동화 정식 지원 (개인 프로필은 API 게시 불가).
"""
from __future__ import annotations

import requests

from .. import config

GRAPH = "https://graph.facebook.com/v21.0"


def post(text: str) -> str:
    """페이지 피드에 게시. 링크는 text 안에 포함돼 있어도 자동 미리보기됨. post id 반환."""
    resp = requests.post(
        f"{GRAPH}/{config.FB_PAGE_ID}/feed",
        data={"message": text, "access_token": config.FB_PAGE_TOKEN},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"FB 게시 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("id", "")


def verify() -> dict:
    """페이지 정보 확인."""
    resp = requests.get(
        f"{GRAPH}/{config.FB_PAGE_ID}",
        params={"fields": "id,name,fan_count", "access_token": config.FB_PAGE_TOKEN},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"FB 인증 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json()
