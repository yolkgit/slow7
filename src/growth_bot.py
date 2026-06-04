"""트렌드 해시태그 댓글 봇 — 슬로우7 그로스 엔진.

매시간 슬로우조깅/러닝 관련 신규 게시물을 발견하고 진정성 있는 첫 댓글을 단다.
첫 댓글은 노출의 70%를 결정하므로 강력한 그로스 효과.

[안전장치 — 메타 봇 감지 회피]
- 시간당 최대 N개로 제한 (기본 6개)
- 24시간 내 동일 사용자에게 최대 1번
- 본인 계정에는 절대 댓글 X
- 너무 오래된 게시물 (12시간 초과) 스킵
- 너무 짧은 게시물 (10자 미만) 스킵
"""
from __future__ import annotations

import random
import time
from typing import Iterable

from . import config, db, threads_client, writer


# 본인 username 캐시 (self-check용)
_MY_USERNAME: str | None = None


def _my_username() -> str:
    """본인 Threads username을 한 번만 가져와서 캐싱."""
    global _MY_USERNAME
    if _MY_USERNAME is None:
        try:
            me = threads_client.me()
            _MY_USERNAME = (me.get("username") or "").lower()
            print(f"[growth] 본인 username: @{_MY_USERNAME}")
        except Exception as e:
            print(f"[growth] me() 실패 — username 캐시 못함: {e}")
            _MY_USERNAME = ""
    return _MY_USERNAME


# 슬로우조깅 / 러닝 / 다이어트 / 건강 도메인 키워드
GROWTH_KEYWORDS = [
    "슬로우조깅",
    "느린달리기",
    "초보러닝",
    "초보달리기",
    "다이어트러닝",
    "러닝다이어트",
    "존2러닝",
    "7분페이스",
    "무릎러닝",
    "유산소운동",
    "러닝일기",
    "러닝챌린지",
    "오늘의러닝",
    "달리기시작",
]

# 안전 한도
MAX_PER_HOUR = 6
MAX_PER_RUN = 4
MIN_TEXT_LEN = 15  # 너무 짧은 게시물은 컨텍스트 부족
MAX_AGE_SECONDS = 12 * 3600  # 12시간 이상 된 게시물은 스킵
MIN_USER_COOLDOWN_SECONDS = 24 * 3600  # 같은 사용자에게 24시간 안에 또 댓글 X


def _is_post_eligible(post: dict) -> tuple[bool, str]:
    """게시물이 댓글 달기 적합한지 검증."""
    post_id = post.get("id")
    if not post_id:
        return False, "no id"

    # 본인 게시물 제외 — username 우선, ID는 폴백
    post_username = (post.get("username") or (post.get("from") or {}).get("username") or "").lower()
    my_username = _my_username()
    if post_username and my_username and post_username == my_username:
        return False, "self (by username)"

    from_id = (post.get("from") or {}).get("id") or post.get("user_id")
    if from_id and str(from_id) == str(config.THREADS_USER_ID):
        return False, "self (by id)"

    text = (post.get("text") or "").strip()
    if len(text) < MIN_TEXT_LEN:
        return False, "too short"

    # 본인 멘션이 포함된 글은 본인을 부르는 답글일 가능성 — 스킵
    # (예: "야 slow7_crew! ..." 같은 텍스트)
    if my_username and (
        f"@{my_username}" in text.lower() or my_username in text.lower().split()
    ):
        return False, "mentions self"

    # 광고/홍보성 게시물 회피
    spam_markers = ("DM", "맞팔", "선팔", "유료광고", "공구", "공동구매", "쿠팡", "도매", "할인코드")
    if any(m.lower() in text.lower() for m in spam_markers):
        return False, "spammy"

    # 이미 댓글 단 게시물
    if db.has_commented_external(post_id):
        return False, "already commented"

    # 같은 사용자에게 24시간 내 또 댓글 금지
    username = post.get("username") or (post.get("from") or {}).get("username")
    if username and db.count_external_comments_to_user(username, MIN_USER_COOLDOWN_SECONDS) > 0:
        return False, f"user cooldown ({username})"

    # 시간 너무 오래됨
    ts_str = post.get("timestamp")
    if ts_str:
        try:
            # ISO 8601 형식
            from datetime import datetime
            ts = int(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp())
            if (time.time() - ts) > MAX_AGE_SECONDS:
                return False, "too old"
        except (ValueError, TypeError):
            pass

    return True, "ok"


