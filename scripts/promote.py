"""블로그 글을 SNS에 크로스포스팅 (유입용).

    python -m scripts.promote          # 아직 안 올린 발행글 1개를 각 SNS에 게시
    python -m scripts.promote --all    # 대기 중인 것 모두 (테스트용, 봇티 주의)

흐름:
    1) 발행된 블로그 글 중 아직 SNS에 안 올린 것 선택
    2) 플랫폼별 홍보글 생성 (마모루 톤 + 링크)
    3) 각 플랫폼에 게시 + DB 기록
    4) 플랫폼 사이 랜덤 딜레이 (봇 패턴 회피)
"""
from __future__ import annotations

import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db, social, social_writer


def _summary(content_html: str, limit: int = 200) -> str:
    text = re.sub(r"<[^>]+>", "", content_html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def promote_one(post: dict, platforms: list[str], dry_run: bool) -> int:
    wp_id = post["wp_post_id"]
    title = post["title"]
    link = post["wp_link"]
    summary = _summary(post.get("content_html", ""))
    done = 0

    for platform in platforms:
        if db.already_posted_social(wp_id, platform):
            continue
        try:
            promo = social_writer.write_promo(title, summary, platform, link)
            print(f"[promote] {platform} 홍보글:\n{promo}\n")
            sns_id = social.post_to(platform, promo)
            db.record_social_post(wp_id, platform, sns_id)
            done += 1
            print(f"[promote] ✅ {platform} 게시 완료 (id={sns_id})")
        except Exception as e:
            print(f"[promote] ❌ {platform} 실패: {e}")
        # 플랫폼 사이 랜덤 딜레이 (동시 게시 = 봇 패턴)
        if not dry_run:
            time.sleep(random.uniform(20, 60))
    return done


def main(argv: list[str]) -> int:
    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 없음")
        return 2

    platforms = social.enabled_platforms()
    if not platforms:
        print("[promote] 설정된 SNS 플랫폼 없음. .env에 토큰 넣거나 SNS_PLATFORMS 설정.")
        return 0
    print(f"[promote] 대상 플랫폼: {platforms}")

    db.init()
    posts = db.published_posts_for_promo(limit=20)
    if not posts:
        print("[promote] 홍보할 발행글 없음")
        return 0

    do_all = "--all" in argv

    # 아직 하나라도 안 올린 플랫폼이 있는 글만 대상
    pending = [
        p for p in posts
        if any(not db.already_posted_social(p["wp_post_id"], pl) for pl in platforms)
    ]
    if not pending:
        print("[promote] 모든 발행글이 이미 크로스포스팅됨")
        return 0

    targets = pending if do_all else pending[:1]
    total = 0
    for post in targets:
        print(f"\n[promote] === {post['title']} ===")
        total += promote_one(post, platforms, config.DRY_RUN)

    print(f"\n[promote] 총 {total}건 게시")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
