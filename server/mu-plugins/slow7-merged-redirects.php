<?php
/**
 * Slow7 — 합친 글의 옛 주소를 남긴 글로 301.
 *
 * 설치: wp-content/mu-plugins/ 에 두면 자동 활성화.
 *
 * ── 왜 필요한가 ───────────────────────────────────────────────
 * 토픽 재사용 버그(최근 30건만 피함)로 같은 주제의 글이 두 번 발행됐다.
 * 애드센스·구글이 "대량 생성 콘텐츠"로 보기 가장 쉬운 형태라, 쌍마다
 * 출처를 갖춘 예전 글만 남기고 나중 글은 비공개(draft)로 돌렸다.
 * 나중 글로 들어오는 링크(검색 결과, 다른 글의 관련 글 목록)는
 * 404 대신 남긴 글로 보낸다.
 *
 * 맵: 비공개로 돌린 글 ID => 남긴 글 ID  (scripts/site_cleanup.py 의 DUPLICATES 와 같아야 함)
 */

if (!defined('ABSPATH')) {
    exit;
}

const SLOW7_MERGED = [
    250 => 107, // 주간 루틴
    246 => 111, // 쿨다운 3분
    242 => 79,  // 공복 vs 식후
    238 => 62,  // 슬로우조깅 vs 걷기
    233 => 99,  // 신발
    225 => 30,  // BDNF
];

add_action('template_redirect', function () {
    if (!is_404()) {
        return;
    }
    $path = trim((string) parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), '/');
    $slug = sanitize_title(basename(urldecode($path)));
    if ($slug === '') {
        return;
    }
    global $wpdb;
    $id = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT ID FROM {$wpdb->posts} WHERE post_type = 'post' AND post_name = %s LIMIT 1",
        $slug
    ));
    // ?p=250 처럼 ID 로 들어온 옛 링크
    if (!$id && isset($_GET['p'])) {
        $id = (int) $_GET['p'];
    }
    if ($id && isset(SLOW7_MERGED[$id]) && get_post_status(SLOW7_MERGED[$id]) === 'publish') {
        wp_safe_redirect(get_permalink(SLOW7_MERGED[$id]), 301);
        exit;
    }
});
