"""손으로 고친 글(revisions/done/{id}.html)을 워드프레스에 반영한다. Anthropic API 는 쓰지 않는다.

파일 첫 줄에 <!-- title: 새 제목 --> 이 있으면 제목도 바꾼다.
반영 전 revise_quality 와 같은 검사(이미지 수, 면책 문구, 분량, 참고 자료, 사진 출처, 편집 메모)를 한다.

사용법 (서버의 slow7 폴더에서):
    .venv/bin/python -m scripts.apply_revisions            # 검사만
    .venv/bin/python -m scripts.apply_revisions --apply    # 실제 반영
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, wordpress_client
from scripts.revise_quality import QUALITY_MARK, _check

DONE_DIR = config.ROOT / "revisions" / "done"
_TITLE_RE = re.compile(r"^\s*<!--\s*title:\s*(.+?)\s*-->\s*\n", re.S)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="워드프레스에 실제 반영")
    args = ap.parse_args()

    files = sorted(DONE_DIR.glob("*.html"), key=lambda f: int(f.stem))
    posts = {p["id"]: p for p in wordpress_client.list_posts_raw()}
    print(f"고친 파일 {len(files)}개 ({'반영' if args.apply else '검사만'})")

    ok = fail = skip = 0
    for f in files:
        pid = int(f.stem)
        p = posts.get(pid)
        if not p:
            print(f"✗ {pid} 워드프레스에 없는 글")
            fail += 1
            continue
        before = p["content"]["raw"]
        if QUALITY_MARK in before:
            print(f"- {pid} 이미 고친 글, 건너뜀")
            skip += 1
            continue
        text = f.read_text(encoding="utf-8")
        m = _TITLE_RE.match(text)
        title = m.group(1) if m else p["title"]["raw"]
        body = text[m.end():] if m else text
        after = body.rstrip() + "\n" + QUALITY_MARK
        problems = _check(before, after)
        if problems:
            print(f"✗ {pid} {title} 검사 실패: {problems}")
            fail += 1
            continue
        if args.apply:
            wordpress_client.update_post(pid, title=title, content_html=after)
            print(f"✓ {pid} 반영됨 {p['link']}")
        else:
            print(f"✓ {pid} 검사 통과 {title}")
        ok += 1

    print(f"\n완료: 성공 {ok}, 실패 {fail}, 건너뜀 {skip}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
