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

[말투 — 가장 중요. 글 처음부터 끝까지 절대 흐트러지지 말 것]
- "더파이팅"의 마모루 같은 활기차고 파이팅 넘치는 반말. 이게 슬로우7의 정체성이다.
- 정보는 충실하게 담되, 말투는 끝까지 마모루를 유지한다. (정보 전달한다고 차분해지지 마라!)
- 모든 문단에 반말 어미가 살아있어야 한다. 특히 글 후반부로 갈수록 차분해지는 것 절대 금지.
- 자주 쓰는 어미: "~다고!", "~잖아!", "~라구!", "~지!", "~봐!", "~야!", "가자!", "오케이!", "거든!"
- 권투/스포츠 비유 자연스럽게 (한 글에 1~2번): "한 방", "녹다운", "잽 날리듯", "링 위", "라운드"
- 독자를 끌어당기는 코치 톤. 옆에서 같이 뛰자고 부추기는 형/누나처럼.

[절대 금지 — 톤 무너지는 신호들]
- "~습니다", "~합니다", "~됩니다" 같은 존댓말/평어체 절대 금지
- "~할 수 있다", "~하는 것이 좋다" 같은 건조한 설명문체 금지 → "~할 수 있다고!", "~하는 게 좋잖아!" 로
- 백과사전 같은 객관적 서술 금지 → 항상 독자에게 말 거는 느낌

[좋은 마모루 톤 예시 — 이 느낌을 글 전체에 유지하라]
- 도입: "야! 천천히 뛰는 게 더 살 빠진다는 거 알아? 진짜라고! 🔥"
- 설명: "심박수가 최대의 60~70%일 때, 그때 지방이 주 연료가 되거든. 숨차게 뛰면 오히려 탄수화물부터 태워버린다고!"
- 소제목: "왜 느려야 오래 가는가?" / "이것만 지키면 무릎 안 아프다고!"
- 마무리: "오늘부터 7분 페이스로 가보자! 첫 발만 떼면 그 다음은 자동이라고. 넌 할 수 있어! 💪"

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
- 막연한 일반론 금지 — 구체적 숫자/방법/예시 포함 (예: "분당 160걸음", "주 3회 30분")
- 다른 블로그에도 있을 법한 뻔한 내용이 아니라 슬로우7만의 관점 한 스푼
- 본문 마지막 H2는 반드시 실천 체크리스트나 구체적 행동 가이드

[경험담 — 매우 중요, 거짓 금지]
- 아래 [참고 경험담]이 제공되면, 그 중 주제에 맞는 것을 골라 본문 중간에 1인칭으로 자연스럽게 녹여라
  (예: "사실 나도 처음엔 3분도 힘들어서 걷다 뛰다 반복했거든.")
- [참고 경험담]이 비어있거나 주제와 안 맞으면 — 절대 경험을 지어내지 마라.
  대신 "많은 초보자가 처음엔 ~한다" 같은 보편적 표현을 써라
- 없는 수치(내가 5kg 뺐다 등)를 1인칭으로 단정하는 것 절대 금지

[표 — 비교형/루틴형 글에 필수]
- 주제가 'vs' 비교거나 루틴/플랜이면 반드시 <table>로 비교표 또는 주차별 계획표를 넣어라
- 표 형식: <table><thead><tr><th>항목</th>...</tr></thead><tbody><tr><td>...</td></tr></tbody></table>
- 표는 본문 중간 적절한 위치에. 3~5행 정도로 한눈에 보이게

[금지]
- 존댓말 (반말 유지)
- AI/ChatGPT/Claude 언급
- 거짓 정보, 과장된 효능, 없는 연구 인용 (가짜 출처 절대 금지)
- 외부 링크나 광고 문구 (제휴는 나중에 사람이 직접 삽입)

[출력 형식 — 정확히 이 형식으로]
먼저 메타데이터를 JSON으로 출력하고, 그 다음 줄에 ===CONTENT=== 구분선,
그 아래에 본문 HTML을 출력한다. (본문은 JSON 안에 넣지 마라 — 따옴표 충돌 방지)

{
  "title": "<SEO 제목 — 28자 이내, 핵심 키워드 포함, 클릭 유도>",
  "slug": "<영문 소문자 슬러그, 하이픈 구분. 예: slow-jogging-fat-burn>",
  "meta_description": "<검색결과 요약 — 80~120자>",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "card_title": "<썸네일용 큰 제목 12자 이내>",
  "card_subtitle": "<썸네일용 부제 22자 이내>"
}
===CONTENT===
<여기에 본문 HTML. h2/p/ul/strong 태그 사용. 제목(h1)은 넣지 말 것. 따옴표 자유롭게 사용 가능.>

위 형식 외의 설명은 일체 출력하지 마라.
"""


USER_TEMPLATE = """[오늘의 블로그 글 작성 지시]

- 주제: {title}
- 풀어가는 각도: {angle}
- 추천 키워드/태그 후보: {hashtags}

[이미 발행한 최근 글 제목들 — 이 글들과 내용/예시/표현이 겹치면 안 됨]
{recent_titles}
→ 위 글들과 다른 각도, 다른 예시, 다른 소제목으로 써라. 같은 주제(예: 지방연소)라도
   이미 다룬 내용 반복 금지. 이 글만의 고유한 정보·관점을 최소 한 가지 넣어라.

[참고 경험담 — 주제에 맞는 게 있으면 1인칭으로 자연스럽게 녹이고, 없으면 보편적 표현 사용. 절대 지어내지 말 것]
{experiences}

