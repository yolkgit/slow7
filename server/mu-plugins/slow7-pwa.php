<?php
/**
 * Slow7 — PWA(홈 화면 설치) 지원.
 *
 * 설치: wp-content/mu-plugins/ 에 두면 자동 활성화.
 *
 * 존재 이유는 딱 하나다. iOS Safari 는 "홈 화면에 추가"된 웹앱에서만
 * 웹 푸시를 허용한다. manifest 가 없으면 추가 자체가 불가능해서
 * 아이폰 사용자는 알림을 받을 방법이 아예 없다.
 *
 *  - /manifest.json  루트로 서빙 (설치 요건)
 *  - iOS  : 자동 설치 API 가 없어 "공유 → 홈 화면에 추가" 안내를 띄운다
 *  - 안드로이드/크롬 : beforeinstallprompt 를 잡아 설치 버튼을 띄운다
 *
 * 안내는 본문을 어느 정도 읽은 사람에게만, 한 번만 보여준다.
 */

if (!defined('ABSPATH')) {
    exit;
}

/* ------------------------------------------------------------------
   manifest.json — 루트 경로로 서빙
   ------------------------------------------------------------------ */

add_action('init', function () {
    add_rewrite_rule('^manifest\.json$', 'index.php?slow7_manifest=1', 'top');
});
add_filter('query_vars', function ($v) { $v[] = 'slow7_manifest'; return $v; });

// /manifest.json → /manifest.json/ 정규화 리다이렉트 방지
add_filter('redirect_canonical', function ($url) {
    return get_query_var('slow7_manifest') ? false : $url;
});

add_action('template_redirect', function () {
    if (!get_query_var('slow7_manifest')) return;

    $upload = wp_get_upload_dir();
    $base   = $upload['baseurl'];
    $icon512     = $base . '/2026/08/slow7-icon-512.png';
    $icon512mask = $base . '/2026/08/slow7-icon-512-maskable.png';
    $icon192     = get_site_icon_url(192) ?: $icon512;

    $manifest = [
        'name'             => get_bloginfo('name'),
        'short_name'       => '슬로우7',
        'description'      => get_bloginfo('description'),
        'start_url'        => home_url('/?utm_source=pwa'),
        'scope'            => '/',
        'display'          => 'standalone',
        'orientation'      => 'portrait',
        'background_color' => '#faf7f0',
        'theme_color'      => '#e8743b',
        'lang'             => 'ko',
        'icons'            => [
            ['src' => $icon192,     'sizes' => '192x192', 'type' => 'image/png'],
            ['src' => $icon512,     'sizes' => '512x512', 'type' => 'image/png'],
            ['src' => $icon512mask, 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'maskable'],
        ],
        // 홈 화면 아이콘 길게 눌렀을 때 나오는 바로가기
        'shortcuts' => [
            [
                'name' => '기록장',
                'url'  => home_url('/tracker/'),
                'icons' => [['src' => $icon192, 'sizes' => '192x192']],
            ],
        ],
    ];

    header('Content-Type: application/manifest+json; charset=utf-8');
    header('Cache-Control: max-age=3600');
    echo wp_json_encode($manifest, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
});

/* ------------------------------------------------------------------
   head 태그
   ------------------------------------------------------------------ */

add_action('wp_head', function () { ?>
<link rel="manifest" href="<?php echo esc_url(home_url('/manifest.json')); ?>" />
<meta name="theme-color" content="#e8743b" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="슬로우7" />
<?php }, 5);

/* ------------------------------------------------------------------
   설치 유도 UI
   ------------------------------------------------------------------ */

add_action('wp_footer', function () { ?>
<div class="s7i" id="s7i" hidden>
  <button type="button" class="s7i__close" id="s7iClose" aria-label="닫기">×</button>
  <div class="s7i__body">
    <strong class="s7i__title" id="s7iTitle">홈 화면에 추가하면 편해</strong>
    <p class="s7i__desc" id="s7iDesc"></p>
  </div>
  <button type="button" class="s7i__btn" id="s7iBtn" hidden>설치하기</button>
</div>
<script>
(function () {
  var SEEN = 'slow7.install.asked';
  var box = document.getElementById('s7i');
  if (!box || localStorage.getItem(SEEN)) return;

  // 이미 설치된 상태(standalone)면 안내하지 않는다
  var standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  if (standalone) return;

  var ua = navigator.userAgent;
  var isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
  var isSafari = /^((?!chrome|android|crios|fxios).)*safari/i.test(ua);
  var deferred = null;
  var ready = false;

  var title = document.getElementById('s7iTitle');
  var desc = document.getElementById('s7iDesc');
  var btn = document.getElementById('s7iBtn');

  function show() {
    if (!ready) return;
    box.hidden = false;
    box.classList.add('s7i--in');
  }

  // 본문을 절반 이상 읽은 뒤에만 노출
  var fired = false;
  function onScroll() {
    if (fired) return;
    var h = document.documentElement;
    if ((h.scrollTop + window.innerHeight) / h.scrollHeight < 0.5) return;
    fired = true;
    show();
    window.removeEventListener('scroll', onScroll);
  }
  window.addEventListener('scroll', onScroll, { passive: true });

  if (isIOS && isSafari) {
    // iOS 는 설치 API 가 없어 수동 안내만 가능하다. 알림을 받으려면 필수.
    title.textContent = '아이폰은 홈 화면에 추가해야 알림을 받을 수 있어';
    desc.innerHTML = '하단 <strong>공유 버튼(⬆️)</strong> → <strong>홈 화면에 추가</strong>를 누르면 끝. ' +
                     '앱처럼 열리고, 새 글 알림도 그때부터 받을 수 있어.';
    ready = true;
  } else {
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferred = e;
      title.textContent = '슬로우7을 앱처럼 쓰자';
      desc.textContent = '홈 화면에 추가하면 브라우저 없이 바로 열리고, 새 글 알림도 받을 수 있어.';
      btn.hidden = false;
      ready = true;
      if (fired) show();
    });
  }

  btn.addEventListener('click', function () {
    localStorage.setItem(SEEN, '1');
    box.hidden = true;
    if (deferred) { deferred.prompt(); deferred = null; }
  });
  document.getElementById('s7iClose').addEventListener('click', function () {
    localStorage.setItem(SEEN, '1');
    box.hidden = true;
  });
})();
</script>
<style>
.s7i{position:fixed;left:50%;bottom:18px;transform:translate(-50%,150%);z-index:9998;
  width:min(440px,calc(100vw - 24px));background:#fff;border:1px solid #e5ded0;border-radius:14px;
  box-shadow:0 12px 34px rgba(60,40,20,.22);padding:18px 42px 18px 20px;transition:transform .35s ease}
.s7i--in{transform:translate(-50%,0)}
.s7i__close{position:absolute;top:8px;right:10px;background:none;border:0;font-size:1.4rem;line-height:1;color:#b0a08c;cursor:pointer}
.s7i__title{display:block;font-size:.98rem;color:#3a2d1a;margin-bottom:6px}
.s7i__desc{margin:0;font-size:.86rem;line-height:1.55;color:#6b5340}
.s7i__btn{margin-top:14px;background:#e8743b;color:#fff;border:0;border-radius:999px;padding:10px 20px;font-weight:700;font-size:.88rem;cursor:pointer}
.s7i__btn:hover{background:#d4602a}
</style>
<?php });
