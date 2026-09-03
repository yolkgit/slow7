"""하루 3번 SNS 게시 — 슬로우조깅 정보 한 토막 + 관련 블로그 글 링크.

    python -m scripts.sns_post          # 토픽 자동 선택
    python -m scripts.sns_post c_vs_walking  # 특정 토픽

흐름:
    1) 최근 안 쓴 토픽 하나 선택 (블로그와 별도로 SNS용 순환)
    2) SNS용 짧은 정보 글 생성 (마모루 톤)
    3) 그 토픽 주제군의 발행 블로그 글을 찾아 링크 첨부
    4) 각 SNS 플랫폼에 게시 (플랫폼 사이 랜덤 딜레이)
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db, social, social_writer, topics

# SNS 토픽 순환 추적용 KV 키 (블로그 이력과 분리)
SNS_RECENT_KEY = "sns_recent_topics"


# 하루 3회 게시하므로 창이 15면 5일이면 같은 토픽이 돌아온다.
# 실제로 n_talk_test 가 8/28 → 9/2 로 정확히 5일 만에 재등장했다.
# 연재 제외 후 풀이 49개이므로 30이면 후보가 19개 남아 고갈되지 않는다.
SNS_RECENT_WINDOW = 30


def _recent_sns_topics(limit: int = SNS_RECENT_WINDOW) -> list[str]:
    raw = db.kv_get(SNS_RECENT_KEY, "") or ""
    return [k for k in raw.split(",") if k][-limit:]


def _push_sns_topic(key: str, keep: int = SNS_RECENT_WINDOW) -> None:
    recent = _recent_sns_topics(limit=keep)
    recent.append(key)
    db.kv_set(SNS_RECENT_KEY, ",".join(recent[-keep:]))


def _strip_html(html: str, limit: int = 200) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _pick_topic(topic_key: str | None):
    all_t = topics.sns_topics()
    if topic_key:
        # 수동 지정은 연재 편도 허용한다
        return next((t for t in topics.all_topics() if t.key == topic_key), None)
    exclude = set(_recent_sns_topics(limit=SNS_RECENT_WINDOW))
    candidates = [t for t in all_t if t.key not in exclude] or all_t
    return random.choice(candidates)


def main(topic_key: str | None = None) -> int:
    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 없음")
        return 2

    platforms = social.enabled_platforms()
    if not platforms:
        print("[sns] 설정된 SNS 플랫폼 없음. .env 확인.")
        return 0

    db.init()
    topic = _pick_topic(topic_key)
    if not topic:
        print(f"토픽 못 찾음: {topic_key}")
        return 2
    print(f"[sns] 토픽: {topic.key} ({topic.title}) | 플랫폼: {platforms}")

    # 관련 블로그 글 찾기 (같은 주제군 우선) — 페이스북 등 링크 항상 거는 플랫폼용
    cluster = topics.topic_cluster(topic.key)
    cluster_keys = topics.keys_in_cluster(cluster)
    related = db.find_related_published(cluster, cluster_keys)
    if related:
        blog_url = related["wp_link"]
        print(f"[sns] 관련 글 링크: {related['title']} → {blog_url}")
    else:
        blog_url = config.WP_SITE_URL or ""
        print(f"[sns] 관련 발행글 없음 → 메인 링크 사용: {blog_url}")

    # 스레드 링크 정책: 평소엔 링크 없는 순수 정보 글,
    # 블로그를 발행한 날만 하루 1회 '새 글 소개'로 링크 (상업 계정처럼 안 보이게)
    today_str = time.strftime("%Y-%m-%d")
    todays_post = db.published_post_today()
    threads_linked_today = db.kv_get("threads_link_date") == today_str

    posted = 0
    for platform in platforms:
        threads_link_used = False
        try:
            if platform == "threads":
                if todays_post and not threads_linked_today:
                    # 오늘 발행한 새 글을 소개 (하루 1회)
                    summary = _strip_html(todays_post.get("content_html", ""))
                    promo = social_writer.write_promo(
                        todays_post["title"], summary, platform, todays_post["wp_link"]
                    )
                    threads_link_used = True
                    print("[sns] threads: 오늘 새 글 소개 (링크 1회)")
                else:
                    promo = social_writer.write_promo(topic.title, topic.angle, platform, None)
                    print("[sns] threads: 링크 없는 정보 글")
            else:
                promo = social_writer.write_promo(topic.title, topic.angle, platform, blog_url)

            print(f"\n[sns] {platform} 글:\n{promo}\n")
            sns_id = social.post_to(platform, promo)
            posted += 1
            print(f"[sns] ✅ {platform} 게시 (id={sns_id})")
            if threads_link_used and not config.DRY_RUN:
                db.kv_set("threads_link_date", today_str)
        except Exception as e:
            print(f"[sns] ❌ {platform} 실패: {e}")
        if not config.DRY_RUN and platform != platforms[-1]:
            d = random.uniform(20, 60)
            print(f"[sns] ⏱ {d:.0f}초 대기")
            time.sleep(d)

    _push_sns_topic(topic.key)
    print(f"\n[sns] 총 {posted}개 플랫폼 게시 완료")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(arg))
