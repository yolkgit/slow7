#!/usr/bin/env bash
# 슬로우7 SNS 하루 3번 게시 (서버 cron용)
set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)

.venv/bin/python -m scripts.sns_post >> "$LOG_DIR/sns_$TS.log" 2>&1
echo "[$(date)] SNS 게시 완료 → $LOG_DIR/sns_$TS.log"

find "$LOG_DIR" -name 'sns_*.log' -mtime +14 -delete 2>/dev/null || true
