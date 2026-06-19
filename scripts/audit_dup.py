"""발행 이력 중복 진단 — 비슷한 글을 반복했는지 확인.

    python -m scripts.audit_dup
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db
from src.db import conn

# 핵심 메시지가 겹치기 쉬운 주제군 (키워드로 클러스터)
CLUSTERS = {
    "지방연소/대사": ["fat", "mitochondria", "zone2", "science_fat", "insulin", "fasted", "post_meal", "대사", "지방"],
    "시작/동기/습관": ["start", "3min", "streak", "mindset", "buddy", "시작", "습관", "동기"],
    "자세/폼": ["forefoot", "stride", "posture", "arm", "cadence", "자세", "착지", "보폭"],
    "호흡": ["breath", "talk_test", "호흡"],
    "회복/수면": ["recovery", "sleep", "cooldown", "회복", "수면"],
    "비교": ["c_", "vs"],
    "플랜/루틴": ["p_", "plan", "routine", "주차", "플랜"],
}


def _cluster_of(topic_key: str, title: str) -> str:
    hay = (topic_key + " " + title).lower()
    for name, kws in CLUSTERS.items():
        if any(k in hay for k in kws):
            return name
    return "기타"


def main() -> int:
    db.init()
    with conn() as c:
        rows = c.execute(
            "SELECT topic_key, text, created_at FROM posts WHERE slot='blog' ORDER BY created_at"
        ).fetchall()

    if not rows:
        print("발행 이력 없음 (slot='blog')")
        return 0

    print(f"=== 총 {len(rows)}개 블로그 글 발행 이력 ===\n")

    # 1) 같은 토픽 반복
    topic_counts = Counter(r["topic_key"] for r in rows)
    dups = {k: v for k, v in topic_counts.items() if v > 1}
    if dups:
        print("⚠️  같은 토픽 2회 이상 발행:")
        for k, v in sorted(dups.items(), key=lambda x: -x[1]):
            print(f"   {k}: {v}회")
    else:
        print("✅ 같은 토픽 중복 발행 없음")

    # 2) 주제군별 분포 (내용 겹침 위험)
    cluster_counts = Counter(_cluster_of(r["topic_key"], r["text"] or "") for r in rows)
    print("\n=== 주제군별 발행 수 (한 군에 몰리면 내용 겹침 위험) ===")
    for name, n in cluster_counts.most_common():
        bar = "█" * n
        flag = " ⚠️ 편중" if n >= 4 else ""
        print(f"   {name:<14} {n:>2}개 {bar}{flag}")

    # 3) 전체 제목 목록 (사람이 눈으로 중복 확인)
    print("\n=== 발행된 제목 목록 (시간순) ===")
    for i, r in enumerate(rows, 1):
        cl = _cluster_of(r["topic_key"], r["text"] or "")
        print(f"   {i:>2}. [{cl}] {r['text']}")

    print("\n→ 같은 주제군이 연달아 많으면 토픽 다양화 필요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
