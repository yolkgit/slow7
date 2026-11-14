"""SNS 게시 — 아침·점심 하루 두 번, 그날 날씨·환경에 맞춘 생활 정보 글.

    python -m scripts.sns_post               # 지금 시각으로 슬롯 판단 (아침/점심 외엔 건너뜀)
    python -m scripts.sns_post morning       # 슬롯 지정 (시각 검사 생략)
    python -m scripts.sns_post lunch --force # 오늘 이미 올렸어도 다시

흐름:
    1) 지금 시각(KST)으로 슬롯 결정 — 아침 5~10시, 점심 11~14시. 그 밖이면 아무것도 안 함.
       같은 슬롯은 하루 한 번만 (cron 이 여러 번 돌아도 중복 게시 안 됨).
    2) Open-Meteo 에서 오늘 날씨·미세먼지를 받아 사실 묶음과 "짚을 포인트"를 만든다.
    3) 최근 글에서 쓴 각도(옷차림/미세먼지/비…)는 피해서 이번 글의 중심을 고른다.
    4) 가벼운 모델로 짧은 글 생성 → 플랫폼에 게시.
       블로그 새 글이 발행된 날엔 점심 글 끝에 한 줄 소개 + 링크 (하루 1회).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db, social, social_writer, weather

# 슬롯별 게시 시간대 (KST, 시 단위 끝 포함)
SLOT_HOURS = {"morning": (5, 10), "lunch": (11, 14)}

# 오늘 이미 올린 슬롯 기록  값: "YYYY-MM-DD:morning,lunch"
SLOT_DONE_KEY = "sns_slot_done"

# 최근 게시한 SNS 본문 (같은 표현 반복 회피용)
SNS_TEXTS_KEY = "sns_recent_texts"
SNS_TEXTS_KEEP = 8

# 최근 글의 중심 각도 (같은 각도 연속 회피)
SNS_ANGLES_KEY = "sns_recent_angles"
SNS_ANGLES_KEEP = 4


def _now() -> dt.datetime:
    return dt.datetime.now(weather.KST)


def slot_for(now: dt.datetime) -> str | None:
    for slot, (h0, h1) in SLOT_HOURS.items():
        if h0 <= now.hour <= h1:
            return slot
    return None


def _done_slots(today: str) -> set[str]:
    raw = db.kv_get(SLOT_DONE_KEY, "") or ""
    day, _, slots = raw.partition(":")
    return set(filter(None, slots.split(","))) if day == today else set()


def _mark_done(today: str, slot: str) -> None:
    done = _done_slots(today) | {slot}
    db.kv_set(SLOT_DONE_KEY, f"{today}:{','.join(sorted(done))}")


def _load_list(key: str) -> list[str]:
    try:
        return json.loads(db.kv_get(key, "[]") or "[]")
    except ValueError:
        return []


def _push_list(key: str, item: str, keep: int) -> None:
    db.kv_set(key, json.dumps((_load_list(key) + [item])[-keep:], ensure_ascii=False))


def pick_focus(points: list[tuple[str, str]], recent_angles: list[str]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """중심 포인트 1~2개와 나머지를 고른다.

    - 비·눈, 미세먼지 나쁨, 한파·더위처럼 "오늘 꼭 알아야 할 것"은 최근에 다뤘어도 우선.
    - 그 밖엔 최근 글에서 안 쓴 각도를 고른다.
    """
    if not points:
        return [], []
    urgent = [p for p in points if p[0] in ("비·눈", "더위")
              or (p[0] == "미세먼지" and "좋음" not in p[1])
              or (p[0] == "옷차림" and "한파" in p[1])]
    fresh = [p for p in points if p[0] not in recent_angles and p not in urgent]
    pool = urgent + fresh or points
    first = pool[0] if urgent else random.choice(pool)
    rest = [p for p in points if p is not first]
    # 두 번째 중심: 첫째와 다른 각도에서 하나 (있으면)
    second = [p for p in rest if p[0] != first[0] and p[0] not in recent_angles]
    focus = [first] + ([random.choice(second)] if second and random.random() < 0.6 else [])
    extra = [p for p in points if p not in focus]
    return focus, extra


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]

    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 없음")
        return 2

    now = _now()
    slot = args[0] if args else slot_for(now)
    if slot not in SLOT_HOURS:
        print(f"[sns] {now:%H:%M} — 아침·점심 시간이 아니라 건너뜀")
        return 0

    platforms = social.enabled_platforms()
    if not platforms:
        print("[sns] 설정된 SNS 플랫폼 없음. .env 확인.")
        return 0

    db.init()
    today = now.date().isoformat()
    if slot in _done_slots(today) and not force:
        print(f"[sns] 오늘 {slot} 글은 이미 올림 — 건너뜀")
        return 0

    try:
        w = weather.fetch(now.date())
    except Exception as e:
        # 날씨 없이 엉뚱한 글을 올리느니 이번 회차는 쉰다
        print(f"[sns] ❌ 날씨 정보를 못 받아 이번 회차 건너뜀: {e}")
        return 1

    facts = weather.facts_text(w, slot)
    points = weather.check_points(w, slot)
    recent_angles = _load_list(SNS_ANGLES_KEY)
    focus, extra = pick_focus(points, recent_angles)
    print(f"[sns] 슬롯: {slot} | 플랫폼: {platforms}")
    print(f"[sns] 오늘 날씨:\n{facts}")
    print(f"[sns] 중심: {[p[0] for p in focus]} | 최근 각도: {recent_angles}")

    # 블로그 새 글이 발행된 날 — 점심 글에 한 줄 소개 (하루 1회)
    todays_post = db.published_post_today() if slot == "lunch" else None
    linked_today = db.kv_get("threads_link_date") == today

    recent_texts = _load_list(SNS_TEXTS_KEY)
    posted = 0
    body = None
    for platform in platforms:
        try:
            if body is None:
                body = social_writer.write_weather_post(
                    slot, facts,
                    [p[1] for p in focus] or ["특별한 날씨 이슈 없음 — 오늘 날씨에서 생활에 쓸모 있는 것 하나"],
                    [p[1] for p in extra],
                    platform=platform, avoid=recent_texts,
                )
            text = body
            link_used = False
            if platform == "threads":
                if todays_post and not linked_today:
                    text = f"{body}\n\n오늘 블로그 새 글: {todays_post['title']}\n{todays_post['wp_link']}"
                    link_used = True
            elif config.WP_SITE_URL:
                text = f"{body}\n\n{config.WP_SITE_URL}"

            print(f"\n[sns] {platform} 글:\n{text}\n")
            sns_id = social.post_to(platform, text)
            posted += 1
            print(f"[sns] ✅ {platform} 게시 (id={sns_id})")
            if not config.DRY_RUN and link_used:
                db.kv_set("threads_link_date", today)
        except Exception as e:
            print(f"[sns] ❌ {platform} 실패: {e}")
        if not config.DRY_RUN and platform != platforms[-1]:
            d = random.uniform(20, 60)
            print(f"[sns] ⏱ {d:.0f}초 대기")
            time.sleep(d)

    if posted and not config.DRY_RUN:
        _mark_done(today, slot)
        _push_list(SNS_TEXTS_KEY, body, SNS_TEXTS_KEEP)
        for p in focus:
            _push_list(SNS_ANGLES_KEY, p[0], SNS_ANGLES_KEEP)

    print(f"\n[sns] 총 {posted}개 플랫폼 게시 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
