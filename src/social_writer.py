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


# write_promo 에 보여줄 최근 글 수 (입력 토큰을 아끼려고 앞 200자씩만)
SNS_AVOID_SHOWN = 6


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
    kwargs = dict(
        max_tokens=1200,
        system=NAVER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    try:
        msg = client.messages.create(model=config.ANTHROPIC_MODEL_LIGHT, **kwargs)
    except Exception as e:
        # 가벼운 모델이 막혀도(단종·설정 오류) 블로그 글 쓰는 모델로 한 번 더 시도
        if config.ANTHROPIC_MODEL == config.ANTHROPIC_MODEL_LIGHT:
            raise
        print(f"[naver] {config.ANTHROPIC_MODEL_LIGHT} 실패 → {config.ANTHROPIC_MODEL} 로 재시도: {e}")
        msg = client.messages.create(model=config.ANTHROPIC_MODEL, **kwargs)
    body = _clean("".join(b.text for b in msg.content if hasattr(b, "text")))
    return f"{body}\n\n👉 전체 글 보기: {blog_url}"


THREADS_VOICE = """너는 스레드(Threads)에 글 쓰는 평범한 러너다. 슬로우조깅(천천히 오래 달리기)을 좋아하고,
출근 전이나 점심에 피드에 짧게 한마디 남기는 사람. 계정 이름은 "슬로우7".

[말투 — 스레드에서 사람들이 실제로 쓰는 반말]
- 친구한테 말하듯 편한 반말. "~했음", "~인 듯", "~하자", "~더라", "ㅋㅋ" 정도는 자연스러우면 섞어도 됨.
- 혼잣말·감상·질문이 섞인 짧은 문장. 줄바꿈 자주.
- 광고·정보 블로그 같은 말투 금지: "꿀팁", "알아볼까요", "~하는 방법", "여러분", 존댓말, 번호 매긴 목록.
- 마모루식 과장("가자!!", "~다고!", 🔥 남발)도 금지. 이모지는 없거나 1개.
- 해시태그·링크 넣지 않는다.

[내용]
- 주어진 사실만 숫자로 쓴다. 기록·거리·장소·사람 같은 구체적인 경험을 지어내지 않는다.
  ("나도 그런 적 있음" 같은 가벼운 공감은 괜찮다)
- 읽고 나서 써먹을 게 하나는 있게. 길게 설명하지 말고 한두 줄로.
- 매번 같은 틀로 시작하지 않는다. 인사로 시작하지 않는다.
- 3~6줄, 짧게.

[출력] 글 본문만. 따옴표·설명 없이.
"""


def write_weather_post(
    slot: str, facts: str, focus: list[str], extra: list[str],
    platform: str = "threads", avoid: list[str] | None = None,
) -> str:
    """오늘 날씨·환경 사실을 바탕으로 한 짧은 정보 글.

    slot: "morning" | "lunch"
    facts: weather.facts_text() 결과
    focus: 이번 글의 중심 포인트 (1~2개)
    extra: 참고만 할 나머지 포인트
    """
    limit = min(LIMITS.get(platform, 300), 350)
    when = {
        "morning": "아침 (출근 전 — 오늘 날씨 보고 한마디)",
        "lunch": "점심 (점심시간 — 오후·퇴근 후 날씨 보고 한마디)",
    }[slot]
    user_msg = (
        f"[올리는 때]\n{when}\n\n"
        f"[오늘 날씨]\n{facts}\n\n"
        "[이번 글의 중심 — 이것 위주로]\n" + "\n".join(f"- {p}" for p in focus)
    )
    if extra:
        user_msg += "\n\n[참고만 — 꼭 필요할 때만 한 줄]\n" + "\n".join(f"- {p}" for p in extra)
    user_msg += f"\n\n{limit}자 이내로 본문만."
    if avoid:
        shown = "\n---\n".join(t[:160] for t in avoid[-SNS_AVOID_SHOWN:])
        user_msg += (
            "\n\n[최근에 올린 글 — 첫 줄, 문장 틀, 표현이 겹치면 안 됨]\n"
            f"{shown}"
        )

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL_LIGHT,
        max_tokens=400,
        system=THREADS_VOICE,
        messages=[{"role": "user", "content": user_msg}],
    )
    body = _clean("".join(b.text for b in msg.content if hasattr(b, "text")))
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0]
    return body


