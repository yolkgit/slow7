<?php
/**
 * Slow7 — 빈약한 아카이브 페이지를 색인에서 제외.
 *
 * 설치: wp-content/mu-plugins/ 에 두면 자동 활성화 (별도 활성화 불필요)
 *
 * ── 왜 필요한가 ───────────────────────────────────────────────
 * 사이트맵이 구글에 106개 URL 을 제출하는데, 실제 콘텐츠는 48개뿐이었다.
 *
 *   글          43
 *   고정페이지    5
 *   태그 아카이브 53   ← 이 중 48개가 글 1~2개짜리
 *   카테고리      4
 *   작성자        1   ← 1인 블로그라 블로그 목록과 내용이 같음
 *
 * 글 1개짜리 태그 페이지는 그 글의 발췌문 하나가 전부다. 원글에 이미
 * 있는 내용을 그대로 반복하는 껍데기 페이지가 48개 있는 셈이고,
 * 구글 입장에선 "사이트의 절반이 알맹이 없는 목록 페이지"로 보인다.
 * 애드센스가 두 번 다 지적한 '빈약한 콘텐츠'가 정확히 이 모양이다.
 *
 * ── 무엇을 하는가 ─────────────────────────────────────────────
 * 글이 THIN_MIN 개 미만인 태그, 작성자 아카이브, 날짜 아카이브에
 *   (1) noindex, follow 를 달고
 *   (2) Yoast 사이트맵에서도 뺀다.
 *
 * (1)만 하면 "색인해 달라"는 사이트맵과 "하지 말라"는 메타가 충돌해서
 * 서치콘솔이 '제출된 URL 이 noindex 로 표시됨' 오류로 잡는다. 반드시 같이 간다.
 *
 * follow 를 유지하므로 크롤러는 이 페이지들을 통해 글을 계속 발견한다.
 * 글이 쌓여 THIN_MIN 을 넘긴 태그는 자동으로 다시 색인 대상이 된다.
 */

if (!defined('ABSPATH')) {
    exit; // 직접 접근 차단
}

/** 이 개수 미만의 글을 가진 태그는 색인하지 않는다. */
const SLOW7_THIN_MIN = 3;

/**
 * 색인에서 뺄 태그인지 판단한다.
 * count 는 워드프레스가 term 테이블에 유지하는 발행글 수다.
 */
function slow7_is_thin_tag($term): bool
{
    return $term instanceof WP_Term
        && $term->taxonomy === 'post_tag'
        && (int) $term->count < SLOW7_THIN_MIN;
}

/**
 * 지금 보고 있는 화면이 색인 제외 대상인가.
 */
function slow7_is_thin_archive(): bool
{
    if (is_author() || is_date()) {
        return true;
    }
    if (is_tag()) {
        return slow7_is_thin_tag(get_queried_object());
    }
    return false;
}

/* ── (1) robots 메타 ──────────────────────────────────────────
 * Yoast 의 robots 배열을 직접 고친다. wp_head 로 따로 찍으면
 * Yoast 가 내보내는 태그와 둘이 되어 서로 모순된 신호가 나간다.
 */
add_filter('wpseo_robots_array', function ($robots) {
    if (slow7_is_thin_archive()) {
        $robots['index']  = 'noindex';
        $robots['follow'] = 'follow';
    }
    return $robots;
}, 10, 1);

/* Yoast 가 없거나 비활성일 때를 위한 보험.
 * Yoast 가 살아 있으면 위 필터가 처리하므로 여기선 아무것도 하지 않는다. */
add_action('wp_head', function () {
    if (!defined('WPSEO_VERSION') && slow7_is_thin_archive()) {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}, 1);

/* ── (2) 사이트맵에서 제외 ────────────────────────────────────
 * wpseo_sitemap_entry 는 URL 하나하나를 거른다. false 를 돌려주면 빠진다.
 * $type 은 'term' | 'post' | 'user'.
 */
add_filter('wpseo_sitemap_entry', function ($url, $type, $object) {
    if ($type === 'term' && slow7_is_thin_tag($object)) {
        return false;
    }
    if ($type === 'user') {
        return false; // 1인 블로그 — 작성자 아카이브는 블로그 목록과 중복
    }
    return $url;
}, 10, 3);

/* 주의: Yoast 의 wpseo_sitemap_exclude_author 는 이름과 달리 '제외할지' 를
 * 묻는 불리언이 아니라 사용자 배열을 받아 배열을 돌려주는 필터다.
 * __return_true 를 걸면 배열 자리에 true 가 들어가 foreach 에서 깨진다.
 * 위의 wpseo_sitemap_entry($type==='user') 만으로 내용이 비므로 쓰지 않는다. */
