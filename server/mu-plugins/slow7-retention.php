<?php
/**
 * Slow7 — 재방문 유도 장치.
 *
 * 설치: 이 파일을 워드프레스의 wp-content/mu-plugins/ 에 두면 자동 활성화됨.
 *
 * 블로그에 재방문 장치가 전혀 없었다(관련 글·다음 글·구독·시리즈 모두 없음).
 * 글을 다 읽으면 나갈 수밖에 없는 구조라, 아래 세 가지를 붙인다.
 *
 *  1) 다음 편 / 이전 편  — 같은 카테고리 안에서 이어 읽게 (세션 연장)
 *  2) 함께 읽으면 좋은 글 — 매번 다른 조합으로 노출 (재방문 시 새 글 발견)
 *  3) 기록장 CTA        — 습관 도구로 유도 (재방문의 실제 동력)
 *
 * 기록장([slow7_tracker])은 전부 브라우저 localStorage 에만 저장한다.
 * 서버로 아무것도 보내지 않으므로 개인정보 수집·동의 이슈가 없다.
 */

if (!defined('ABSPATH')) {
    exit; // 직접 접근 차단
}

/* ------------------------------------------------------------------
   1. 글 하단 재방문 블록
   ------------------------------------------------------------------ */

function slow7_retention_blocks($content)
{
    // 단일 글 본문에서만 (목록·RSS·REST 발췌 등에는 끼어들지 않게)
    if (!is_singular('post') || !in_the_loop() || !is_main_query()) {
        return $content;
    }

    $out = '';

    // --- 다음 편 / 이전 편 (같은 카테고리 우선) ---
    $prev = get_previous_post(true);
    $next = get_next_post(true);
    if (!$prev) $prev = get_previous_post(false);
    if (!$next) $next = get_next_post(false);

    if ($prev || $next) {
        $out .= '<nav class="s7r-nav" aria-label="이어서 읽기">';
        if ($prev) {
            $out .= '<a class="s7r-nav__item s7r-nav__item--prev" href="' . esc_url(get_permalink($prev)) . '">'
                . '<span class="s7r-nav__label">← 이전 편</span>'
                . '<span class="s7r-nav__title">' . esc_html(get_the_title($prev)) . '</span></a>';
        }
        if ($next) {
            $out .= '<a class="s7r-nav__item s7r-nav__item--next" href="' . esc_url(get_permalink($next)) . '">'
                . '<span class="s7r-nav__label">다음 편 →</span>'
                . '<span class="s7r-nav__title">' . esc_html(get_the_title($next)) . '</span></a>';
        }
        $out .= '</nav>';
    }

    // --- 함께 읽으면 좋은 글 (같은 카테고리에서 무작위 3개) ---
    $cats = wp_get_post_categories(get_the_ID());
    $related = get_posts([
        'posts_per_page'      => 3,
        'post__not_in'        => [get_the_ID()],
        'category__in'        => $cats ?: [],
        'orderby'             => 'rand', // 다시 왔을 때 다른 글이 보이게
        'ignore_sticky_posts' => true,
    ]);
    if (count($related) < 3) { // 같은 카테고리가 부족하면 전체에서 채운다
        $related = get_posts([
            'posts_per_page'      => 3,
            'post__not_in'        => [get_the_ID()],
            'orderby'             => 'rand',
            'ignore_sticky_posts' => true,
        ]);
    }

    if ($related) {
        $out .= '<section class="s7r-related"><h2 class="s7r-h">함께 읽으면 좋은 글</h2><ul class="s7r-related__list">';
        foreach ($related as $p) {
            $thumb = get_the_post_thumbnail_url($p, 'medium');
            $out .= '<li class="s7r-related__item"><a href="' . esc_url(get_permalink($p)) . '">';
            if ($thumb) {
                $out .= '<img class="s7r-related__thumb" src="' . esc_url($thumb) . '" alt="" loading="lazy" />';
            }
            $out .= '<span class="s7r-related__title">' . esc_html(get_the_title($p)) . '</span></a></li>';
        }
        $out .= '</ul></section>';
        wp_reset_postdata();
    }

    // --- 기록장 CTA ---
    $tracker = get_page_by_path('tracker');
    if ($tracker) {
        $out .= '<aside class="s7r-cta"><div class="s7r-cta__body">'
            . '<strong class="s7r-cta__title">오늘 달린 거, 기록해두자!</strong>'
            . '<p class="s7r-cta__desc">슬로우조깅은 꾸준함이 전부다. 연속 며칠째인지 눈으로 보이면 확실히 덜 빠진다. '
            . '기록은 네 브라우저에만 저장되니까 가입도, 로그인도 필요 없어.</p></div>'
            . '<a class="s7r-cta__btn" href="' . esc_url(get_permalink($tracker)) . '">기록장 열기</a></aside>';
    }

    return $content . $out;
}
add_filter('the_content', 'slow7_retention_blocks');

