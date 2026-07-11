#!/usr/bin/env bash
# 슬로우7 텔레그램 검수 봇 (서버 cron용)
# 사용: cron이 주기적으로 호출 → 텔레그램 응답 확인 후 발행/수정 처리
set -euo pipefail

cd "$(dirname "$0")/.."

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

.venv/bin/python -m scripts.review_bot >> "$LOG_DIR/review.log" 2>&1

# 로그 너무 커지면 잘라내기 (최근 1000줄만)
if [ -f "$LOG_DIR/review.log" ]; then
  tail -n 1000 "$LOG_DIR/review.log" > "$LOG_DIR/review.log.tmp" && mv "$LOG_DIR/review.log.tmp" "$LOG_DIR/review.log"
fi