def write_issue_post(
    slot: str, issues: list[str], weather_line: str = "",
    platform: str = "threads", avoid: list[str] | None = None,
) -> tuple[int | None, str]:
    """요즘 러닝 쪽 화제 중 하나를 골라 사람 말투로 한마디.

    issues: 화제 목록 (기사 제목·스레드 글 앞부분). 번호는 1부터.
    반환: (고른 번호 또는 None, 본문). 고를 만한 게 없으면 (None, "").
    """
    limit = min(LIMITS.get(platform, 300), 350)
    listing = "\n".join(f"{i}. {t}" for i, t in enumerate(issues, 1))
    user_msg = (
        f"[올리는 때]\n{'아침' if slot == 'morning' else '점심'}\n\n"
        f"[요즘 러닝 쪽에서 돌고 있는 얘기 — 기사 제목이나 남들 글]\n{listing}\n\n"
    )
    if weather_line:
        user_msg += f"[오늘 날씨 — 자연스러우면 한 줄만]\n{weather_line}\n\n"
    user_msg += (
        "위에서 러너들이 반응할 만한 걸 하나 골라서, 그 얘기를 본 사람처럼 한마디 써줘.\n"
        "- 대회·이벤트면 언제 뭐가 있는지, 나가는 사람한테 도움 될 한 줄.\n"
        "- 화제·논쟁이면 내 생각이나 슬로우조깅 하는 입장에서 한마디.\n"
        "- 제목에 없는 사실(날짜·기록·참가자 수 등)은 지어내지 마.\n"
        "- 남의 글을 그대로 옮기지 마.\n"
        "- 러닝과 관계없거나 사건·사고·정치 얘기면 고르지 마.\n\n"
        "출력 형식:\n첫 줄에 '번호: N' (고를 게 없으면 '번호: 0')\n빈 줄\n본문"
        f" ({limit}자 이내)"
    )
    if avoid:
        shown = "\n---\n".join(t[:160] for t in avoid[-SNS_AVOID_SHOWN:])
        user_msg += f"\n\n[최근에 올린 글 — 첫 줄·표현 겹치지 않게]\n{shown}"

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL_LIGHT,
        max_tokens=450,
        system=THREADS_VOICE,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = _clean("".join(b.text for b in msg.content if hasattr(b, "text")))
    m = re.match(r"\s*번호\s*[:：]\s*(\d+)\s*\n?", raw)
    if not m:
        return None, ""
    n = int(m.group(1))
    body = raw[m.end():].strip()
    if n < 1 or n > len(issues) or not body:
        return None, ""
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0]
    return n, body


def write_promo(
    title: str, summary: str, platform: str, blog_url: str | None,
    avoid: list[str] | None = None,
) -> str:
    """플랫폼용 글 생성.

    blog_url 있으면: 클릭 유도 홍보글 + 링크 첨부
    blog_url 없으면: 링크 없는 순수 정보 글 (자연스러운 계정 운영용)
    avoid: 최근 게시한 글들 — 첫 줄·표현·예시가 겹치지 않게 참고용으로 준다
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

    if avoid:
        shown = "\n---\n".join(t[:200] for t in avoid[-SNS_AVOID_SHOWN:])
        user_msg += (
            "\n\n[최근에 올린 글 — 이 글들과 첫 줄, 표현, 예시, 숫자가 겹치면 안 됨]\n"
            f"{shown}"
        )

    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL_LIGHT,
        max_tokens=400,
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
