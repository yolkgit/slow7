"""글 품질 장치 — 웹 검색으로 실제 출처를 찾고, 본문 링크가 진짜인지 검증한다.

애드센스가 "가치가 별로 없는 콘텐츠"로 거절한 이유(2026-10)는 글마다
출처 없는 건강 수치, 직접 겪지 않은 경험, 찍어낸 듯한 문체였다.
여기서는 두 가지를 보장한다.

1) Claude 가 server-side web_search 로 찾은 페이지만 링크로 쓸 수 있다.
   검색 결과에 없던 URL 이 본문에 있으면 지어낸 출처로 보고 글을 거절한다.
2) 링크가 실제로 열리는지(HTTP 400 미만) 확인한다.
"""
from __future__ import annotations

import re

import requests
from anthropic import Anthropic

from . import config

# 출처·인용으로 링크해도 되는 사이트를 제한하지 않는다(커뮤니티 후기도 필요하므로).
# 대신 "검색 결과에 실제로 나온 URL 인지"와 "열리는지"로 거른다.
_INTERNAL_HOSTS = ("soritok.com",)

_HREF_RE = re.compile(r'href="(https?://[^"]+)"', re.I)


QUALITY_RULES = """[품질 규칙 — 애드센스 심사 대응. 말투 규칙보다 우선한다]
1. 출처: 건강 효과, 수치(심박수 %, kcal, mmHg, 주수 등), 연구 결과를 말할 때는 web_search 로
   신뢰할 만한 자료(질병관리청·보건복지부·WHO·대한의학회·대학병원·학회·PubMed 논문·공신력 있는 언론)를 찾아
   본문 끝 <h2>참고 자료</h2> 아래 <ul> 에 2~4개 링크로 단다.
   링크 형식: <li><a href="실제URL" rel="nofollow noopener" target="_blank">자료 제목</a> — 기관/매체명</li>
   검색 결과에서 직접 확인한 URL 만 쓴다. URL 을 추측하거나 만들어 내지 마라.
   근거를 찾지 못한 수치나 효과 주장은 빼거나 "개인차가 크다" 수준으로 낮춘다.
2. 의료 표현: 약 복용·중단, 질병 치료를 권하거나 암시하는 문장 금지
   (예: "혈압 약에만 의존하기 전에" X). 효과는 "도움이 될 수 있다" 수준으로 쓴다.
3. 다른 러너의 실제 후기: web_search 로 찾은 공개 글(러닝 커뮤니티, 블로그, 기사 인터뷰)에서
   주제와 맞는 경험을 최대 2개까지 짧게(각 2문장 이내) 인용할 수 있다.
   반드시 남의 경험으로 밝히고 출처를 단다:
   <blockquote><p>"인용문"</p><p>— <a href="실제URL" rel="nofollow noopener" target="_blank">출처 사이트/작성자</a></p></blockquote>
   절대 1인칭("나도 ~했다")으로 바꾸지 마라. 적당한 후기를 못 찾으면 넣지 않는다.
4. 지어내기 금지: 글쓴이 본인의 경험·기록·수치를 만들어 내지 마라. 연구·통계·인용도 검색으로 확인한 것만.
5. 문체 반복 줄이기: 같은 어미("~거든", "~라고!")를 연달아 쓰지 말고, 느낌표는 문단당 1개 이내,
   이모지는 글 전체 2개 이내, 스포츠 비유는 글 전체 1번 이내. ✅ 이모지 체크리스트 대신 일반 <ul> 을 쓴다.
"""


def web_search_tool() -> dict:
    """모델에 맞는 web_search 서버 도구 정의."""
    model = config.ANTHROPIC_MODEL
    # 동적 필터링 버전(_20260209)은 Opus 4.6+/Sonnet 4.6+ 에서만 동작한다
    old = model.startswith("claude-haiku-4") or model.startswith("claude-3")
    return {
        "type": "web_search_20250305" if old else "web_search_20260209",
        "name": "web_search",
        "max_uses": 3,  # 검색 결과 본문이 통째로 입력 토큰이 되므로 횟수를 아낀다
        "user_location": {"type": "approximate", "country": "KR"},
    }


def _search_urls(content: list) -> set[str]:
    """응답 블록에서 web_search 결과 URL 을 모은다."""
    urls: set[str] = set()
    for b in content:
        if getattr(b, "type", "") != "web_search_tool_result":
            continue
        results = getattr(b, "content", None)
        if not isinstance(results, list):  # 오류 객체면 건너뜀
            continue
        for r in results:
            url = getattr(r, "url", None)
            if url:
                urls.add(_norm(url))
    return urls


