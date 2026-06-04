"""성과 추적 — 본인 게시물 insights 수집 + 토픽별 성과 리포트.

    python -m scripts.track          # insights 수집 + 리포트 출력
    python -m scripts.track report   # 수집 없이 현재 DB 기준 리포트만

흐름:
    1) DB의 최근 게시물(threads_id) 가져옴
    2) 각각 Threads insights API 호출 → views/likes/replies/... 수집
    3) DB에 갱신
    4) 토픽별 평균 인게이지먼트 점수 리포트 출력
       → 이 점수가 다음 게시 때 토픽 가중 선택에 자동 반영됨
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db, threads_client


def collect() -> int:
    """최근 게시물 insights 수집 → DB 갱신. 갱신 개수 반환."""
    posts = db.posts_for_metrics(limit=50)
    if not posts:
        print("[track] 추적할 게시물 없음 (아직 게시 이력 없음)")
        return 0

    updated = 0
    for p in posts:
        tid = p["threads_id"]
        m = threads_client.fetch_media_insights(tid)
        db.update_metrics(tid, m)
        updated += 1
        print(
            f"[track] {p['topic_key']:<16} views={m['views']:<5} "
            f"likes={m['likes']:<4} replies={m['replies']:<3} "
            f"reposts={m['reposts']:<3} quotes={m['quotes']:<3}"
        )
        time.sleep(0.5)  # API 레이트리밋 배려
    print(f"[track] {updated}개 게시물 성과 갱신 완료")
    return updated


def report() -> None:
    """토픽별 성과 리포트 출력."""
    perf = db.topic_performance()
    if not perf:
        print("[track] 아직 성과 데이터 없음. 며칠 게시 후 다시 확인.")
        return

    print("\n========== 슬로우7 토픽별 성과 리포트 ==========")
    print(f"{'토픽':<18}{'게시수':>5}{'평균점수':>9}{'평균조회':>9}{'좋아요':>7}{'답글':>6}")
    print("-" * 60)
    for r in perf:
        print(
            f"{r['topic_key']:<18}{r['n']:>5}{(r['avg_score'] or 0):>9.1f}"
            f"{(r['avg_views'] or 0):>9.0f}{(r['likes'] or 0):>7}{(r['replies'] or 0):>6}"
        )
    print("-" * 60)
    best = perf[0]
    print(f"🏆 최고 성과 토픽: {best['topic_key']} (평균점수 {best['avg_score']:.1f})")
    if len(perf) > 1:
        worst = perf[-1]
        print(f"📉 개선 필요 토픽: {worst['topic_key']} (평균점수 {worst['avg_score']:.1f})")
    print("→ 이 점수는 다음 게시 때 토픽 선택 가중치에 자동 반영됨\n")


def main(argv: list[str]) -> int:
    db.init()
    if argv and argv[0] == "report":
        report()
        return 0

    missing = config.validate(require_threads=True, require_claude=False)
    if missing:
        print(f"환경변수 누락: {missing}")
        return 2

    collect()
    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
