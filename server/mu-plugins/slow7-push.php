<?php
/**
 * Slow7 — 웹 푸시 구독 수집.
 *
 * 설치: wp-content/mu-plugins/ 에 두면 자동 활성화.
 *
 * 역할은 "구독 수집·보관"까지만이다. 실제 발송은 파이썬 봇이
 * 글 발행 시점(scripts/review_bot.py 의 _publish)에 처리한다.
 * 발송 로직을 봇에 둔 이유는 발행 훅이 이미 거기 있고, 개인키를
 * 워드프레스가 아닌 봇의 .env 한 곳에만 두기 위해서다.
 *
 * 엔드포인트
 *   POST   /wp-json/slow7/v1/push/subscribe    구독 저장 (공개)
 *   POST   /wp-json/slow7/v1/push/unsubscribe  구독 해제 (공개)
 *   GET    /wp-json/slow7/v1/push/list         구독 목록 (관리자 인증 필요 — 봇이 사용)
 *   DELETE /wp-json/slow7/v1/push/prune        만료 구독 삭제 (관리자 인증 필요)
 *
 * 구독 요청 프롬프트는 "글을 어느 정도 읽은 사람"에게만 띄운다.
 * 첫 방문에 바로 물으면 대부분 거부하고, 거부는 되돌리기 어렵다.
 */

if (!defined('ABSPATH')) {
    exit;
}

const SLOW7_PUSH_TABLE   = 'slow7_push_subs';
const SLOW7_PUSH_VERSION = '1';

/** 구독 저장 테이블 (엔드포인트 기준 중복 방지) */
function slow7_push_install()
{
    global $wpdb;
    $table   = $wpdb->prefix . SLOW7_PUSH_TABLE;
    $charset = $wpdb->get_charset_collate();
    $sql = "CREATE TABLE $table (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        endpoint VARCHAR(500) NOT NULL,
        p256dh VARCHAR(255) NOT NULL,
        auth VARCHAR(255) NOT NULL,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY endpoint (endpoint(191))
    ) $charset;";
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta($sql);
    update_option('slow7_push_db_version', SLOW7_PUSH_VERSION);
}
add_action('init', function () {
    if (get_option('slow7_push_db_version') !== SLOW7_PUSH_VERSION) {
        slow7_push_install();
    }
});

/* ------------------------------------------------------------------
   REST API
   ------------------------------------------------------------------ */

add_action('rest_api_init', function () {
    register_rest_route('slow7/v1', '/push/subscribe', [
        'methods'             => 'POST',
        'permission_callback' => '__return_true', // 방문자 누구나 구독 가능
        'callback'            => 'slow7_push_subscribe',
    ]);
    register_rest_route('slow7/v1', '/push/unsubscribe', [
        'methods'             => 'POST',
        'permission_callback' => '__return_true',
        'callback'            => 'slow7_push_unsubscribe',
    ]);
    register_rest_route('slow7/v1', '/push/list', [
        'methods'             => 'GET',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback'            => 'slow7_push_list',
    ]);
    register_rest_route('slow7/v1', '/push/prune', [
        'methods'             => 'DELETE',
        'permission_callback' => function () { return current_user_can('manage_options'); },
        'callback'            => 'slow7_push_prune',
    ]);
});

