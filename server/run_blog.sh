#!/usr/bin/env bash
# 슬로우7 블로그 자동 발행 실행 스크립트 (서버 cron용)
# 사용: cron이 이 스크립트를 주기적으로 호출 → draft 글 1개 생성
set -euo pipefail

# 이 스크립트가 있는 위치 기준으로 프로젝트 루트 이동
cd "$(dirname "$0")/.."

# 최신 코드 반영 (선택 — git pull 실패해도 계속)
git pull --quiet 2>/dev/null || true

# 가상환경 파이썬으로 발행
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)

.venv/bin/python -m scripts.publish_blog >> "$LOG_DIR/blog_$TS.log" 2>&1
echo "[$(date)] 발행 시도 완료 → $LOG_DIR/blog_$TS.log"

# 오래된 로그 정리 (30일 이상)
find "$LOG_DIR" -name 'blog_*.log' -mtime +30 -delete 2>/dev/null || true
