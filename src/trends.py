"""러닝 쪽 요즘 화제 모으기 — 스레드 글에 '이슈·이벤트' 재료로 쓴다.

두 군데서 모은다 (둘 다 실패해도 빈 목록으로 조용히 넘어감).
    1) 스레드 키워드 검색 (graph.threads.net /keyword_search, 게시용 토큰)
       — 앱에 threads_keyword_search 권한이 있어야 남의 글이 나온다. 없으면 빈 결과.
    2) 구글 뉴스 RSS (무료, 키 없음) — 최근 2일 러닝·마라톤 기사 제목.

결과를 그대로 베끼지 않고 "요즘 이런 얘기가 돈다" 정도의 힌트로만 넘긴다.
"""
from __future__ import annotations

import email.utils
import html
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote

import requests

from . import config

THREADS_QUERIES = ["러닝", "러닝크루", "마라톤", "달리기"]
NEWS_QUERY = "러닝 OR 마라톤 OR 러닝크루 OR 달리기"
NEWS_MAX_AGE_H = 48

# 기사 제목에 이런 말이 있으면 러닝 화제가 아닐 가능성이 큼 (주식 '러닝메이트' 등)
_NOISE = re.compile(r"러닝메이트|런닝맨|러닝머신 판매|주가|증시|코인|선거|후보")


@dataclass
class Issue:
    source: str    # "threads" | "news"
    text: str      # 한 줄 요약 재료 (게시글 앞부분이나 기사 제목)
    key: str       # 중복 방지용 키
    ts: float      # 작성 시각 (epoch)


def _norm_key(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)[:40]


def threads_search(limit: int = 10) -> list[Issue]:
    token = config.THREADS_PROMO_TOKEN
    if not token:
        return []
    out: list[Issue] = []
    for q in THREADS_QUERIES:
        try:
            r = requests.get(
                "https://graph.threads.net/v1.0/keyword_search",
                params={"q": q, "search_type": "TOP", "limit": limit,
                        "fields": "id,text,timestamp", "access_token": token},
                timeout=20,
            )
            if r.status_code >= 400:
                print(f"[trends] 스레드 검색 안 됨 ({r.status_code}) — 권한 없으면 정상: {r.text[:120]}")
                return out
            data = r.json().get("data", [])
        except Exception as e:
            print(f"[trends] 스레드 검색 실패: {e}")
            return out
        for d in data:
            text = re.sub(r"\s+", " ", (d.get("text") or "")).strip()
            if len(text) < 15:
                continue
            ts = time.time()
            try:
                ts = time.mktime(time.strptime(d.get("timestamp", "")[:19], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                pass
            out.append(Issue("threads", text[:120], "t:" + str(d.get("id")), ts))
    return out


def news_rss(max_items: int = 15) -> list[Issue]:
    url = ("https://news.google.com/rss/search?q=" + quote(f"{NEWS_QUERY} when:2d")
           + "&hl=ko&gl=KR&ceid=KR:ko")
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"[trends] 뉴스 RSS 실패: {e}")
        return []
    now = time.time()
    out: list[Issue] = []
    for item in root.iter("item"):
        title = html.unescape(item.findtext("title") or "").strip()
        # "제목 - 언론사" 꼴에서 언론사 떼기
        title = re.sub(r"\s+-\s+[^-]+$", "", title)
        if not title or _NOISE.search(title):
            continue
        try:
            ts = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "").timestamp()
        except (TypeError, ValueError):
            ts = now
        if now - ts > NEWS_MAX_AGE_H * 3600:
            continue
        out.append(Issue("news", title, "n:" + _norm_key(title), ts))
        if len(out) >= max_items:
            break
    return out


def collect(used_keys: set[str]) -> list[Issue]:
    """아직 안 쓴 화제 목록 (최신순)."""
    items = threads_search() + news_rss()
    seen: set[str] = set()
    fresh = []
    for it in sorted(items, key=lambda x: -x.ts):
        if it.key in used_keys or it.key in seen:
            continue
        seen.add(it.key)
        fresh.append(it)
    return fresh
