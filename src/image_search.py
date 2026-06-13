"""Pexels 무료 사진 검색 — 본문 이미지용.

Pexels: 무료, 상업적 사용 가능, 출처 표기 권장(필수는 아님).
API 키 발급: https://www.pexels.com/api/ (이메일 가입, 무료)
키 없으면 모든 함수가 None 반환 → 본문 이미지 생략.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import requests

from . import config

# 슬로우조깅/러닝 글에 어울리는 영어 검색어 (Pexels는 영어가 결과 좋음)
QUERY_MAP = [
    ("jogging", ("조깅", "달리기", "러닝", "뛰")),
    ("running outdoor", ("야외", "공원", "코스")),
    ("morning run", ("아침", "출발", "시작")),
    ("runner stretching", ("스트레칭", "워밍업", "준비")),
    ("healthy lifestyle", ("건강", "다이어트", "체중")),
    ("running shoes", ("신발", "러닝화")),
    ("heart rate fitness", ("심박", "존2", "유산소")),
]


def _pick_query(topic_title: str, tags: list[str]) -> str:
    """주제·태그에 맞는 Pexels 검색어 선택."""
    haystack = topic_title + " " + " ".join(tags)
    for en, kos in QUERY_MAP:
        if any(k in haystack for k in kos):
            return en
    return "jogging"  # 기본


def search_and_download(topic_title: str, tags: list[str]) -> dict | None:
    """사진 1장 검색 → 임시파일로 다운로드.

    반환: {path, photographer, photographer_url, alt} 또는 None
    """
    if not config.PEXELS_API_KEY:
        return None

    query = _pick_query(topic_title, tags)
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": "landscape", "per_page": 15, "size": "medium"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[pexels] 검색 실패 {resp.status_code}: {resp.text[:150]}")
            return None
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"[pexels] '{query}' 결과 없음")
            return None

        # 매번 다른 사진 쓰도록 약간 랜덤
        import random
        photo = random.choice(photos[:10])
        img_url = photo["src"].get("large") or photo["src"].get("medium")
        photographer = photo.get("photographer", "Pexels")
        photographer_url = photo.get("photographer_url", "https://www.pexels.com")

        # 다운로드
        img_resp = requests.get(img_url, timeout=60)
        if img_resp.status_code != 200:
            return None
        tmp = Path(tempfile.gettempdir()) / f"pexels_{photo['id']}.jpg"
        tmp.write_bytes(img_resp.content)

        return {
            "path": tmp,
            "photographer": photographer,
            "photographer_url": photographer_url,
            "alt": f"{topic_title} - 슬로우조깅 이미지",
            "query": query,
        }
    except Exception as e:
        print(f"[pexels] 오류(무시): {e}")
        return None
