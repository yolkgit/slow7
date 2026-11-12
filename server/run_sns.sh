#!/usr/bin/env bash
# 슬로우7 SNS 게시 (서버 cron용)
# 아침(5~10시)·점심(11~14시)에만 실제로 올리고, 그 밖의 시각이나
# 같은 슬롯 두 번째 실행은 스크립트가 알아서 건너뛴다.
# 권장 crontab:  30 7 * * *  와  20 12 * * *
set -euo pipefail
cd "$(dirname "$0")/.."

# 최신 코드 반영 (실패해도 계속)
git pull --quiet 2>/dev/null || true

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)

.venv/bin/python -m scripts.sns_post >> "$LOG_DIR/sns_$TS.log" 2>&1
echo "[$(date)] SNS 게시 완료 → $LOG_DIR/sns_$TS.log"

find "$LOG_DIR" -name 'sns_*.log' -mtime +14 -delete 2>/dev/null || true
