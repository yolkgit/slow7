<?php
/**
 * Slow7 — Yoast SEO 메타를 REST API로 쓰기 가능하게 노출.
 *
 * 설치: 이 파일을 워드프레스의 wp-content/mu-plugins/ 에 두면 자동 활성화됨.
 * (mu-plugins = must-use plugins, 별도 활성화 불필요)
 *
 * 이걸 넣으면 자동 발행 스크립트가 글의 Yoast 메타설명/제목을
 * REST API의 meta 필드로 직접 설정할 수 있다.
 */

if (!defined('ABSPATH')) {
    exit; // 직접 접근 차단
}

add_action('init', function () {
    $fields = [
        '_yoast_wpseo_metadesc',  // Yoast 메타 설명
        '_yoast_wpseo_title',     // Yoast SEO 제목
        '_yoast_wpseo_focuskw',   // 포커스 키워드
    ];
    foreach ($fields as $key) {
        register_post_meta('post', $key, [
            'show_in_rest'  => true,
            'single'        => true,
            'type'          => 'string',
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);
    }
});
