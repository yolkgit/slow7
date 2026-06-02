"""Threads Graph API 래퍼.

문서: https://developers.facebook.com/docs/threads
2단계 흐름: (1) container 생성 → (2) publish
"""
from __future__ import annotations

import time
from typing import Any

import requests

from . import config

BASE = "https://graph.threads.net/v1.0"


class ThreadsError(RuntimeError):
    pass


def _req(method: str, path: str, params: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> dict:
    params = dict(params or {})
    params["access_token"] = config.THREADS_ACCESS_TOKEN
    url = f"{BASE}{path}"
    resp = requests.request(method, url, params=params, data=data, timeout=30)
    if resp.status_code >= 400:
        raise ThreadsError(f"{method} {path} -> {resp.status_code}: {resp.text}")
    return resp.json()


# --------------------- 게시 ---------------------

def _create_text_container(text: str, reply_to_id: str | None = None) -> str:
    data = {"media_type": "TEXT", "text": text}
    if reply_to_id:
        data["reply_to_id"] = reply_to_id
    r = _req("POST", f"/{config.THREADS_USER_ID}/threads", data=data)
    return r["id"]


def _create_image_container(text: str, image_url: str, reply_to_id: str | None = None) -> str:
    data = {"media_type": "IMAGE", "image_url": image_url, "text": text}
    if reply_to_id:
        data["reply_to_id"] = reply_to_id
    r = _req("POST", f"/{config.THREADS_USER_ID}/threads", data=data)
    return r["id"]


def _publish(creation_id: str) -> str:
    # 컨테이너 상태가 FINISHED 될 때까지 잠깐 대기 (이미지일 때 필요할 수 있음)
    for _ in range(10):
        st = _req("GET", f"/{creation_id}", params={"fields": "status,error_message"})
        if st.get("status") in ("FINISHED", None):
            break
        if st.get("status") == "ERROR":
            raise ThreadsError(f"container error: {st.get('error_message')}")
        time.sleep(2)
    r = _req("POST", f"/{config.THREADS_USER_ID}/threads_publish", data={"creation_id": creation_id})
    return r["id"]


def publish_post(text: str, image_url: str | None = None) -> str:
    """텍스트 또는 이미지+텍스트 게시. media_id 반환."""
    if config.DRY_RUN:
        print(f"[DRY_RUN] publish_post text=[{text}] image_url={image_url}")
        return "dry-run-id"
    if image_url:
        cid = _create_image_container(text, image_url)
    else:
        cid = _create_text_container(text)
    return _publish(cid)


def publish_reply(parent_id: str, text: str) -> str:
    """다른 게시물(또는 댓글)에 답글."""
    if config.DRY_RUN:
        print(f"[DRY_RUN] reply to {parent_id}: {text}")
        return "dry-run-reply"
    cid = _create_text_container(text, reply_to_id=parent_id)
    return _publish(cid)


# --------------------- 조회 ---------------------

def fetch_conversation(post_id: str) -> list[dict]:
    """특정 게시물의 모든 답글(중첩 포함)을 평탄화해서 반환.

    각 항목: {id, text, username, timestamp, replied_to: {id}}
    """
    fields = "id,text,username,timestamp,replied_to,from"
    r = _req("GET", f"/{post_id}/conversation", params={"fields": fields, "reverse": "true"})
    return r.get("data", [])


def fetch_user_posts(limit: int = 10) -> list[dict]:
    fields = "id,text,timestamp,permalink"
    r = _req("GET", f"/{config.THREADS_USER_ID}/threads", params={"fields": fields, "limit": limit})
    return r.get("data", [])


def search_topic(query: str, search_type: str = "TOP", limit: int = 20) -> list[dict]:
    """키워드 검색. search_type: TOP | RECENT.

    참고: keyword_search 권한 필요. 권한 없으면 빈 리스트 반환.
    """
    try:
        fields = "id,text,username,permalink,timestamp"
        r = _req(
            "GET",
            "/keyword_search",
            params={"q": query, "search_type": search_type, "fields": fields, "limit": limit},
        )
        return r.get("data", [])
    except ThreadsError:
        return []


def me() -> dict:
    return _req("GET", "/me", params={"fields": "id,username,threads_profile_picture_url"})
