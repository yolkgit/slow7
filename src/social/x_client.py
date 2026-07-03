"""X (트위터) 자동 게시 — API v2 + OAuth 1.0a.

토큰 발급: https://developer.x.com → 앱 생성 → Keys and tokens
필요: API Key/Secret + Access Token/Secret (User 권한, Read and Write)
무료 티어도 쓰기(POST) 월 500개까지 가능.
"""
from __future__ import annotations

import requests
from requests_oauthlib import OAuth1

from .. import config


def _auth() -> OAuth1:
    return OAuth1(
        config.X_API_KEY,
        config.X_API_SECRET,
        config.X_ACCESS_TOKEN,
        config.X_ACCESS_SECRET,
    )


def post(text: str) -> str:
    """트윗 게시. tweet id 반환."""
    resp = requests.post(
        "https://api.twitter.com/2/tweets",
        auth=_auth(),
        json={"text": text},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"X 게시 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("data", {}).get("id", "")


def verify() -> dict:
    """인증 확인 — 내 계정 정보."""
    resp = requests.get(
        "https://api.twitter.com/2/users/me",
        auth=_auth(),
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"X 인증 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json()
