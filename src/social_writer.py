"""블로그 글 → SNS 홍보글 생성.

플랫폼별 길이·스타일에 맞춰 마모루 톤 홍보글 + 블로그 링크.
목적: 클릭 유도해서 블로그로 유입.
"""
from __future__ import annotations

import json
import re

from anthropic import Anthropic

from . import config

# 플랫폼별 글자수 제한 (링크·해시태그 여유 고려한 본문 목표)
LIMITS = {
    "x": 230,           # 280자 - 링크(약 23) - 여유
    "facebook": 400,
    "threads": 450,     # 500자 제한
    "instagram": 300,
}

PROMO_SYSTEM = """너는 슬로우조깅 블로그 "슬로우7"의 SNS 홍보 담당이다.
블로그 글 제목·요약을 받아서, SNS에 올릴 짧은 홍보글을 쓴다. 목적은 클릭 유도.

[말투]
- "더파이팅" 마모루 같은 활기찬 반말. 짧고 강하게.
- 첫 줄에서 궁금증/공감 유발 (스크롤 멈추게)
- "~다고!", "~잖아!", "가자!" 같은 어미
- 이모지 1~2개 (🔥💪🏃⚡)

[홍보글 구조]
- 후킹 한 줄 (질문/통념깨기/충격)
- 핵심 한 줄 (블로그에서 뭘 얻는지)
- "자세한 건 아래 링크!" 같은 클릭 유도
- 해시태그 3~5개 (링크·본문과 별도 줄)

[금지]
- 낚시성 과장 ("충격!", "이것만 하면 10kg") 금지
- 존댓말 금지
- 링크는 본문에 넣지 마라 (코드가 따로 붙임)

[출력] 홍보글 본문만 출력. 링크는 넣지 말 것. 따옴표/JSON 없이 바로.
"""


def _clean(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```.*?\n", "", s)
    s = re.sub(r"\n```$", "", s)
    if (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    return s.strip()


NAVER_SYSTEM = """너는 슬로우조깅 블로그 "슬로우7"의 네이버 블로그 담당이다.
워드프레스에 발행된 글을 받아서, 네이버 블로그에 올릴 "요약 버전"을 새로 쓴다.

[가장 중요 — 중복 콘텐츠 방지]
- 원문 문장을 그대로 복사하지 마라. 같은 내용이라도 완전히 새로운 문장으로 다시 써라.
- 원문의 핵심 정보 중 2~3가지만 골라서 풀고, 나머지는 "전체 글에서" 라고 궁금증을 남겨라.

[네이버 블로그 스타일]
- 분량: 500~800자
- 문단은 1~3문장씩 짧게 끊고, 문단 사이 빈 줄
- 말투: 마모루 톤(활기찬 반말) 유지하되 네이버답게 살짝 부드럽게
- 이모지 2~3개 적당히
- 글 마지막에 "표/체크리스트가 포함된 전체 글은 아래 링크에서!" 같은 문장으로 마무리 (링크는 코드가 붙임)

[출력 형식 — 정확히 이대로]
제목: <네이버 검색 친화 제목 — 원문 제목과 다르게, 30자 이내>

<본문>

태그: #태그1 #태그2 #태그3 #태그4 #태그5

다른 설명 없이 위 형식만 출력.
"""


def write_naver_summary(title: str, content_html: str, blog_url: str) -> str:
    """네이버 블로그용 요약본 생성 (복붙용 완성 텍스트)."""
    text = re.sub(r"<[^>]+>", " ", content_html or "")
    text = re.sub(r"\s+", " ", text).strip()[:2500]
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    user_msg = (
        f"[원문 제목]\n{title}\n\n"
        f"[원문 내용]\n{text}\n\n"
        "위 글의 네이버 블로그용 요약 버전을 형식대로 작성해줘."
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1200,
        temperature=1.0,
        system=NAVER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    body = _clean("".join(b.text for b in msg.content if hasattr(b, "text")))
    return f"{body}\n\n👉 전체 글 보기: {blog_url}"


def write_promo(title: str, summary: str, platform: str, blog_url: str | None) -> str:
    """플랫폼용 글 생성.

    blog_url 있으면: 클릭 유도 홍보글 + 링크 첨부
    blog_url 없으면: 링크 없는 순수 정보 글 (자연스러운 계정 운영용)
    """
    limit = LIMITS.get(platform, 300)
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    if blog_url:
        user_msg = (
            f"[블로그 글 제목]\n{title}\n\n"
            f"[요약]\n{summary}\n\n"
            f"[플랫폼]\n{platform} (본문 {limit}자 이내)\n\n"
            f"{limit}자 이내로 홍보글 작성. 링크는 넣지 말고 본문만."
        )
    else:
        user_msg = (
            f"[주제]\n{title}\n\n"
            f"[핵심 내용]\n{summary}\n\n"
            f"[플랫폼]\n{platform} (본문 {limit}자 이내)\n\n"
            "⚠️ 이번 글에는 링크가 없다. 규칙:\n"
            "- '링크', '블로그', '자세한 건 아래' 같은 표현 절대 금지\n"
            "- 글 자체로 완결된 꿀팁 — 읽고 바로 써먹을 수 있게 핵심을 다 담아라\n"
            "- 마지막 줄은 가벼운 참여 유도 (질문이나 '오늘 해보자!' 같은 실천 제안)\n"
            f"{limit}자 이내로 본문만 출력."
        )

    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=400,
        temperature=1.0,
        system=PROMO_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    body = _clean("".join(b.text for b in msg.content if hasattr(b, "text")))
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0]

    if not blog_url:
        return body

    # 인스타는 링크 클릭이 안 되므로 안내 문구
    if platform == "instagram":
        return f"{body}\n\n👉 프로필 링크에서 전체 글 보기\n{blog_url}"
    return f"{body}\n\n{blog_url}"
