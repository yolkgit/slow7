#!/usr/bin/env bash
# 슬로우7 블로그를 slow7.soritok.com → soritok.com/slow7/ 로 옮긴다.
#
# 왜: 애드센스는 루트 도메인(soritok.com) 단위로 심사하는데, 루트에는 자체 글이
#     하나도 없고 글 47편은 전부 서브도메인에 있었다. 블로그를 루트 경로 아래로
#     옮겨 심사 대상 도메인의 콘텐츠로 만든다.
#
# 사용 (서버, ~/slow7-wp/slow7-bot 에서):
#   bash server/migrate_to_subpath.sh            # 점검만 (아무것도 안 바꿈)
#   bash server/migrate_to_subpath.sh --apply    # 실제 이전
#
# 하는 일 (--apply):
#   0. 백업: DB 덤프, nginx 설정 두 개 → ~/slow7-migrate-backup-<시각>/
#   1. 워드프레스 컨테이너에 /var/www/html/slow7 → . 심볼릭 링크
#      (nginx 가 /slow7/... 경로를 그대로 넘기므로 정적 파일도 그 경로로 찾게 한다)
#   2. DB 안의 //slow7.soritok.com 을 //soritok.com/slow7 로 일괄 치환 (wp-cli)
#      → home/siteurl, 본문 이미지·내부 링크, Yoast 설정이 모두 바뀐다
#   3. mu-plugins 최신본 복사, 고유주소 규칙·캐시 비우기
#   4. 호스트 nginx: soritok.com 에 /slow7/ 프록시 추가,
#      slow7.soritok.com 은 전부 soritok.com/slow7/... 로 301
#   5. 봇 .env 의 WP_SITE_URL 변경
# 실패하면 nginx 는 백업으로 되돌린다. DB 는 백업 덤프로 복구할 수 있다(맨 아래 안내).
set -euo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

WP=slow7_wp
DB=slow7_db
OLD='//slow7.soritok.com'
NEW='//soritok.com/slow7'
PORT=8090
BOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TS=$(date +%Y%m%d_%H%M%S)
BK="$HOME/slow7-migrate-backup-$TS"

say() { echo "[migrate] $*"; }

# ── 점검 ────────────────────────────────────────────────────────────
docker inspect "$WP" >/dev/null || { say "컨테이너 $WP 없음"; exit 1; }
docker inspect "$DB" >/dev/null || { say "컨테이너 $DB 없음"; exit 1; }
if docker exec "$WP" env | grep -qE 'WP_HOME|WP_SITEURL'; then
    say "컨테이너 환경변수에 WP_HOME/WP_SITEURL 이 고정돼 있음 — docker-compose 에서 먼저 바꿔야 함"; exit 1
fi