def _gather_candidates(keywords: list[str]) -> list[tuple[dict, str]]:
    """각 키워드로 검색해서 (post, keyword) 튜플 리스트로 모음."""
    results: list[tuple[dict, str]] = []
    seen_ids: set[str] = set()
    seen_usernames: set[str] = set()
    # 키워드 순서 섞어서 매번 다른 키워드부터
    shuffled = list(keywords)
    random.shuffle(shuffled)
    first_dump = True
    for kw in shuffled:
        for search_type in ("RECENT", "TOP"):  # RECENT가 막히면 TOP 시도
            try:
                posts = threads_client.search_topic(kw, search_type=search_type, limit=10)
            except Exception as e:
                print(f"[growth] search 실패 [{kw}/{search_type}]: {e}")
                continue
            if not posts:
                continue
            # 첫 결과 한 번만 raw 덤프해서 응답 구조 확인
            if first_dump and posts:
                import json as _json
                print(f"[growth][debug] 첫 결과 raw 응답 구조: {_json.dumps(posts[0], ensure_ascii=False)[:500]}")
                first_dump = False
            for p in posts:
                pid = p.get("id")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                uname = (p.get("username") or "(no username)").lower()
                seen_usernames.add(uname)
                snippet = (p.get("text") or "").strip()[:50].replace("\n", " ")
                print(f"[growth][debug] [{kw}/{search_type}] @{uname}: {snippet}")
                results.append((p, kw))
    # 발견된 username 분포 요약
    print(f"[growth][debug] 발견된 unique username: {sorted(seen_usernames)}")
    return results


def run(dry_run: bool | None = None) -> int:
    """그로스 봇 1회 실행. 단 댓글 개수 반환."""
    if dry_run is None:
        dry_run = config.DRY_RUN

    db.init()

    # 시간당 한도 체크
    recent_hour = db.count_recent_external_comments(within_seconds=3600)
    if recent_hour >= MAX_PER_HOUR:
        print(f"[growth] 시간당 한도 도달 ({recent_hour}/{MAX_PER_HOUR}) → skip")
        return 0

    budget = min(MAX_PER_RUN, MAX_PER_HOUR - recent_hour)
    print(f"[growth] 이번 실행 예산: {budget}개")

    candidates = _gather_candidates(GROWTH_KEYWORDS)
    print(f"[growth] {len(candidates)}개 후보 발견")

    if not candidates:
        print("[growth] 후보 없음. keyword_search 권한 확인 필요.")
        return 0

    # 후보 셔플 (다양성 + 봇 패턴 회피)
    random.shuffle(candidates)

    commented = 0
    skip_counts: dict[str, int] = {}
    for post, kw in candidates:
        if commented >= budget:
            break

        ok, reason = _is_post_eligible(post)
        if not ok:
            skip_counts[reason] = skip_counts.get(reason, 0) + 1
            continue

        text = post.get("text", "")
        comment = writer.write_growth_comment(text)
        if not comment:
            print(f"[growth] 댓글 생성 스킵 (필터됨): {post.get('id')}")
            continue

        post_id = post["id"]
        username = post.get("username") or (post.get("from") or {}).get("username") or "unknown"
        snippet = text[:80].replace("\n", " ")

        print(f"[growth] → @{username} [{kw}] \"{snippet}...\"")
        print(f"[growth]    └ 댓글: {comment}")

        if dry_run:
            print("[growth]    (DRY_RUN — 실제 게시 X)")
            db.record_external_comment(post_id, username, text, None, kw)
            commented += 1
            continue

        try:
            reply_id = threads_client.publish_reply(post_id, comment)
            db.record_external_comment(post_id, username, text, reply_id, kw)
            commented += 1
            print(f"[growth]    ✅ 게시됨 reply_id={reply_id}")
        except threads_client.ThreadsError as e:
            print(f"[growth]    ❌ 실패: {e}")

        # 사람처럼 보이게 사이에 랜덤 딜레이
        time.sleep(random.uniform(8, 25))

    if skip_counts:
        print(f"[growth] 스킵 요약: {skip_counts}")
    print(f"[growth] 총 {commented}개 댓글 게시")
    return commented
