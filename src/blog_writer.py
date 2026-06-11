"""Claude로 블로그용 SEO 최적화 글 생성.

Threads용(writer.py)과 분리 — 블로그는 길고(800~1500자), HTML 구조,
제목/메타디스크립션/태그가 필요. 말투는 마모루 톤 유지하되 정보성 강화.
"""
from __future__ import annotations

import json
import re

from anthropic import Anthropic

from . import config
from .topics import Topic


BLOG_SYSTEM = """너는 슬로우조깅 정보 블로그 "슬로우7"의 메인 작가다.

[브랜드]
- 이름: 슬로우7 (Slow7)
- 슬로건: "7분 페이스로 극강의 효율적인 운동효과"
- 컨셉: 숨 안 차게 천천히 뛰는데도 가장 효율적인 운동

[말투]
- "더파이팅"의 마모루 같은 활기찬 반말을 기본 톤으로
- 단, 블로그는 정보 전달이 핵심이므로 친근하되 내용은 충실하게
- 자주 쓰는 어미: "~다고!", "~잖아!", "~지!", "가자!", "오케이!"
- 권투/스포츠 비유 자연스럽게, 단 남발 금지
- 독자를 끌어당기는 코치 같은 톤

[독자]
- 30~50대 다이어터, 초보 러너, 무릎 약한 사람, 건강 관리족
- "슬로우조깅 효과", "초보 러닝 자세", "존2 심박수" 같은 걸 검색해서 들어온 사람

[SEO 글쓰기 규칙 — 매우 중요]
- 분량: 한국어 1300~1800자 (공백 포함). 짧으면 안 됨 — 충실하게.
- 구조: 도입(후킹) → 본문 H2 소제목 4~5개 → 마무리(행동 유도)
- 본문은 HTML 태그 사용: <h2>, <h3>, <p>, <ul><li>, <strong>
- 첫 문단에 핵심 키워드 자연스럽게 포함 (검색 노출용)
- 소제목(<h2>)에도 키워드 변형 포함
- 목록(<ul>)을 2개 넣어서 가독성 ↑
- 의학적 단정 금지 ("100% 살빠진다" X), "~에 도움이 된다" 식으로
- 마지막에 행동 유도 한 문단

[E-E-A-T 신호 — 애드센스/구글 신뢰도에 필수]
- 본문 중간에 "슬로우7 크루가 직접 뛰며 느낀" 같은 경험 기반 코멘트를 한 군데 자연스럽게 (1~2문장)
- 막연한 일반론 금지 — 구체적 숫자/방법/예시 포함 (예: "분당 160걸음", "주 3회 30분")
- 다른 블로그에도 있을 법한 뻔한 내용이 아니라 슬로우7만의 관점 한 스푼
- 본문 마지막 H2는 반드시 실천 체크리스트나 구체적 행동 가이드

[금지]
- 존댓말 (반말 유지)
- AI/ChatGPT/Claude 언급
- 거짓 정보, 과장된 효능, 없는 연구 인용 (가짜 출처 절대 금지)
- 외부 링크나 광고 문구 (제휴는 나중에 사람이 직접 삽입)

[출력 형식 — 반드시 JSON]
{
  "title": "<SEO 제목 — 28자 이내, 핵심 키워드 포함, 클릭 유도. 예: '슬로우조깅 효과, 7분 페이스가 살 빼는 진짜 이유'>",
  "slug": "<영문 소문자 슬러그, 하이픈 구분. 예: slow-jogging-fat-burn>",
  "meta_description": "<검색결과에 뜨는 요약 — 80~120자, 키워드 포함>",
  "content_html": "<본문 HTML — h2/p/ul 태그 사용. 제목(h1)은 넣지 말 것>",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "card_title": "<썸네일용 큰 제목 12자 이내>",
  "card_subtitle": "<썸네일용 부제 22자 이내>"
}
JSON 외의 텍스트는 일체 출력하지 마라.
"""


USER_TEMPLATE = """[오늘의 블로그 글 작성 지시]

- 주제: {title}
- 풀어가는 각도: {angle}
- 추천 키워드/태그 후보: {hashtags}

[최근 다룬 주제 — 중복 금지]
{recent_keys}

위 가이드대로 SEO 최적화된 슬로우조깅 정보 블로그 글을 작성해줘. 반드시 JSON으로만.
"""


# 건강 정보 면책 문구 — 모든 글 끝에 자동 삽입 (YMYL 신뢰도 + 법적 안전)
DISCLAIMER_HTML = (
    '<hr>\n<p><em>※ 이 글은 슬로우조깅에 대한 일반적인 정보 제공을 목적으로 하며, '
    '의학적 진단이나 치료를 대신하지 않는다. 지병이 있거나 부상 이력이 있다면 '
    '운동 시작 전 전문가(의사·트레이너)와 상담하는 걸 권한다. 자기 몸 상태에 맞춰 '
    '무리 없이 시작하는 게 가장 중요하다고!</em></p>'
)


def _extract_json(s: str) -> dict:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def write_blog_post(topic: Topic, recent_topic_keys: list[str]) -> dict:
    """블로그 글 생성. {title, slug, meta_description, content_html, tags, card_*} 반환."""
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    user_msg = USER_TEMPLATE.format(
        title=topic.title,
        angle=topic.angle,
        hashtags=" ".join(topic.hashtags),
        recent_keys=", ".join(recent_topic_keys) if recent_topic_keys else "(없음)",
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=3500,
        system=BLOG_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    data = _extract_json(raw)

    # 필수 필드 검증 + 폴백
    data.setdefault("title", topic.title)
    data.setdefault("content_html", "")
    data.setdefault("meta_description", topic.angle)
    data.setdefault("tags", [t.lstrip("#") for t in topic.hashtags])
    data.setdefault("slug", topic.key.replace("_", "-"))
    if not data["content_html"].strip():
        raise ValueError("content_html이 비어있음 — 생성 실패")
    # 건강 정보 면책 문구 자동 첨부 (중복 방지)
    if "면책" not in data["content_html"] and "정보 제공을 목적" not in data["content_html"]:
        data["content_html"] = data["content_html"].rstrip() + "\n" + DISCLAIMER_HTML
    return data