def _norm(url: str) -> str:
    return url.split("#")[0].rstrip("/")


def generate_with_search(system: str, user_msg: str, max_tokens: int = 8000) -> tuple[str, set[str]]:
    """web_search 를 켠 채로 생성. (최종 텍스트, 검색으로 확인된 URL 집합) 반환.

    서버 도구는 한 응답 안에서 끝나지만, 검색이 길어지면 stop_reason=pause_turn 으로
    멈추므로 그대로 이어 붙여 다시 요청한다.
    """
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    messages: list[dict] = [{"role": "user", "content": user_msg}]
    urls: set[str] = set()
    text_parts: list[str] = []
    for _ in range(4):
        msg = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=[web_search_tool()],
            messages=messages,
        )
        u = msg.usage
        print(f"  [토큰] 입력 {u.input_tokens:,} / 출력 {u.output_tokens:,}", flush=True)
        urls |= _search_urls(msg.content)
        text_parts.append("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))
        if msg.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": msg.content})
    # 출력 형식(JSON + ===CONTENT===)은 마지막 텍스트 묶음에 들어 있다
    final = text_parts[-1] if text_parts[-1].strip() else "".join(text_parts)
    return final, urls


def external_links(html: str) -> list[str]:
    return [u for u in _HREF_RE.findall(html) if not any(h in u for h in _INTERNAL_HOSTS)]


def bad_links(html: str, verified: set[str]) -> list[str]:
    """검색 결과에 없었거나 열리지 않는 외부 링크 목록. 빈 리스트면 통과."""
    bad: list[str] = []
    for url in external_links(html):
        if _norm(url) not in verified:
            bad.append(f"{url} (검색 결과에 없던 주소)")
            continue
        try:
            r = requests.get(url, timeout=15, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (slow7 link check)"}, stream=True)
            r.close()
            # 일부 사이트는 봇에 403 을 준다 — 존재는 하므로 통과시킨다
            if r.status_code >= 400 and r.status_code not in (401, 403, 429):
                bad.append(f"{url} (HTTP {r.status_code})")
        except requests.RequestException as e:
            bad.append(f"{url} ({type(e).__name__})")
    return bad


# ----------------------------------------------------------------------
# 내부 메모 제거
# 모델이 "[작성 근거 노트 — 발행 전 확인용]" 같은 작업 메모를 본문에 남길 때가 있다
# (2026-10-21 자동 발행 글에서 실제로 노출됨). 독자에게 보이면 사람이 검수하지 않은
# 자동 생성 글이라는 신호가 되므로, 발행 전에 그 블록을 통째로 지운다.
# ----------------------------------------------------------------------
NOTE_MARKERS = (
    "발행 전", "작성 근거", "확인용", "근거 노트", "작성 노트", "편집 메모", "편집 참고",
    "내부 메모", "수정 내역", "변경 내역", "중복 방지", "검색에서 확인", "작성자 메모",
)
_BLOCK_RE = re.compile(
    r"<(p|div|blockquote|ul|ol|aside|details|pre|section|table)\b[^>]*>.*?</\1>",
    re.S | re.I,
)
_HEADING_RE = re.compile(r"<h([2-4])\b[^>]*>(.*?)</h\1>", re.S | re.I)


def _has_note(fragment: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return any(m in text for m in NOTE_MARKERS)


CONTENT_MARKER = "===CONTENT==="
# 모델이 글을 한 번 쓰고 "보기 좋게 정리해서 다시 출력할게!" 하며 JSON·구분자·본문을 또 내보내면
# 첫 구분자 뒤를 모두 본문으로 받아 두 벌이 한 글에 들어간다 (2026-10-23 커피 글).
_LEAK_START_RE = re.compile(r"다시 출력|```|`json|^[ \t]*(?:<p>)?\{", re.M)
_LEAK_END_RE = re.compile(r"<h2>함께 읽으면 좋은 글|<hr\b", re.I)


def strip_output_leak(html: str) -> tuple[str, int]:
    """본문에 섞인 두 번째 출력(구분자 앞 '다시 출력'·코드 펜스·JSON 부터 두 번째 본문 끝까지)을 지운다.
    첫 번째 본문과, 발행 때 붙은 '함께 읽으면 좋은 글'·면책 문구는 남긴다."""
    removed = 0
    while (i := html.find(CONTENT_MARKER)) >= 0:
        # 구분자 바로 앞 몇 줄 안에서 찌꺼기가 시작되는 곳
        window = max(0, i - 3000)
        # finditer(pos, endpos) 의 m.start() 는 이미 html 전체 기준 위치다
        starts = [m.start() for m in _LEAK_START_RE.finditer(html, window, i)]
        start = min(starts) if starts else i
        start = html.rfind("\n", 0, start) + 1
        end_m = _LEAK_END_RE.search(html, i + len(CONTENT_MARKER))
        end = end_m.start() if end_m else len(html)
        html = html[:start].rstrip() + "\n\n" + html[end:]
        removed += 1
    return html, removed


def strip_internal_notes(html: str) -> tuple[str, int]:
    """작업 메모 블록을 지운 본문과 지운 개수."""
    # 0) 두 번 출력된 글의 두 번째 벌
    html, removed = strip_output_leak(html)
    # 1) 메모가 소제목이면 그 소제목부터 다음 같은 급 이상 소제목 전까지 통째로
    while True:
        hit = next((m for m in _HEADING_RE.finditer(html) if _has_note(m.group(2))), None)
        if not hit:
            break
        level = int(hit.group(1))
        nxt = re.compile(rf"<h[2-{level}]\b", re.I).search(html, hit.end())
        disc = html.find("※", hit.end())
        end_candidates = [i for i in (nxt.start() if nxt else -1, disc) if i != -1]
        end = min(end_candidates) if end_candidates else len(html)
        if disc != -1 and end == disc:  # 면책 문구가 든 <p> 시작점까지만
            end = html.rfind("<", hit.end(), disc)
        html = html[: hit.start()] + html[end:]
        removed += 1
    # 2) 메모가 든 개별 블록 (참고 자료 목록·면책 문구는 표현이 겹치지 않아 안전)
    def _drop(m: re.Match) -> str:
        nonlocal removed
        if _has_note(m.group(0)):
            removed += 1
            return ""
        return m.group(0)
    html = _BLOCK_RE.sub(_drop, html)
    # 3) 태그 없이 빈 줄로 나뉜 문단 (워드프레스 raw 본문은 <p> 없이 저장되고 화면에서만 감싸진다)
    html, n = _strip_plain_notes(html)
    # 4) 코드 블록 표시(```)·구분선이 따옴표 등으로 바뀌어 홀로 남은 문단 (“` 나 — 만 있는 줄)
    html, k = _JUNK_RE.subn("", html)
    return html, removed + n + k


_JUNK_RE = re.compile(r"(?:^|\n)[ \t]*(?:<p>)?[ \t]*[`“”\"'‘’—–\-]{1,4}[ \t]*(?:</p>)?[ \t]*(?=\n|$)")


def _strip_plain_notes(html: str) -> tuple[str, int]:
    """'[작성 근거 노트 — …]' 같은 제목 문단과, 그 아래 이어지는 태그 없는 문단을 지운다.
    <hr>·소제목·※ 면책 문구 등 태그로 시작하는 문단을 만나면 멈춘다."""
    parts = re.split(r"(\n[ \t]*\n)", html)
    out: list[str] = []
    removed = 0
    skipping = False
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        s = chunk.strip()
        plain = bool(s) and (not s.startswith("<") or re.match(r"<(strong|b|em)\b", s, re.I) is not None)
        # 메모 줄 바로 아래(빈 줄 없이) <hr>·면책 문구가 붙어 있으면 그 줄부터는 남긴다
        tail = ""
        if plain:
            m = re.search(r"^[ \t]*(<(?!/?(strong|b|em|br)\b)|※)", chunk, re.M | re.I)
            if m:
                chunk, tail = chunk[: m.start()], chunk[m.start():]
                s = chunk.strip()
        if skipping:
            if plain and s and not s.startswith("※"):
                if tail:
                    skipping = False
                    out.append(tail + sep)
                continue
            skipping = False
        if plain and _has_note(s):
            removed += 1
            # 대괄호 제목형이면 뒤따르는 메모 항목 문단까지
            skipping = not tail and re.match(r"^[*_\s]*(<(strong|b)>)?[*_\s]*\[", s) is not None
            if tail:
                out.append(tail + sep)
            continue
        out.append(chunk + tail + sep)
    return "".join(out), removed
