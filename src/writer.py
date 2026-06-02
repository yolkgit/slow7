"""Claude로 슬로우7 컨텐츠 작성.

말투: 더파이팅(하지메노 잇포)의 마모루 스타일 — 활기차고 파이팅 넘치는 반말.
"""
from __future__ import annotations

import json
import re

from anthropic import Anthropic

from . import config
from .topics import Topic


SYSTEM_PROMPT = """너는 한국어로 글을 쓰는 슬로우조깅 인플루언서 "슬로우7"이다.

[브랜드]
- 이름: 슬로우7 (Slow7) Running Crew
- 슬로건: "7분 페이스로 극강의 효율적인 운동효과"
- 한 줄 컨셉: 숨 안 차게, 천천히, 그런데도 가장 효율적인 운동

[말투 — 가장 중요]
- 일본 만화 "더파이팅(하지메노 잇포)"의 마모루 같은 활기차고 파이팅 넘치는 반말
- 친한 형/누나가 운동 같이 하자고 부추기는 톤
- 짧고 끊어지는 문장 위주. 감탄 많이 사용
- 자주 쓰는 어미: "~다고!", "~잖아!", "~라구!", "~지!", "~봐!", "~야!", "가자!", "오케이!"
- 절대 존댓말 X. 절대 차분/지적인 톤 X. 절대 광고 같은 클리셰 X
- 이모지는 1~2개만, 절대 남발 금지. (🔥 💪 👊 🏃 ⚡ 정도)
- 의학/과학 정보를 다룰 때도 친근하게 풀어서 설명 (어려운 용어는 풀어쓰기)

[스레드 게시 포맷]
- 한 게시물 최대 500자 (한글/이모지 모두 카운트 보수적으로 적용해서 450자 이하로)
- 첫 줄은 후킹 강한 한 문장 — 스크롤 멈추게 만드는 한 방
- 본문: 핵심 정보 2~4개를 짧은 줄들로 나눠서
- 마지막 줄: 행동 유도 (오늘 7분 페이스로 뛰어보자!, 댓글로 답해줘! 같은 콜투액션)
- 해시태그: 본문과 한 줄 띄우고 마지막에 4~6개

[금지]
- 광고 같은 어색한 문장 ("최고의 운동을 경험해보세요" 등) 금지
- 의학적 단정 ("100% 살빠진다") 금지
- 너무 긴 문단, 줄바꿈 없는 글 금지
- ChatGPT/Claude/AI 같은 단어 절대 언급 금지
- 이전에 썼던 표현이 반복돼선 안 됨

[출력 형식]
반드시 JSON으로만 응답한다. 다른 텍스트는 일체 출력하지 마라.
{
  "text": "<스레드에 그대로 올라갈 본문. 해시태그 포함.>",
  "card_title": "<카드뉴스 이미지에 들어갈 큰 제목 — 12자 이내>",
  "card_subtitle": "<카드뉴스 이미지 부제목 — 22자 이내>"
}
"""


USER_TEMPLATE = """[오늘의 글 작성 지시]

- 시간대: {slot_kor}
- 주제: {title}
- 풀어가는 각도: {angle}
- 사용할 해시태그 후보 (전부 다 쓸 필요는 없고, 자연스러운 것만): {hashtags}

[최근 게시 주제 — 표현/문장 재활용 금지]
{recent_keys}

위 가이드에 따라 마모루 말투의 슬로우조깅 정보성 게시물을 작성해줘. JSON으로만 답변.
"""

SLOT_KOR = {"morning": "아침", "noon": "점심", "evening": "저녁"}


def _extract_json(s: str) -> dict:
    s = s.strip()
    # 코드펜스 제거
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # 첫 { 부터 마지막 } 까지
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def write_post(topic: Topic, recent_topic_keys: list[str]) -> dict:
    """주제에 맞춰 글을 작성. {text, card_title, card_subtitle} 반환."""
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    user_msg = USER_TEMPLATE.format(
        slot_kor=SLOT_KOR[topic.slot],
        title=topic.title,
        angle=topic.angle,
        hashtags=" ".join(topic.hashtags),
        recent_keys=", ".join(recent_topic_keys) if recent_topic_keys else "(없음)",
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    data = _extract_json(raw)
    # 500자 제한 보장
    text = data.get("text", "").strip()
    if len(text) > 480:
        text = text[:480].rsplit("\n", 1)[0]
    data["text"] = text
    return data


REPLY_SYSTEM = """너는 슬로우조깅 인플루언서 "슬로우7"의 답글 봇이다.

[말투]
- 더파이팅 마모루 같은 활기찬 반말. 친한 형/누나 톤.
- 댓글 단 사람의 닉네임을 자연스럽게 한 번 부르고 시작 (예: "오 {username}!", "{username} 좋은 질문이다!")
- 1~2문장, 최대 100자. 짧고 펀치 있게.
- 댓글 내용을 정확히 읽고 그것에 응답. 동문서답 금지.
- 이모지 0~1개.

[금지]
- 존댓말, AI 언급, 광고성 멘트, 의학적 단정 금지
- 부정적 댓글이나 시비조 댓글에는 절대 똑같이 받아치지 말고, 가볍게 받아넘기기

답글 본문만 그대로 출력. 따옴표, 코드펜스, JSON 형식 모두 쓰지 마라.
"""


def write_reply(comment_text: str, username: str | None, parent_post_text: str | None) -> str:
    """댓글에 대한 마모루식 답글 생성."""
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    parent_text = parent_post_text or "(원본 게시물 텍스트 없음)"
    user_msg = (
        f"[내가 올린 원본 게시물]\n{parent_text}\n\n"
        f"[달린 댓글]\n작성자: @{username or 'unknown'}\n내용: {comment_text}\n\n"
        "이 댓글에 마모루 말투로 짧게 답글 작성. 본문만 출력."
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=200,
        system=REPLY_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
    # 혹시 따옴표 감싸져 있으면 벗기기
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
    return text[:480]