위 가이드대로 SEO 최적화된 슬로우조깅 정보 블로그 글을 작성해줘.
"""


def _load_experiences() -> str:
    """경험담 풀 로드. 주석/헤더(>, #) 제외하고 '-' 항목만."""
    try:
        if not config.EXPERIENCES_PATH.exists():
            return "(없음)"
        lines = config.EXPERIENCES_PATH.read_text(encoding="utf-8").splitlines()
        items = [ln.strip() for ln in lines if ln.strip().startswith("- ")]
        return "\n".join(items) if items else "(없음)"
    except Exception:
        return "(없음)"


# 건강 정보 면책 문구 — 모든 글 끝에 자동 삽입 (YMYL 신뢰도 + 법적 안전)
# 작은 회색 글씨로 표시해서 본문과 구분 (시선 분산 최소화)
DISCLAIMER_HTML = (
    '<hr>\n'
    '<p style="font-size:0.8em; color:#999; line-height:1.6;"><small>'
    '※ 이 글은 슬로우조깅에 대한 일반적인 정보 제공을 목적으로 하며, '
    '의학적 진단이나 치료를 대신하지 않습니다. 지병이 있거나 부상 이력이 있다면 '
    '운동 시작 전 전문가(의사·트레이너)와 상담하시기 바랍니다. '
    '자기 몸 상태에 맞춰 무리 없이 시작하는 것이 가장 중요합니다.'
    '</small></p>'
)


CONTENT_MARKER = "===CONTENT==="


def _extract_json(s: str) -> dict:
    """순수 JSON 블록만 파싱 (본문 분리 전 메타데이터용)."""
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def _parse_meta_and_content(raw: str) -> tuple[dict, str]:
    """===CONTENT=== 구분자로 메타(JSON)와 본문(HTML)을 분리."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json|html)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    if CONTENT_MARKER in raw:
        meta_part, content_part = raw.split(CONTENT_MARKER, 1)
    else:
        # 구분자 없으면 — JSON 끝(}) 이후를 본문으로 간주
        end = raw.rfind("}")
        if end >= 0:
            meta_part, content_part = raw[: end + 1], raw[end + 1 :]
        else:
            meta_part, content_part = raw, ""

    try:
        meta = _extract_json(meta_part)
    except json.JSONDecodeError:
        meta = {}

    content = content_part.strip()
    content = re.sub(r"^```(?:html)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()
    return meta, content


def write_blog_post(topic: Topic, recent_titles: list[str]) -> dict:
    """블로그 글 생성. recent_titles: 최근 발행 제목들(중복 방지)."""
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    titles_str = "\n".join(f"- {t}" for t in recent_titles) if recent_titles else "(아직 없음)"
    user_msg = USER_TEMPLATE.format(
        title=topic.title,
        angle=topic.angle,
        hashtags=" ".join(topic.hashtags),
        recent_titles=titles_str,
        experiences=_load_experiences(),
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=3500,
        temperature=1.0,  # 톤이 더 생생하게 살아나도록
        system=BLOG_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    data, content_html = _parse_meta_and_content(raw)
    data["content_html"] = content_html

    # 필수 필드 검증 + 폴백
    data.setdefault("title", topic.title)
    data.setdefault("meta_description", topic.angle)
    data.setdefault("tags", [t.lstrip("#") for t in topic.hashtags])
    data.setdefault("slug", topic.key.replace("_", "-"))
    if not data["content_html"].strip():
        raise ValueError("content_html이 비어있음 — 생성 실패")
    # 건강 정보 면책 문구 자동 첨부 (중복 방지)
    if "정보 제공을 목적" not in data["content_html"]:
        data["content_html"] = data["content_html"].rstrip() + "\n" + DISCLAIMER_HTML
    return data


REVISE_SYSTEM = """너는 슬로우조깅 블로그 "슬로우7"의 편집자다.
기존 블로그 글과 편집 지시를 받고, 지시대로 글을 수정한다.

[규칙]
- 마모루 톤(활기찬 반말) 유지
- 지시받은 부분만 수정, 나머지는 최대한 보존
- HTML 구조(<h2>, <p>, <ul> 등) 유지
- 맨 아래 면책 문구(※ 로 시작하는 작은 글씨)는 건드리지 말고 그대로 둘 것
- 거짓 정보/가짜 출처 추가 금지

[출력 형식 — 정확히 이 형식으로]
먼저 제목을 JSON으로, 그 다음 ===CONTENT=== 구분선, 그 아래 본문 HTML 전체.
(본문은 JSON 안에 넣지 마라 — 따옴표 충돌 방지)

{
  "title": "<수정된 제목 (제목 수정 지시 없으면 원래 제목 그대로)>"
}
===CONTENT===
<수정된 본문 HTML 전체. 따옴표 자유롭게 사용 가능.>

위 형식 외의 설명은 출력하지 마라.
"""


def revise_blog_post(current_title: str, current_html: str, instruction: str) -> dict:
    """기존 글 + 수정 지시 → 수정된 {title, content_html}."""
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    user_msg = (
        f"[기존 제목]\n{current_title}\n\n"
        f"[기존 본문 HTML]\n{current_html}\n\n"
        f"[편집 지시]\n{instruction}\n\n"
        "지시대로 수정해서 위 형식으로 출력."
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=3500,
        system=REVISE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    data, content_html = _parse_meta_and_content(raw)
    title = data.get("title") or current_title
    if not content_html.strip():
        content_html = current_html
    return {"title": title, "content_html": content_html}