NGX_MAIN=$(grep -lE 'server_name\s+(www\.)?soritok\.com[ ;]' /etc/nginx/sites-enabled/* | head -1)
NGX_SLOW7=$(grep -l 'slow7\.soritok\.com' /etc/nginx/sites-enabled/* | head -1)
[ -n "$NGX_MAIN" ] && [ -n "$NGX_SLOW7" ] || { say "nginx 설정 파일을 못 찾음 (main=$NGX_MAIN slow7=$NGX_SLOW7)"; exit 1; }
[ "$NGX_MAIN" != "$NGX_SLOW7" ] || { say "soritok.com 과 slow7 이 같은 파일에 있음 — 자동 수정 중단, 수동 처리 필요: $NGX_MAIN"; exit 1; }
NGX_MAIN=$(readlink -f "$NGX_MAIN"); NGX_SLOW7=$(readlink -f "$NGX_SLOW7")
say "nginx soritok.com : $NGX_MAIN"
say "nginx slow7       : $NGX_SLOW7"

# wp-cli: 공식 이미지에 없어서 phar 를 컨테이너에 넣어 쓴다
if ! docker exec "$WP" test -f /tmp/wp-cli.phar; then
    curl -fsSL -o /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
    docker cp /tmp/wp-cli.phar "$WP":/tmp/wp-cli.phar
fi
wp() { docker exec -u www-data "$WP" php /tmp/wp-cli.phar --path=/var/www/html "$@"; }

say "현재 home   : $(wp option get home)"
say "현재 siteurl: $(wp option get siteurl)"
say "치환 미리보기 ($OLD → $NEW):"
wp search-replace "$OLD" "$NEW" --all-tables-with-prefix --skip-columns=guid --dry-run --report-changed-only

if [ "$APPLY" -ne 1 ]; then
    say "점검만 했습니다. 실제 이전은 --apply 로 다시 실행하세요."
    exit 0
fi

# ── 0. 백업 ─────────────────────────────────────────────────────────
mkdir -p "$BK"
docker exec "$DB" sh -c 'P="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}"; mariadb-dump -uroot -p"$P" --all-databases' > "$BK/db.sql" \
  || docker exec "$DB" sh -c 'U="${MARIADB_USER:-$MYSQL_USER}"; P="${MARIADB_PASSWORD:-$MYSQL_PASSWORD}"; D="${MARIADB_DATABASE:-$MYSQL_DATABASE}"; mariadb-dump -u"$U" -p"$P" "$D"' > "$BK/db.sql"
[ -s "$BK/db.sql" ] || { say "DB 백업 실패 — 중단"; exit 1; }
sudo cp "$NGX_MAIN" "$BK/nginx-main.conf"
sudo cp "$NGX_SLOW7" "$BK/nginx-slow7.conf"
say "백업 완료: $BK"

# ── 1. 경로 심볼릭 링크 ─────────────────────────────────────────────
docker exec "$WP" sh -c 'cd /var/www/html && [ -e slow7 ] || ln -s . slow7'

# ── 2. URL 치환 ─────────────────────────────────────────────────────
wp search-replace "$OLD" "$NEW" --all-tables-with-prefix --skip-columns=guid --report-changed-only
say "변경 후 home: $(wp option get home)"

# ── 3. mu-plugins, 고유주소, 캐시 ───────────────────────────────────
for f in "$BOT_DIR"/server/mu-plugins/*.php; do
    docker cp "$f" "$WP":/var/www/html/wp-content/mu-plugins/
done
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/mu-plugins
wp rewrite flush --hard
docker exec "$WP" sh -c 'rm -rf /var/www/html/wp-content/cache/supercache/* 2>/dev/null || true'

# ── 4. nginx ────────────────────────────────────────────────────────
SNIP=/etc/nginx/snippets/slow7-subpath.conf
sudo tee "$SNIP" >/dev/null <<NGX
# 슬로우7 블로그 (워드프레스 컨테이너). 경로를 자르지 않고 그대로 넘긴다:
# 컨테이너 안 /var/www/html/slow7 → . 링크가 있어 /slow7/wp-content/... 도 찾는다.
location = /slow7 { return 301 /slow7/; }
location ^~ /slow7/ {
    proxy_pass http://127.0.0.1:$PORT;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    client_max_body_size 50m;
}
NGX

restore_nginx() {
    say "nginx 설정 오류 — 백업으로 되돌립니다"
    sudo cp "$BK/nginx-main.conf" "$NGX_MAIN"
    sudo cp "$BK/nginx-slow7.conf" "$NGX_SLOW7"
    sudo nginx -t && sudo systemctl reload nginx
}

# soritok.com 의 각 server 블록에서 'location / {' 앞에 include 를 넣는다 (중복 방지)
if ! sudo grep -q 'slow7-subpath.conf' "$NGX_MAIN"; then
    sudo sed -i 's|^\(\s*\)location / {|\1include snippets/slow7-subpath.conf;\n\1location / {|' "$NGX_MAIN"
fi
# slow7.soritok.com 은 server_name 바로 뒤에서 전부 새 주소로 301
if ! sudo grep -q 'soritok.com/slow7' "$NGX_SLOW7"; then
    sudo sed -i 's|^\(\s*\)server_name\(\s\+\)slow7\.soritok\.com;|&\n\1return 301 https://soritok.com/slow7$request_uri;|' "$NGX_SLOW7"
fi
sudo grep -q 'slow7-subpath.conf' "$NGX_MAIN" || say "주의: $NGX_MAIN 에 'location / {' 가 없어 include 를 못 넣음 — 수동 추가 필요"
sudo grep -q 'soritok.com/slow7' "$NGX_SLOW7" || say "주의: $NGX_SLOW7 에 301 을 못 넣음 — 수동 추가 필요"
if sudo nginx -t; then
    sudo systemctl reload nginx
else
    restore_nginx
    exit 1
fi

# ── 5. 봇 설정 ──────────────────────────────────────────────────────
if [ -f "$BOT_DIR/.env" ]; then
    cp "$BOT_DIR/.env" "$BK/bot.env"
    sed -i 's|^WP_SITE_URL=.*|WP_SITE_URL=https://soritok.com/slow7|' "$BOT_DIR/.env"
fi

# ── 확인 ────────────────────────────────────────────────────────────
sleep 1
for u in https://soritok.com/slow7/ https://soritok.com/slow7/sitemap_index.xml https://soritok.com/slow7/wp-json/ https://slow7.soritok.com/about/; do
    echo "  $(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$u")  $u"
done
cd "$BOT_DIR" && .venv/bin/python -m scripts.wp_check || true

cat <<EOF

[migrate] 완료. 백업: $BK
  되돌리기가 필요하면:
    sudo cp $BK/nginx-main.conf $NGX_MAIN && sudo cp $BK/nginx-slow7.conf $NGX_SLOW7 && sudo nginx -t && sudo systemctl reload nginx
    docker exec -i $DB sh -c 'mariadb -uroot -p"\${MARIADB_ROOT_PASSWORD:-\$MYSQL_ROOT_PASSWORD}"' < $BK/db.sql
    cp $BK/bot.env $BOT_DIR/.env
EOF