/* ------------------------------------------------------------------
   2. 기록장 숏코드 [slow7_tracker]
   ------------------------------------------------------------------ */

function slow7_tracker_shortcode()
{
    ob_start(); ?>
<div class="s7t" id="s7t">
  <div class="s7t-stats">
    <div class="s7t-stat"><span class="s7t-stat__num" id="s7tStreak">0</span><span class="s7t-stat__label">연속 일수</span></div>
    <div class="s7t-stat"><span class="s7t-stat__num" id="s7tWeek">0</span><span class="s7t-stat__label">이번 주 (분)</span></div>
    <div class="s7t-stat"><span class="s7t-stat__num" id="s7tTotal">0</span><span class="s7t-stat__label">전체 횟수</span></div>
  </div>

  <p class="s7t-msg" id="s7tMsg"></p>

  <form class="s7t-form" id="s7tForm">
    <label class="s7t-field"><span>날짜</span><input type="date" id="s7tDate" required /></label>
    <label class="s7t-field"><span>시간(분)</span><input type="number" id="s7tMin" min="1" max="600" placeholder="30" required /></label>
    <label class="s7t-field s7t-field--wide"><span>느낌 한 줄 (선택)</span><input type="text" id="s7tNote" maxlength="60" placeholder="숨 안 차고 딱 좋았음" /></label>
    <button type="submit" class="s7t-submit">기록 추가</button>
  </form>

  <ul class="s7t-list" id="s7tList"></ul>
  <p class="s7t-note">기록은 이 브라우저에만 저장돼. 서버로 전송되지 않으니 안심하고 써도 된다. (브라우저 데이터를 지우면 함께 사라져)</p>
</div>

<script>
(function () {
  var KEY = 'slow7.tracker.v1';
  var $ = function (id) { return document.getElementById(id); };
  var load = function () { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; } };
  var save = function (r) { localStorage.setItem(KEY, JSON.stringify(r)); };
  var ymd = function (d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  };

  // 연속 일수: 오늘(또는 어제)부터 하루씩 거슬러 올라가며 기록이 끊기는 지점까지
  function streak(rows) {
    var days = {};
    rows.forEach(function (r) { days[r.date] = true; });
    var d = new Date(), n = 0;
    if (!days[ymd(d)]) d.setDate(d.getDate() - 1); // 오늘 아직 안 뛰었어도 어제까지 인정
    while (days[ymd(d)]) { n++; d.setDate(d.getDate() - 1); }
    return n;
  }

  // 이번 주(월요일 시작) 누적 분
  function weekMinutes(rows) {
    var now = new Date();
    var day = (now.getDay() + 6) % 7; // 월=0
    var mon = new Date(now); mon.setDate(now.getDate() - day); mon.setHours(0, 0, 0, 0);
    return rows.reduce(function (sum, r) {
      var d = new Date(r.date + 'T00:00:00');
      return d >= mon ? sum + Number(r.min || 0) : sum;
    }, 0);
  }

  function message(s) {
    if (s === 0) return '오늘 한 번 뛰고 첫 칸을 채워보자. 시작이 제일 어렵다!';
    if (s === 1) return '1일차! 내일 이어가면 2일. 여기서부터가 진짜다.';
    if (s < 7) return s + '일 연속! 일주일까지 ' + (7 - s) + '일 남았어. 갈 수 있다.';
    if (s < 30) return s + '일 연속! 이제 습관 궤도에 올랐다. 무리하지 말고 계속.';
    return s + '일 연속!! 이 정도면 슬로우조깅이 생활이 됐다. 대단해!';
  }

  function render() {
    var rows = load().sort(function (a, b) { return b.date.localeCompare(a.date); });
    var s = streak(rows);
    $('s7tStreak').textContent = s;
    $('s7tWeek').textContent = weekMinutes(rows);
    $('s7tTotal').textContent = rows.length;
    $('s7tMsg').textContent = message(s);

    var list = $('s7tList');
    list.innerHTML = '';
    rows.slice(0, 10).forEach(function (r, i) {
      var li = document.createElement('li');
      li.className = 's7t-item';
      var main = document.createElement('span');
      main.className = 's7t-item__main';
      main.textContent = r.date + ' · ' + r.min + '분' + (r.note ? ' · ' + r.note : '');
      var del = document.createElement('button');
      del.type = 'button';
      del.className = 's7t-del';
      del.textContent = '삭제';
      del.addEventListener('click', function () {
        var all = load();
        var idx = all.findIndex(function (x) { return x.date === r.date && x.min === r.min && x.note === r.note; });
        if (idx > -1) { all.splice(idx, 1); save(all); render(); }
      });
      li.appendChild(main); li.appendChild(del);
      list.appendChild(li);
    });
  }

  var form = $('s7tForm');
  if (!form) return;
  $('s7tDate').value = ymd(new Date());
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var rows = load();
    rows.push({ date: $('s7tDate').value, min: Number($('s7tMin').value), note: $('s7tNote').value.trim() });
    save(rows);
    $('s7tMin').value = ''; $('s7tNote').value = '';
    render();
  });
  render();
})();
</script>
<?php
    return ob_get_clean();
}
add_shortcode('slow7_tracker', 'slow7_tracker_shortcode');

