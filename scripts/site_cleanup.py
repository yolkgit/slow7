"""애드센스 재신청 전 블로그 정리 (API 비용 없음 — 워드프레스 REST 만 씀).

    python -m scripts.site_cleanup            # 바꿀 내용만 출력
    python -m scripts.site_cleanup --apply    # 실제 반영

1. 같은 주제로 두 번 쓴 글 6쌍: 나중 글을 비공개(draft)로 돌린다.
   옛 주소는 mu-plugin slow7-merged-redirects.php 가 남긴 글로 301 한다.
   봇의 관련 글 목록에서도 빠지도록 review_queue 상태를 'merged' 로 바꾼다.
2. 소개 페이지(about) 본문을 wordpress_pages/about.html 로 교체한다.
3. 예전 기본 카테고리 '슬로우조깅'에만 있는 글을 난이도(초급/중급/고급)로 옮긴다.
4. 봇 DB 에 남은 옛 블로그 주소(slow7.soritok.com)를 새 주소로 바꾼다
   (새 글의 '관련 글' 링크가 301 을 거치지 않게).
5. 고정 페이지의 예시 메일 주소·GitHub 원본 링크를 정리한다.
6. 본문의 ?p=숫자 내부 링크를 실제 글 주소로 바꾼다. 없는 글로 가는 링크는 걷어 낸다.
"""
from __future__ import annotations

import re
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


def fix_db_links(apply: bool) -> None:
    print("\n== 4. 봇 DB 의 옛 주소 ==")
    old, new = "https://slow7.soritok.com", "https://soritok.com/slow7"
    with conn() as c:
        n1 = c.execute("SELECT COUNT(*) FROM review_queue WHERE wp_link LIKE ?", (old + "%",)).fetchone()[0]
        n2 = c.execute("SELECT COUNT(*) FROM posts WHERE image_url LIKE ?", (old + "%",)).fetchone()[0]
        print(f"  review_queue {n1}건, posts {n2}건")
        if apply:
            c.execute("UPDATE review_queue SET wp_link = replace(wp_link, ?, ?)", (old, new))
            c.execute("UPDATE posts SET image_url = replace(image_url, ?, ?)", (old, new))
            print("  ✅ 변경")


_GITHUB_A_RE = re.compile(r"<a\b[^>]*href=[\"']https?://github\.com/yolkgit/slow7[^\"']*[\"'][^>]*>([\s\S]*?)</a>", re.I)


def fix_pages(apply: bool) -> None:
    """고정 페이지의 남은 흔적: 개인정보처리방침의 예시 메일 주소, 연락처의 GitHub 원본 링크."""
    print("\n== 5. 고정 페이지 정리 ==")
    for page in _get("pages", per_page=100, context="edit", _fields="id,slug,content"):
        before = page["content"]["raw"]
        after = before.replace("slow7@example.com", "yolkacd@naver.com")
        # GitHub 화면에서 복사해 붙이며 따라온 원본 파일 링크(제목마다 붙어 있음)는
        # 링크만 걷고 글자는 남긴다. 줄째 지우면 제목까지 사라진다.
        after = _GITHUB_A_RE.sub(lambda m: m.group(1), after)
        if after != before:
            print(f"  {page['slug']}: 변경 있음")
            if apply:
                wp._req("POST", f"pages/{page['id']}", json={"content": after})
                print("  ✅ 반영")


_PLINK = r"(?:https?://(?:soritok\.com/slow7|slow7\.soritok\.com))?/?\?p=(\d+)"
_ANCHOR_RE = re.compile(r"<a\b[^>]*?href=([\"'])" + _PLINK + r"\1[^>]*>([\s\S]*?)</a>", re.I)
_LI_RE = re.compile(r"<li>\s*(<a\b[^>]*>[\s\S]*?</a>)\s*</li>\s*", re.I)


def _relink(html: str, links: dict[int, str]) -> tuple[str, int, int]:
    """?p=N 링크를 고유주소로. 없는 글이면 링크만 걷고 글자는 남긴다(목록 항목이면 항목째 삭제)."""
    def target(pid: str) -> str | None:
        pid = int(pid)
        return links.get(pid) or links.get(DUPLICATES.get(pid, -1))

    fixed = dropped = 0

    def drop_li(m):
        nonlocal dropped
        a = _ANCHOR_RE.fullmatch(m.group(1))
        if a and not target(a.group(2)):
            dropped += 1
            return ""
        return m.group(0)

    def sub(m):
        nonlocal fixed, dropped
        url = target(m.group(2))
        if url:
            fixed += 1
            return re.sub(r"href=([\"'])" + _PLINK + r"\1", lambda h: f"href={h.group(1)}{url}{h.group(1)}",
                          m.group(0), count=1)
        dropped += 1
        return m.group(3)

    html = _LI_RE.sub(drop_li, html)
    html = _ANCHOR_RE.sub(sub, html)
    return html, fixed, dropped


def fix_internal_links(apply: bool) -> None:
    print("\n== 6. ?p=숫자 내부 링크 ==")
    posts = wp.list_posts_raw("publish")
    links = {p["id"]: p["link"] for p in posts}
    total_f = total_d = 0
    for p in posts:
        before = p["content"]["raw"]
        after, f, d = _relink(before, links)
        if after == before:
            continue
        total_f += f
        total_d += d
        print(f"  {p['id']} {p['title']['raw']}  고침 {f} · 없는 글 링크 제거 {d}")
        if apply:
            wp.update_post(p["id"], content_html=after)
    print(f"  합계: 고침 {total_f}, 제거 {total_d}")
    # 다음 글의 '관련 글' 목록도 고유주소를 쓰도록 봇 DB 갱신
    if apply:
        with conn() as c:
            for pid, url in links.items():
                c.execute("UPDATE review_queue SET wp_link=? WHERE wp_post_id=?", (url, str(pid)))
        print("  ✅ 봇 DB 링크 갱신")


def main() -> int:
    apply = "--apply" in sys.argv
    db.init()
    merge_duplicates(apply)
    update_about(apply)
    recategorize(apply)
    fix_db_links(apply)
    fix_pages(apply)
    fix_internal_links(apply)
    if not apply:
        print("\n바꾼 것은 없습니다. 실제 반영은 --apply 로 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
