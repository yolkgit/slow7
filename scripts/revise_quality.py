"""발행된 슬로우7 글을 품질 규칙(출처·의료 표현·문체·지어낸 경험 제거)에 맞게 일괄 수정.

기본은 미리보기다. 워드프레스는 건드리지 않고 logs/revisions/ 에 수정 전·후 HTML 을 저장한다.
결과를 확인한 뒤 --apply 로 실제 반영한다. 워드프레스가 이전 판을 '리비전'으로 남기므로
글 편집 화면의 '리비전' 메뉴에서 언제든 되돌릴 수 있다.

사용법 (서버의 slow7 폴더에서):
    .venv/bin/python -m scripts.revise_quality                 # 3편 미리보기
    .venv/bin/python -m scripts.revise_quality --limit 10      # 10편 미리보기
    .venv/bin/python -m scripts.revise_quality --apply --limit 50   # 실제 반영
    .venv/bin/python -m scripts.revise_quality --id 123 --apply     # 특정 글만

이미 고친 글은 본문 맨 끝의 표식(QUALITY_MARK)을 보고 건너뛴다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import blog_writer, config, wordpress_client

QUALITY_MARK = "<!-- slow7-quality:v1 -->"
OUT_DIR = config.ROOT / "logs" / "revisions"


def _text_len(html: str) -> int:
    return len(re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", html)))


def _check(before: str, after: str) -> list[str]:
    """수정 결과가 원본을 망가뜨리지 않았는지 확인."""
    problems = []
    if before.count("<img") != after.count("<img"):
        problems.append(f"이미지 개수 변경 {before.count('<img')} → {after.count('<img')}")
    if "정보 제공을 목적" in before and "정보 제공을 목적" not in after:
        problems.append("면책 문구 사라짐")
    if _text_len(after) < _text_len(before) * 0.6:
        problems.append(f"본문이 너무 짧아짐 {_text_len(before)} → {_text_len(after)}자")
    if "참고 자료" not in after:
        problems.append("참고 자료 섹션 없음")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="워드프레스에 실제 반영")
    ap.add_argument("--limit", type=int, default=3, help="이번에 처리할 글 수")
    ap.add_argument("--id", type=int, help="특정 글 ID 만 처리")
    args = ap.parse_args()

    missing = config.validate_wp()
    if missing:
        print(f"환경 변수 누락: {missing}")
        return 1

    posts = wordpress_client.list_posts_raw()
    if args.id:
        posts = [p for p in posts if p["id"] == args.id]
    todo = [p for p in posts if QUALITY_MARK not in p["content"]["raw"]][: args.limit]
    print(f"전체 {len(posts)}편 중 이번 처리 {len(todo)}편 ({'반영' if args.apply else '미리보기'})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for p in todo:
        pid, slug = p["id"], p["slug"]
        title, before = p["title"]["raw"], p["content"]["raw"]
        print(f"\n▶ {pid} {title}")
        try:
            res = blog_writer.revise_for_quality(title, before)
        except Exception as e:  # 한 편이 실패해도 나머지는 계속
            print(f"  ✗ 수정 실패: {e}")
            fail += 1
            continue
        after = res["content_html"].rstrip() + "\n" + QUALITY_MARK
        problems = _check(before, after)
        (OUT_DIR / f"{pid}-{slug}.before.html").write_text(before, encoding="utf-8")
        (OUT_DIR / f"{pid}-{slug}.after.html").write_text(
            f"<h1>{res['title']}</h1>\n{after}", encoding="utf-8")
        if problems:
            print(f"  ✗ 검사 실패, 반영 안 함: {problems}")
            fail += 1
            continue
        if args.apply:
            wordpress_client.update_post(pid, title=res["title"], content_html=after)
            print(f"  ✓ 반영됨 {p['link']}")
        else:
            print(f"  ✓ 미리보기 저장: logs/revisions/{pid}-{slug}.after.html")
        ok += 1

    print(f"\n완료: 성공 {ok}, 실패 {fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
