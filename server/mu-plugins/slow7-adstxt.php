<?php
/**
 * Slow7 — ads.txt 서빙.
 *
 * 설치: wp-content/mu-plugins/ 에 두면 자동 활성화.
 *
 * slow7.soritok.com/ads.txt 가 404(HTML 반환) 상태였다. 애드센스는 이 파일로
 * "이 게시자가 이 사이트의 광고를 팔 권한이 있는지"를 확인한다.
 *
 * 워드프레스 루트에 파일로 두지 않고 라우트로 서빙하는 이유:
 * 이 프로젝트에서 루트에 올린 인증 파일이 재배포 중 유실된 전례가 있다
 * (네이버 소유확인). mu-plugin 은 wp-content 볼륨에 있어 함께 유지된다.
 */

if (!defined('ABSPATH')) {
    exit;
}

// 소리톡 루트 도메인과 동일한 게시자 ID
const SLOW7_ADS_TXT = "google.com, pub-6173583985814201, DIRECT, f08c47fec0942fa0\n";

add_action('init', function () {
    add_rewrite_rule('^ads\.txt$', 'index.php?slow7_ads=1', 'top');
});
add_filter('query_vars', function ($v) { $v[] = 'slow7_ads'; return $v; });

// /ads.txt → /ads.txt/ 정규화 리다이렉트 방지 (크롤러가 리다이렉트를 싫어한다)
add_filter('redirect_canonical', function ($url) {
    return get_query_var('slow7_ads') ? false : $url;
});

add_action('template_redirect', function () {
    if (!get_query_var('slow7_ads')) return;
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: max-age=3600');
    echo SLOW7_ADS_TXT;
    exit;
});