function slow7_push_subscribe($req)
{
    global $wpdb;
    $b = $req->get_json_params();
    $endpoint = isset($b['endpoint']) ? esc_url_raw($b['endpoint']) : '';
    $p256dh   = isset($b['keys']['p256dh']) ? sanitize_text_field($b['keys']['p256dh']) : '';
    $auth     = isset($b['keys']['auth']) ? sanitize_text_field($b['keys']['auth']) : '';

    if (!$endpoint || !$p256dh || !$auth) {
        return new WP_Error('bad_request', '구독 정보가 올바르지 않다', ['status' => 400]);
    }
    // 푸시 서비스 도메인만 허용 (임의 URL 로의 발송 방지)
    $host = wp_parse_url($endpoint, PHP_URL_HOST);
    $ok = false;
    foreach (['push.services.mozilla.com', 'fcm.googleapis.com', 'web.push.apple.com',
              'notify.windows.com', 'wns2-*.notify.windows.com'] as $allow) {
        if ($host && (fnmatch($allow, $host) || str_ends_with($host, 'push.apple.com'))) { $ok = true; break; }
    }
    if (!$ok) {
        return new WP_Error('bad_endpoint', '허용되지 않은 푸시 엔드포인트다', ['status' => 400]);
    }

    $table = $wpdb->prefix . SLOW7_PUSH_TABLE;
    $wpdb->query($wpdb->prepare(
        "INSERT INTO $table (endpoint, p256dh, auth, created_at) VALUES (%s, %s, %s, %s)
         ON DUPLICATE KEY UPDATE p256dh = VALUES(p256dh), auth = VALUES(auth)",
        $endpoint, $p256dh, $auth, current_time('mysql')
    ));
    return ['ok' => true];
}

function slow7_push_unsubscribe($req)
{
    global $wpdb;
    $b = $req->get_json_params();
    $endpoint = isset($b['endpoint']) ? esc_url_raw($b['endpoint']) : '';
    if (!$endpoint) {
        return new WP_Error('bad_request', 'endpoint 가 필요하다', ['status' => 400]);
    }
    $table = $wpdb->prefix . SLOW7_PUSH_TABLE;
    $wpdb->delete($table, ['endpoint' => $endpoint]);
    return ['ok' => true];
}

function slow7_push_list()
{
    global $wpdb;
    $table = $wpdb->prefix . SLOW7_PUSH_TABLE;
    $rows = $wpdb->get_results("SELECT endpoint, p256dh, auth FROM $table", ARRAY_A);
    return ['count' => count($rows), 'subscriptions' => $rows];
}

function slow7_push_prune($req)
{
    global $wpdb;
    $endpoints = (array) $req->get_json_params()['endpoints'];
    if (!$endpoints) return ['deleted' => 0];
    $table = $wpdb->prefix . SLOW7_PUSH_TABLE;
    $n = 0;
    foreach ($endpoints as $e) {
        $n += (int) $wpdb->delete($table, ['endpoint' => esc_url_raw($e)]);
    }
    return ['deleted' => $n];
}

/* ------------------------------------------------------------------
   서비스워커 — 루트 스코프(/sw.js)로 서빙해야 사이트 전체를 담당한다
   ------------------------------------------------------------------ */

add_action('init', function () {
    add_rewrite_rule('^sw\.js$', 'index.php?slow7_sw=1', 'top');
});
add_filter('query_vars', function ($v) { $v[] = 'slow7_sw'; return $v; });

// 워드프레스가 /sw.js → /sw.js/ 로 정규화 리다이렉트하면 서비스워커 등록이
// 실패한다(등록 시 리다이렉트 불허). 이 경로만 정규화를 끈다.
add_filter('redirect_canonical', function ($url) {
    return get_query_var('slow7_sw') ? false : $url;
});

add_action('template_redirect', function () {
    if (!get_query_var('slow7_sw')) return;
    header('Content-Type: application/javascript; charset=utf-8');
    header('Service-Worker-Allowed: /');
    header('Cache-Control: max-age=0, no-cache'); ?>
self.addEventListener('push', function (event) {
  var d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) { d = { title: '슬로우7', body: event.data ? event.data.text() : '' }; }
  event.waitUntil(self.registration.showNotification(d.title || '슬로우7 새 글', {
    body: d.body || '',
    icon: d.icon || '<?php echo esc_js(get_site_icon_url(192) ?: ''); ?>',
    badge: d.badge || '<?php echo esc_js(get_site_icon_url(96) ?: ''); ?>',
    data: { url: d.url || '<?php echo esc_js(home_url('/')); ?>' },
    tag: 'slow7-post',
    renotify: true
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      if (list[i].url === url && 'focus' in list[i]) return list[i].focus();
    }
    return clients.openWindow(url);
  }));
});
<?php
    exit;
});

