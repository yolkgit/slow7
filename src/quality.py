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
        "max_uses": 6,
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
