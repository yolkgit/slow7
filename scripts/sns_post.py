"""SNS 게시 — 아침·점심 하루 두 번. 스레드 사람들처럼 반말로, 세 종류를 섞는다.
    정보: 예전처럼 슬로우조깅 토픽 하나를 짧게 (topics.sns_topics 순환)
    날씨: 그날 날씨·미세먼지 맞춤 한마디
    화제: 요즘 러닝 뉴스·대회·이벤트에 한마디

    python -m scripts.sns_post                 # 지금 시각으로 슬롯 판단 (아침/점심 외엔 건너뜀)
    python -m scripts.sns_post morning         # 슬롯 지정 (시각 검사 생략)
    python -m scripts.sns_post lunch --force   # 오늘 이미 올렸어도 다시
    python -m scripts.sns_post lunch --issue   # 종류 지정 (--info / --issue / --weather)

흐름:
    1) 지금 시각(KST)으로 슬롯 결정 — 아침 5~10시, 점심 11~14시. 그 밖이면 아무것도 안 함.
       같은 슬롯은 하루 한 번만 (cron 이 여러 번 돌아도 중복 게시 안 됨).
    2) 날씨를 받는다 (Open-Meteo → 안 되면 wttr.in).
    3) KIND_WEIGHTS 비율로 글 종류를 고른다. 아침은 정보·날씨 위주, 점심은 화제·정보 위주.
       비·미세먼지 나쁨·한파 날은 날씨 글 우선. 고른 종류가 안 되면 다른 종류로.
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

from src import config, db, social, social_writer, topics, trends, weather

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

# 이미 글로 쓴 화제 (같은 기사·글 재사용 방지)
SNS_ISSUES_KEY = "sns_used_issues"
SNS_ISSUES_KEEP = 60

# 글 종류별 비율. 정보 = 예전처럼 슬로우조깅 토픽 하나를 푸는 글,
# 날씨 = 그날 날씨 맞춤, 화제 = 요즘 러닝 뉴스·이벤트에 한마디.
KIND_WEIGHTS = {
    "morning": {"info": 0.45, "weather": 0.45, "issue": 0.10},
    "lunch": {"issue": 0.40, "info": 0.40, "weather": 0.20},
}
URGENT_ANGLES = ("비·눈", "더위")

# 정보 글 토픽 순환. 예전 기록(sns_recent_topics, 쉼표 구분)도 함께 피한다
SNS_TOPICS_KEY = "sns_recent_topics_v2"
SNS_TOPICS_KEEP = 60


def choose_kinds(slot: str, argv: list[str], has_weather: bool, urgent_weather: bool) -> list[str]:
    """이번 회차에 시도할 글 종류 순서. 첫 번째가 안 되면 다음 것으로."""
    for flag in ("info", "issue", "weather"):
        if f"--{flag}" in argv:
            first = flag
            break
    else:
        weights = dict(KIND_WEIGHTS[slot])
        if not has_weather:
            weights["weather"] = 0
        elif urgent_weather:
            # 비·미세먼지 나쁨·한파 날: 아침은 날씨 글, 점심은 날씨 글 비중 크게
            if slot == "morning":
                weights = {"weather": 1, "info": 0, "issue": 0}
            else:
                weights["weather"] = 0.5
        kinds = [k for k, v in weights.items() if v > 0]
        first = random.choices(kinds, weights=[weights[k] for k in kinds])[0]
    fallback = [k for k in ("info", "issue", "weather") if k != first]
    return [first] + fallback


def _pick_topic():
    """최근에 안 쓴 슬로우조깅 토픽 하나. 직전 3개와 같은 주제군은 피한다."""
    all_t = topics.sns_topics()
    old = [k for k in (db.kv_get("sns_recent_topics", "") or "").split(",") if k]
    recent = old + _load_list(SNS_TOPICS_KEY)
    candidates = [t for t in all_t if t.key not in set(recent)] or all_t
    recent_clusters = {topics.topic_cluster(k) for k in recent[-3:]}
    fresh = [t for t in candidates if topics.topic_cluster(t.key) not in recent_clusters]
    return random.choice(fresh or candidates)


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
        # 날씨를 못 받으면 날씨 글은 못 쓰니, 러닝 화제 글로만 시도한다
        print(f"[sns] ⚠️ 날씨 정보를 못 받음 — 화제 글로만 시도: {e}")
        w = None

    print(f"[sns] 슬롯: {slot} | 플랫폼: {platforms}")
    if w:
        facts = weather.facts_text(w, slot)
        points = weather.check_points(w, slot)
        recent_angles = _load_list(SNS_ANGLES_KEY)
        focus, extra = pick_focus(points, recent_angles)
        print(f"[sns] 오늘 날씨:\n{facts}")
        print(f"[sns] 중심: {[p[0] for p in focus]} | 최근 각도: {recent_angles}")
    else:
        facts, focus, extra = "", [], []

    # 블로그 새 글이 발행된 날 — 점심 글에 한 줄 소개 (하루 1회)
    todays_post = db.published_post_today() if slot == "lunch" else None
    linked_today = db.kv_get("threads_link_date") == today

    recent_texts = _load_list(SNS_TEXTS_KEY)
    urgent_weather = any(p[0] in URGENT_ANGLES or (p[0] == "미세먼지" and "좋음" not in p[1])
                         or "한파" in p[1] for p in focus)
    order = choose_kinds(slot, argv, has_weather=w is not None, urgent_weather=urgent_weather)
    print(f"[sns] 글 종류 순서: {order}")

    body = None
    used_issue = None
    used_topic = None
    for kind in order:
        try:
            if kind == "info":
                topic = _pick_topic()
                body = social_writer.write_info_post(topic.title, topic.angle, slot, avoid=recent_texts)
                used_topic = topic
                print(f"[sns] 정보 글: {topic.key} ({topic.title})")
            elif kind == "issue":
                issues = trends.collect(set(_load_list(SNS_ISSUES_KEY)))[:8]
                print(f"[sns] 화제 후보 {len(issues)}개: {[i.text[:30] for i in issues]}")
                if not issues:
                    continue
                first_win = next(iter(w.windows.values()), None) if w else None
                if urgent_weather:
                    wline = focus[0][1]
                elif first_win:
                    wline = f"{first_win.name} {first_win.sky}, 체감 {first_win.feels_min}~{first_win.feels_max}℃"
                else:
                    wline = ""
                n, text = social_writer.write_issue_post(
                    slot, [f"{i.text} ({trends.age_text(i.ts)})" for i in issues],
                    wline, avoid=recent_texts,
                )
                if not n:
                    print("[sns] 고를 만한 화제 없음")
                    continue
                body, used_issue = text, issues[n - 1]
                print(f"[sns] 화제 글: {used_issue.text}")
            elif kind == "weather":
                if not w:
                    continue
                body = social_writer.write_weather_post(
                    slot, facts,
                    [p[1] for p in focus] or ["특별한 날씨 이슈 없음 — 오늘 날씨에서 생활에 쓸모 있는 것 하나"],
                    [p[1] for p in extra], avoid=recent_texts,
                )
        except Exception as e:
            print(f"[sns] {kind} 글 생성 실패 — 다음 종류로: {e}")
            body = None
            continue
        if body:
            kind_used = kind
            break

    if not body:
        print("[sns] ❌ 쓸 글이 없어 이번 회차 건너뜀")
        return 1
    print(f"[sns] 최종 글 종류: {kind_used}")

    posted = 0
    for platform in platforms:
        try:
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
        if used_issue:
            _push_list(SNS_ISSUES_KEY, used_issue.key, SNS_ISSUES_KEEP)
        elif used_topic:
            _push_list(SNS_TOPICS_KEY, used_topic.key, SNS_TOPICS_KEEP)
        else:
            for p in focus:
                _push_list(SNS_ANGLES_KEY, p[0], SNS_ANGLES_KEEP)

    print(f"\n[sns] 총 {posted}개 플랫폼 게시 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