/* ------------------------------------------------------------------
   구독 UI — 글을 읽은 사람에게만 노출
   ------------------------------------------------------------------ */

function slow7_push_frontend()
{
    $pub = get_option('slow7_vapid_public_key', '');
    if (!$pub) return; // 공개키 미설정이면 아무것도 하지 않는다
    ?>
<div class="s7p" id="s7p" hidden>
  <div class="s7p__body">
    <strong class="s7p__title">새 글 나오면 알려줄까?</strong>
    <p class="s7p__desc">슬로우조깅 글이 올라올 때만 딱 알림 보낼게. 광고는 안 보낸다. 언제든 끌 수 있어.</p>
  </div>
  <div class="s7p__actions">
    <button type="button" class="s7p__no" id="s7pNo">괜찮아</button>
    <button type="button" class="s7p__yes" id="s7pYes">알림 받기</button>
  </div>
</div>
<script>
(function () {
  var PUB = '<?php echo esc_js($pub); ?>';
  var API = '<?php echo esc_js(rest_url('slow7/v1/push/')); ?>';
  var SEEN = 'slow7.push.asked';

  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
  if (Notification.permission === 'denied') return;      // 이미 거부 → 다시 묻지 않음
  if (localStorage.getItem(SEEN)) return;                 // 이미 물어봄
  if (Notification.permission === 'granted') return;      // 이미 구독

  var box = document.getElementById('s7p');
  if (!box) return;

  // 글을 60% 이상 읽었을 때만 노출 (첫 화면에서 바로 물으면 대부분 거부한다)
  var shown = false;
  function maybeShow() {
    if (shown) return;
    var h = document.documentElement;
    var read = (h.scrollTop + window.innerHeight) / h.scrollHeight;
    if (read < 0.6) return;
    shown = true;
    box.hidden = false;
    box.classList.add('s7p--in');
    window.removeEventListener('scroll', maybeShow);
  }
  window.addEventListener('scroll', maybeShow, { passive: true });

  document.getElementById('s7pNo').addEventListener('click', function () {
    localStorage.setItem(SEEN, '1');
    box.hidden = true;
  });

  function urlB64ToUint8(b64) {
    var pad = '='.repeat((4 - (b64.length % 4)) % 4);
    var raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from([].map.call(raw, function (c) { return c.charCodeAt(0); }));
  }

  document.getElementById('s7pYes').addEventListener('click', function () {
    localStorage.setItem(SEEN, '1');
    box.hidden = true;
    navigator.serviceWorker.register('/sw.js').then(function (reg) {
      return Notification.requestPermission().then(function (p) {
        if (p !== 'granted') return;
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlB64ToUint8(PUB)
        }).then(function (sub) {
          return fetch(API + 'subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sub)
          });
        });
      });
    }).catch(function (e) { console.warn('[slow7] push 등록 실패', e); });
  });
})();
</script>
<style>
.s7p{position:fixed;left:50%;transform:translate(-50%,120%);bottom:18px;z-index:9999;width:min(440px,calc(100vw - 24px));
  background:#fff;border:1px solid #e5ded0;border-radius:14px;box-shadow:0 12px 34px rgba(60,40,20,.22);padding:18px 20px;transition:transform .35s ease}
.s7p--in{transform:translate(-50%,0)}
.s7p__title{display:block;font-size:1rem;color:#3a2d1a;margin-bottom:6px}
.s7p__desc{margin:0;font-size:.86rem;line-height:1.55;color:#6b5340}
.s7p__actions{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
.s7p__no,.s7p__yes{border:0;border-radius:999px;padding:9px 18px;font-size:.88rem;font-weight:700;cursor:pointer}
.s7p__no{background:#f1ece2;color:#7a6650}
.s7p__yes{background:#e8743b;color:#fff}
.s7p__yes:hover{background:#d4602a}
</style>
<?php }
add_action('wp_footer', 'slow7_push_frontend');
