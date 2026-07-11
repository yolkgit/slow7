#!/usr/bin/env bash
# 스레드 장기 토큰 자동 갱신 (60일 만료 → 갱신하면 다시 60일)
# 주 1회 cron으로 실행. 발급 후 24시간 지나야 갱신 가능.
set -euo pipefail
cd "$(dirname "$0")/.."

LOG="logs/threads_refresh.log"
mkdir -p logs

CURRENT=$(grep '^THREADS_PROMO_TOKEN=' .env | cut -d= -f2-)
if [ -z "$CURRENT" ]; then
  echo "[$(date)] THREADS_PROMO_TOKEN 없음 — skip" >> "$LOG"
  exit 0
fi

RESP=$(curl -s -G "https://graph.threads.net/refresh_access_token" \
  --data-urlencode "grant_type=th_refresh_token" \
  --data-urlencode "access_token=$CURRENT")

NEW=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -n "$NEW" ] && [ ${#NEW} -gt 50 ]; then
  # .env의 토큰 교체
  sed -i "s|^THREADS_PROMO_TOKEN=.*|THREADS_PROMO_TOKEN=$NEW|" .env
  echo "[$(date)] ✅ 스레드 토큰 갱신 성공 (길이 ${#NEW})" >> "$LOG"
else
  echo "[$(date)] ❌ 갱신 실패: $RESP" >> "$LOG"
fi

# 로그 크기 관리
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
