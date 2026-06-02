"""스레드 키워드 검색해서 트렌드 인사이트 뽑기.

Threads keyword_search API가 권한 없거나 막혀있으면 우아하게 빈 결과 반환.
검색 결과를 그대로 글에 박지 않고, 어떤 흐름인지 요약만 해서 writer에 힌트로 전달.
"""
from __future__ import annotations

from . import threads_client

SEED_QUERIES = [
    "슬로우조깅",
    "느린달리기",
    "존2러닝",
    "다이어트러닝",
    "초보러닝",
]


def fetch_trend_snippets(slot: str, limit_per_query: int = 5) -> list[str]:
    """오늘 시간대에 어울리는 키워드들을 돌면서 짧은 스니펫 모음을 가져온다."""
    snippets: list[str] = []
    for q in SEED_QUERIES:
        results = threads_client.search_topic(q, search_type="RECENT", limit=limit_per_query)
        for r in results:
            text = (r.get("text") or "").strip().replace("\n", " ")
            if not text:
                continue
            if len(text) > 120:
                text = text[:120] + "…"
            snippets.append(f"[{q}] {text}")
            if len(snippets) >= 15:
                return snippets
    return snippets
