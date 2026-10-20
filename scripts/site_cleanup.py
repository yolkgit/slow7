"""애드센스 재신청 전 블로그 정리 (API 비용 없음 — 워드프레스 REST 만 씀).

    python -m scripts.site_cleanup            # 바꿀 내용만 출력
    python -m scripts.site_cleanup --apply    # 실제 반영

1. 같은 주제로 두 번 쓴 글 6쌍: 나중 글을 비공개(draft)로 돌린다.
   옛 주소는 mu-plugin slow7-merged-redirects.php 가 남긴 글로 301 한다.
   봇의 관련 글 목록에서도 빠지도록 review_queue 상태를 'merged' 로 바꾼다.
2. 소개 페이지(about) 본문을 wordpress_pages/about.html 로 교체한다.
3. 예전 기본 카테고리 '슬로우조깅'에만 있는 글을 난이도(초급/중급/고급)로 옮긴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import db, topics, wordpress_client as wp  # noqa: E402
from src.db import conn  # noqa: E402

# 비공개로 돌릴 글 → 남길 글 (mu-plugin 의 SLOW7_MERGED 와 같아야 함)
DUPLICATES = {250: 107, 246: 111, 242: 79, 238: 62, 233: 99, 225: 30}
OLD_CATEGORY = "슬로우조깅"
ABOUT_HTML = ROOT / "wordpress_pages" / "about.html"


def _get(path: str, **params):
    return wp._req("GET", path, params=params)


def merge_duplicates(apply: bool) -> None:
    print("\n== 1. 중복 글 정리 ==")
    for drop, keep in DUPLICATES.items():
        a = _get(f"posts/{drop}", context="edit", _fields="id,status,title,link")
        b = _get(f"posts/{keep}", _fields="id,status,title,link")
        print(f"  {drop} [{a['status']}] {a['title']['raw']}")
        print(f"    → 남김 {keep} [{b['status']}] {b['title']['rendered']}  {b['link']}")
        if b["status"] != "publish":
            print("    ⚠️ 남길 글이 공개 상태가 아님 — 건너뜀")
            continue
        if apply and a["status"] == "publish":
            wp._req("POST", f"posts/{drop}", json={"status": "draft"})
            with conn() as c:
                c.execute("UPDATE review_queue SET status='merged' WHERE wp_post_id=?", (str(drop),))
            print("    ✅ 비공개로 전환")


def update_about(apply: bool) -> None:
    print("\n== 2. 소개 페이지 ==")
    pages = _get("pages", slug="about", _fields="id,link,title")
    if not pages:
        print("  ⚠️ slug 'about' 페이지를 못 찾음")
        return
    page = pages[0]
    html = ABOUT_HTML.read_text(encoding="utf-8")
    print(f"  {page['id']} {page['link']}  ← {ABOUT_HTML.name} ({len(html)}자)")
    if apply:
        wp._req("POST", f"pages/{page['id']}", json={"content": html})
        print("  ✅ 교체")


def recategorize(apply: bool) -> None:
    print("\n== 3. '슬로우조깅' 카테고리 재분류 ==")
    cats = {c["name"]: c["id"] for c in _get("categories", per_page=100, _fields="id,name")}
    old = cats.get(OLD_CATEGORY)
    if not old:
        print("  옛 카테고리 없음")
        return
    posts = _get("posts", categories=old, per_page=100, _fields="id,title,categories")
    with conn() as c:
        keys = {r["threads_id"]: r["topic_key"] for r in c.execute(
            "SELECT threads_id, topic_key FROM posts WHERE slot='blog' AND threads_id IS NOT NULL")}
    by_key = {t.key: t for t in topics.all_topics()}
    for p in posts:
        t = by_key.get(keys.get(str(p["id"]), ""))
        # 봇 DB 에 없는 초창기 글은 입문 글이라 초급으로 둔다
        level = topics.topic_level(t) if t else "초급"
        if level not in cats:
            print(f"  ⚠️ 카테고리 '{level}' 없음 — {p['id']} 건너뜀")
            continue
        new = [cid for cid in p["categories"] if cid != old] + [cats[level]]
        new = list(dict.fromkeys(new))
        print(f"  {p['id']} {p['title']['rendered']}  → {level}{'' if t else ' (토픽 기록 없음)'}")
        if apply:
            wp._req("POST", f"posts/{p['id']}", json={"categories": new})
    if apply and not posts:
        print("  옮길 글 없음")


def main() -> int:
    apply = "--apply" in sys.argv
    db.init()
    merge_duplicates(apply)
    update_about(apply)
    recategorize(apply)
    if not apply:
        print("\n바꾼 것은 없습니다. 실제 반영은 --apply 로 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
