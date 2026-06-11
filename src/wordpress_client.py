"""WordPress REST API 클라이언트.

인증: Application Password (워드프레스 5.6+ 내장 기능).
문서: https://developer.wordpress.org/rest-api/

흐름:
    1) (선택) 카테고리/태그 ID 확보 (없으면 생성)
    2) (선택) 대표 이미지 업로드 → media ID
    3) 글 발행 (POST /wp/v2/posts)
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from . import config


class WordPressError(RuntimeError):
    pass


def _auth() -> HTTPBasicAuth:
    # Application Password는 공백이 포함된 형태(xxxx xxxx xxxx)지만 그대로 사용 가능
    return HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)


def _api(path: str) -> str:
    return f"{config.WP_SITE_URL}/wp-json/wp/v2/{path.lstrip('/')}"


def _req(method: str, path: str, **kwargs) -> Any:
    url = _api(path)
    resp = requests.request(method, url, auth=_auth(), timeout=30, **kwargs)
    if resp.status_code >= 400:
        raise WordPressError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
    return resp.json()


# --------------------- 분류 (카테고리/태그) ---------------------

def _ensure_term(taxonomy: str, name: str) -> int:
    """카테고리(categories) 또는 태그(tags) 이름으로 ID 확보. 없으면 생성."""
    # 검색
    found = _req("GET", f"{taxonomy}", params={"search": name, "per_page": 100})
    for t in found:
        if t.get("name", "").strip().lower() == name.strip().lower():
            return t["id"]
    # 생성
    try:
        created = _req("POST", f"{taxonomy}", json={"name": name})
        return created["id"]
    except WordPressError as e:
        # 동시 생성 충돌 등 — 다시 검색
        found = _req("GET", f"{taxonomy}", params={"search": name, "per_page": 100})
        for t in found:
            if t.get("name", "").strip().lower() == name.strip().lower():
                return t["id"]
        raise


def ensure_category(name: str) -> int:
    return _ensure_term("categories", name)


def ensure_tags(names: list[str]) -> list[int]:
    ids: list[int] = []
    for n in names:
        n = n.strip().lstrip("#")
        if not n:
            continue
        try:
            ids.append(_ensure_term("tags", n))
        except WordPressError as e:
            print(f"[wp] 태그 '{n}' 처리 실패(무시): {e}")
    return ids


# --------------------- 미디어 ---------------------

def upload_media(image_path: Path, alt_text: str = "") -> int:
    """대표 이미지 업로드 → media ID."""
    if config.DRY_RUN:
        print(f"[DRY_RUN] upload_media {image_path}")
        return 0
    filename = image_path.name
    mime = mimetypes.guess_type(filename)[0] or "image/png"
    with open(image_path, "rb") as f:
        data = f.read()
    url = _api("media")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": mime,
    }
    resp = requests.post(url, auth=_auth(), headers=headers, data=data, timeout=60)
    if resp.status_code >= 400:
        raise WordPressError(f"media upload -> {resp.status_code}: {resp.text[:300]}")
    media_id = resp.json()["id"]
    # alt 텍스트 설정 (SEO)
    if alt_text:
        try:
            _req("POST", f"media/{media_id}", json={"alt_text": alt_text})
        except WordPressError:
            pass
    return media_id


# --------------------- 글 발행 ---------------------

def create_post(
    title: str,
    content_html: str,
    excerpt: str = "",
    category: str | None = None,
    tags: list[str] | None = None,
    featured_media_id: int | None = None,
    status: str | None = None,
    slug: str | None = None,
) -> dict:
    """글 발행. 발행된 글 정보(dict) 반환 ({id, link, ...})."""
    status = status or config.WP_POST_STATUS
    if config.DRY_RUN:
        print(f"[DRY_RUN] create_post title=[{title}] status={status} tags={tags}")
        return {"id": 0, "link": "(dry-run)"}

    payload: dict[str, Any] = {
        "title": title,
        "content": content_html,
        "status": status,
    }
    if excerpt:
        payload["excerpt"] = excerpt
    if slug:
        payload["slug"] = slug
    if category:
        payload["categories"] = [ensure_category(category)]
    if tags:
        payload["tags"] = ensure_tags(tags)
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    return _req("POST", "posts", json=payload)


def update_post(
    post_id: str | int,
    title: str | None = None,
    content_html: str | None = None,
    status: str | None = None,
) -> dict:
    """기존 글 수정. 제목/본문/상태 중 준 것만 갱신."""
    if config.DRY_RUN:
        print(f"[DRY_RUN] update_post {post_id} status={status}")
        return {"id": post_id, "link": "(dry-run)"}
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if content_html is not None:
        payload["content"] = content_html
    if status is not None:
        payload["status"] = status
    return _req("POST", f"posts/{post_id}", json=payload)


def whoami() -> dict:
    """인증 확인용 — 현재 사용자 정보."""
    url = f"{config.WP_SITE_URL}/wp-json/wp/v2/users/me"
    resp = requests.get(url, auth=_auth(), timeout=30)
    if resp.status_code >= 400:
        raise WordPressError(f"whoami -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()