/* ------------------------------------------------------------------
   3. 스타일
   ------------------------------------------------------------------ */

function slow7_retention_styles()
{
    if (!is_singular()) return; ?>
<style>
.s7r-h{font-size:1.15rem;font-weight:800;margin:0 0 14px}
.s7r-nav{display:flex;gap:12px;flex-wrap:wrap;margin:40px 0 8px}
.s7r-nav__item{flex:1 1 220px;display:flex;flex-direction:column;gap:4px;padding:14px 16px;border:1px solid #e5ded0;border-radius:12px;background:#fbf8f2;text-decoration:none;transition:border-color .15s}
.s7r-nav__item:hover{border-color:#e8743b}
.s7r-nav__item--next{text-align:right}
.s7r-nav__label{font-size:.78rem;font-weight:700;color:#e8743b}
.s7r-nav__title{font-size:.95rem;font-weight:600;color:#3a2d1a;line-height:1.4}
.s7r-related{margin:36px 0}
.s7r-related__list{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.s7r-related__item a{display:flex;flex-direction:column;gap:8px;text-decoration:none;color:#3a2d1a}
.s7r-related__thumb{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:10px}
.s7r-related__title{font-size:.92rem;font-weight:600;line-height:1.45}
.s7r-related__item a:hover .s7r-related__title{color:#e8743b}
.s7r-cta{margin:36px 0;padding:20px;border-radius:14px;background:linear-gradient(135deg,#fff3e8,#ffe6d2);border:1px solid #f3d3b6;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.s7r-cta__body{flex:1 1 260px}
.s7r-cta__title{display:block;font-size:1.05rem;color:#8a4520;margin-bottom:6px}
.s7r-cta__desc{margin:0;font-size:.9rem;line-height:1.6;color:#6b5340}
.s7r-cta__btn{flex-shrink:0;background:#e8743b;color:#fff;font-weight:700;padding:12px 22px;border-radius:999px;text-decoration:none;white-space:nowrap}
.s7r-cta__btn:hover{background:#d4602a;color:#fff}
/* 기록장 */
.s7t{margin:8px 0 24px}
.s7t-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.s7t-stat{background:#fbf8f2;border:1px solid #e5ded0;border-radius:12px;padding:16px 8px;text-align:center}
.s7t-stat__num{display:block;font-size:1.9rem;font-weight:800;color:#e8743b;line-height:1.1}
.s7t-stat__label{font-size:.8rem;color:#7a6650}
.s7t-msg{margin:0 0 18px;padding:12px 16px;background:#fff3e8;border-left:4px solid #e8743b;border-radius:6px;font-weight:600;color:#8a4520}
.s7t-form{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;align-items:end;margin-bottom:20px}
.s7t-field{display:flex;flex-direction:column;gap:5px;font-size:.85rem;color:#6b5340}
.s7t-field--wide{grid-column:1/-1}
.s7t-field input{padding:10px 12px;border:1px solid #ddd3c2;border-radius:8px;font-size:.95rem;width:100%}
.s7t-submit{background:#e8743b;color:#fff;border:0;border-radius:8px;padding:12px 20px;font-weight:700;font-size:.95rem;cursor:pointer}
.s7t-submit:hover{background:#d4602a}
.s7t-list{list-style:none;padding:0;margin:0}
.s7t-item{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 4px;border-bottom:1px solid #eee6d8;font-size:.92rem}
.s7t-item__main{color:#3a2d1a}
.s7t-del{background:none;border:0;color:#b0a08c;font-size:.8rem;cursor:pointer;padding:4px 6px}
.s7t-del:hover{color:#e8743b}
.s7t-note{margin-top:16px;font-size:.8rem;color:#9a8b76}
@media(max-width:600px){
  .s7r-nav__item--next{text-align:left}
  .s7r-cta{flex-direction:column;align-items:stretch}
  .s7r-cta__btn{text-align:center}
}
</style>
<?php }
add_action('wp_head', 'slow7_retention_styles');
