"""슬로우조깅 토픽 풀.

각 토픽은 시간대(slot)에 어울리는 카테고리를 가짐.
- morning  : 동기부여 / 출발 / 마인드
- noon     : 자세·호흡·페이스 같은 실전 팁
- evening  : 효과·과학·연구·회복 같은 깊이있는 정보
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    key: str           # 중복 추적용 고유 키
    slot: str          # morning / noon / evening
    title: str         # 간단 주제
    angle: str         # 어떤 각도로 풀지
    hashtags: tuple[str, ...]
    level: str = ""    # 초급/중급/고급. 비우면 slot·종류로 자동 추론


# 난이도 카테고리 (워드프레스 카테고리로 사용)
LEVELS = ("초급", "중급", "고급")


def topic_level(t: "Topic") -> str:
    """토픽 난이도. 명시값 우선, 없으면 종류·slot으로 추론."""
    if t.level:
        return t.level
    if t.key.startswith("c_"):   # 비교형 = 입문자가 많이 검색
        return "초급"
    if t.key.startswith("p_"):   # 루틴/플랜 = 어느 정도 시작한 사람
        return "중급"
    return {"morning": "초급", "noon": "중급", "evening": "고급"}.get(t.slot, "중급")


# 핵심 메시지가 겹치기 쉬운 주제군 — 같은 군이 연달아 안 나오게 회피용
_CLUSTERS = {
    "지방연소": ["fat", "mitochondria", "zone2", "science_fat", "insulin", "fasted", "post_meal"],
    "시작동기": ["start", "3min", "streak", "mindset", "buddy", "age_proof"],
    "자세폼": ["forefoot", "stride", "posture", "arm", "cadence"],
    "호흡": ["breath", "talk_test", "no_breath"],
    "회복": ["recovery", "sleep", "cooldown"],
    "건강효과": ["cortisol", "bdnf", "blood_pressure", "longevity", "mental", "age_research", "vo2max"],
    "장비": ["shoes", "water"],
    "코스환경": ["hill", "route", "rainy", "warmup"],
    "비교": ["c_"],
    "플랜": ["p_"],
}


# 키는 달라도 사실상 같은 글이 되는 토픽 묶음.
# 하나라도 블로그로 나갔으면 나머지도 쓴 것으로 본다.
_SAME_TOPIC = [
    {"m_post_meal", "c_fasted_vs_fed", "m_fat_burn"},
    {"m_no_breath", "n_talk_test"},
    {"n_heart_rate", "e_zone2"},
    {"m_rainy_day", "s1_09"},
    {"p_4week_beginner", "s1_01"},
]


def covered_keys(posted: set[str]) -> set[str]:
    """이미 쓴 토픽 + 그와 사실상 같은 토픽."""
    out = set(posted)
    for group in _SAME_TOPIC:
        if group & posted:
            out |= group
    return out


def topic_cluster(topic_key: str) -> str:
    """토픽이 속한 주제군. 내용 중복 회피에 사용."""
    for name, kws in _CLUSTERS.items():
        if any(k in topic_key for k in kws):
            return name
    return topic_key  # 못 찾으면 자기 자신 (고유 취급)


def keys_in_cluster(cluster: str) -> list[str]:
    """특정 주제군에 속하는 모든 토픽 키. SNS 관련 글 매칭용."""
    return [t.key for t in all_topics() if topic_cluster(t.key) == cluster]


_BASE_TAGS = ("#슬로우7", "#슬로우조깅", "#슬로우조깅챌린지", "#7분페이스")


MORNING: list[Topic] = [
    Topic("m_start_today", "morning", "오늘도 7분 페이스로 출발", "비 오는 날에도 30분이면 충분하다는 동기부여", _BASE_TAGS + ("#아침러닝",)),
    Topic("m_no_breath", "morning", "숨 안 차는 게 정답", "옆 사람과 대화 가능한 강도가 핵심", _BASE_TAGS + ("#유산소",)),
    Topic("m_fat_burn", "morning", "공복 슬로우조깅", "지방 연소 효율 극대화 메커니즘", _BASE_TAGS + ("#다이어트",)),
    Topic("m_3min_start", "morning", "3분만 뛰어도 OK", "시작이 반, 작은 성공이 큰 습관 만든다", _BASE_TAGS + ("#운동습관",)),
    Topic("m_age_proof", "morning", "60대도 가능한 운동", "남녀노소 모두에게 안전한 강도", _BASE_TAGS + ("#건강관리",)),
    Topic("m_rainy_day", "morning", "실내에서도 슬로우조깅", "제자리 슬로우조깅 자세와 효과", _BASE_TAGS + ("#홈트",)),
    Topic("m_post_meal", "morning", "공복vs식후 비교", "각각의 장단점과 추천 시점", _BASE_TAGS + ("#러닝팁",)),
    Topic("m_mindset", "morning", "느리게 가는 게 빠른 거", "속도 욕심 버리는 마인드 셋업", _BASE_TAGS + ("#마인드셋",)),
    Topic("m_buddy", "morning", "친구와 함께 하면 더 좋다", "대화하며 뛰는 사회적 효과", _BASE_TAGS + ("#러닝크루",)),
    Topic("m_streak", "morning", "21일의 법칙", "꾸준함이 만드는 변화 타임라인", _BASE_TAGS + ("#운동챌린지",)),
    Topic("m_heavy_start", "morning", "체중이 많이 나가도 시작하는 법", "관절 부담 줄이는 걷기·조깅 섞기와 첫 2주 기준", _BASE_TAGS + ("#체중감량",), level="초급"),
    Topic("m_restart", "morning", "쉬었다가 다시 시작할 때", "2주·한 달·석 달 쉰 뒤 어디서부터 다시 할지", _BASE_TAGS + ("#운동재개",), level="초급"),
    Topic("m_office_worker", "morning", "바쁜 직장인의 슬로우조깅", "출근 전·점심·퇴근 후 중 현실적인 시간대 고르기", _BASE_TAGS + ("#직장인운동",), level="초급"),
    Topic("m_slump", "morning", "운동 권태기 넘기기", "한두 달 지나 재미가 떨어질 때 쓰는 방법", _BASE_TAGS + ("#운동권태기",), level="초급"),
]

NOON: list[Topic] = [
    Topic("n_forefoot", "noon", "앞꿈치 착지", "왜 발 앞쪽으로 디뎌야 무릎이 안 아픈가", _BASE_TAGS + ("#러닝자세",)),
    Topic("n_stride", "noon", "보폭은 짧게", "리듬과 케이던스로 효율 올리기", _BASE_TAGS + ("#러닝폼",)),
    Topic("n_cadence_180", "noon", "180 케이던스", "분당 180걸음이 황금 비율인 이유", _BASE_TAGS + ("#러닝팁",)),
    Topic("n_breath_232", "noon", "호흡 2-3-2 리듬", "들숨 2번 날숨 3번, 안정적 호흡법", _BASE_TAGS + ("#호흡법",)),
    Topic("n_posture", "noon", "상체 자세", "골반 위 상체 똑바로, 시선은 10m 앞", _BASE_TAGS + ("#러닝자세",)),
    Topic("n_arm_swing", "noon", "팔치기 90도", "어깨 힘 빼고 진자운동처럼", _BASE_TAGS + ("#러닝팁",)),
    Topic("n_warmup", "noon", "5분 워밍업 루틴", "발목·고관절 동적스트레칭 시퀀스", _BASE_TAGS + ("#스트레칭",)),
    Topic("n_cooldown", "noon", "쿨다운 3분", "끝나고 천천히 걷기 + 폼롤러", _BASE_TAGS + ("#회복",)),
    Topic("n_water", "noon", "수분 섭취 전략", "운동 전 200ml, 30분 안에 다시", _BASE_TAGS + ("#영양",)),
    Topic("n_shoes", "noon", "신발 선택 기준", "쿠션·드롭·무게, 슬로우조깅에 맞는 스펙", _BASE_TAGS + ("#러닝화",)),
    Topic("n_heart_rate", "noon", "최대심박의 60-70%", "Zone 2 트레이닝이 곧 슬로우조깅", _BASE_TAGS + ("#심박수",)),
    Topic("n_talk_test", "noon", "토크 테스트", "옆 사람과 대화 되면 적정 강도", _BASE_TAGS + ("#운동강도",)),
    Topic("n_hill", "noon", "오르막 대처법", "보폭 더 줄이고 케이던스 유지", _BASE_TAGS + ("#러닝팁",)),
    Topic("n_route", "noon", "코스 짜는 법", "5-3-2 구간 나누기 (워밍업-본운동-쿨다운)", _BASE_TAGS + ("#러닝루트",)),
    Topic("n_shin_splints", "noon", "정강이가 아플 때", "신스플린트 원인과 쉬어야 할 때의 기준", _BASE_TAGS + ("#정강이통증",), level="중급"),
    Topic("n_plantar", "noon", "발바닥 통증과 족저근막", "발뒤꿈치 통증이 있을 때 조정할 것과 병원 갈 때", _BASE_TAGS + ("#족저근막염",), level="중급"),
    Topic("n_night_safety", "noon", "밤에 뛸 때 안전", "조명·반사 소재·코스 선택", _BASE_TAGS + ("#야간러닝",), level="초급"),
    Topic("n_summer_heat", "noon", "여름 더위 속 슬로우조깅", "온열질환 신호와 시간대·수분 조절", _BASE_TAGS + ("#여름운동",), level="중급"),
    Topic("n_winter_layers", "noon", "겨울 옷 겹쳐 입기", "기온별 레이어링과 손·귀 보온", _BASE_TAGS + ("#겨울러닝",), level="초급"),
    Topic("n_fine_dust", "noon", "미세먼지 많은 날", "실외 운동을 쉴 기준과 실내 대안", _BASE_TAGS + ("#미세먼지",), level="초급"),
    Topic("n_tracking", "noon", "앱과 워치로 기록하기", "페이스·심박·시간 중 무엇을 볼지", _BASE_TAGS + ("#러닝기록",), level="초급"),
    Topic("n_strength", "noon", "종아리·엉덩이 보조 근력운동", "주 2회 10분, 부상을 줄이는 기본 동작", _BASE_TAGS + ("#근력운동",), level="중급"),
    Topic("n_clothes_socks", "noon", "옷과 양말 고르기", "쓸림·물집을 막는 소재와 핏", _BASE_TAGS + ("#러닝복",), level="초급"),
]

EVENING: list[Topic] = [
    Topic("e_science_fat", "evening", "지방산 산화 메커니즘", "저강도일수록 지방이 주연료가 되는 이유", _BASE_TAGS + ("#운동과학",)),
    Topic("e_mitochondria", "evening", "미토콘드리아 증식", "Zone 2가 미토 밀도를 늘려 기초대사 끌어올린다", _BASE_TAGS + ("#대사",)),
    Topic("e_vo2max", "evening", "VO2max 향상", "느린 페이스가 오히려 최대산소섭취량을 늘린다", _BASE_TAGS + ("#유산소",)),
    Topic("e_recovery_sleep", "evening", "회복과 수면", "저강도 유산소가 깊은 잠을 만드는 메커니즘", _BASE_TAGS + ("#수면",)),
    Topic("e_cortisol", "evening", "코티솔 감소", "스트레스 호르몬을 낮추는 운동 강도", _BASE_TAGS + ("#스트레스",)),
    Topic("e_bdnf", "evening", "BDNF 분비", "뇌유래신경영양인자, 머리가 좋아지는 운동", _BASE_TAGS + ("#두뇌건강",)),
    Topic("e_blood_pressure", "evening", "혈압 관리", "꾸준한 슬로우조깅이 수축기 혈압을 낮춘다", _BASE_TAGS + ("#건강",)),
    Topic("e_insulin", "evening", "인슐린 감수성", "혈당 스파이크 막는 저녁 슬로우조깅", _BASE_TAGS + ("#혈당관리",)),
    Topic("e_longevity", "evening", "장수와 운동량", "주 150분 저강도가 사망률을 가장 크게 낮춘다", _BASE_TAGS + ("#장수",)),
    Topic("e_zone2", "evening", "Zone 2 트레이닝", "엘리트 선수의 80%가 저강도인 이유", _BASE_TAGS + ("#존2",)),
    Topic("e_recovery_meal", "evening", "운동 후 식사", "탄수:단백질 3:1 골든타임 30분", _BASE_TAGS + ("#영양",)),
    Topic("e_injury_prevention", "evening", "부상 예방", "느린 페이스가 무릎·아킬레스에 주는 안전마진", _BASE_TAGS + ("#부상예방",)),
    Topic("e_age_research", "evening", "노화 지연 연구", "텔로미어와 유산소 운동의 상관관계", _BASE_TAGS + ("#노화방지",)),
    Topic("e_mental_health", "evening", "우울감 감소", "12주 슬로우조깅으로 항우울제만큼의 효과", _BASE_TAGS + ("#정신건강",)),
    Topic("e_knee_arthritis", "evening", "무릎 관절염이 있어도 될까", "연구로 본 달리기와 무릎 관절, 조심할 사람", _BASE_TAGS + ("#무릎관절",), level="고급"),
    Topic("e_bone_density", "evening", "뼈 건강과 체중부하 운동", "골밀도에 걷기·조깅이 주는 자극", _BASE_TAGS + ("#골밀도",), level="고급"),
    Topic("e_cholesterol", "evening", "콜레스테롤·중성지방", "유산소 운동이 혈중 지질에 주는 변화", _BASE_TAGS + ("#콜레스테롤",), level="고급"),
    Topic("e_menopause", "evening", "갱년기와 유산소 운동", "갱년기 증상·체중·수면에 대한 근거", _BASE_TAGS + ("#갱년기",), level="고급"),
    Topic("e_immune", "evening", "적당한 운동과 면역", "중강도 운동과 감기, 너무 많이 하면 생기는 일", _BASE_TAGS + ("#면역력",), level="고급"),
    Topic("e_gut", "evening", "장 건강과 변비", "가벼운 유산소가 장운동에 주는 영향", _BASE_TAGS + ("#장건강",), level="고급"),
    Topic("e_resting_hr", "evening", "안정시 심박수 변화 읽기", "몇 주 뒤 심박이 내려가는 이유와 재는 법", _BASE_TAGS + ("#안정시심박",), level="고급"),
    Topic("e_calorie_math", "evening", "칼로리 소모 현실 계산", "30분에 얼마나 쓰는지, 먹는 것과의 관계", _BASE_TAGS + ("#칼로리",), level="중급"),
    Topic("e_caffeine", "evening", "운동 전 커피", "카페인이 지구력·심박에 주는 영향과 주의점", _BASE_TAGS + ("#카페인",), level="중급"),
    Topic("e_alcohol", "evening", "술 마신 다음 날 운동", "탈수·심박 측면에서 쉬어야 할 때", _BASE_TAGS + ("#음주",), level="중급"),
]


# 비교형 토픽 — 검색량 크고 체류시간 높음. 블로그 전용(slot=evening 색감).
# blog_writer가 'vs' 또는 '비교' 감지 시 자동으로 비교표를 넣는다.
COMPARISON: list[Topic] = [
    Topic("c_vs_walking", "evening", "슬로우조깅 vs 걷기", "같은 시간 운동 시 칼로리·지방연소·관절부담 비교, 누구에게 뭐가 맞나", _BASE_TAGS + ("#걷기", "#유산소비교")),
    Topic("c_vs_running", "evening", "슬로우조깅 vs 일반 달리기", "강도·부상위험·지속가능성·다이어트 효과 비교", _BASE_TAGS + ("#달리기", "#러닝비교")),
    Topic("c_fasted_vs_fed", "evening", "공복 유산소 vs 식후 유산소", "각각의 지방연소 메커니즘과 추천 대상 비교", _BASE_TAGS + ("#공복유산소", "#다이어트")),
    Topic("c_treadmill_vs_outdoor", "evening", "러닝머신 vs 야외 슬로우조깅", "에너지 소모·재미·관절부담·날씨 영향 비교", _BASE_TAGS + ("#러닝머신", "#야외운동")),
    Topic("c_morning_vs_evening", "evening", "아침 운동 vs 저녁 운동", "시간대별 지방연소·수면·코티솔 차이와 추천", _BASE_TAGS + ("#아침운동", "#저녁운동")),
    Topic("c_vs_cycling", "evening", "슬로우조깅 vs 자전거", "체중부하·칼로리·무릎부담·전신운동 효과 비교", _BASE_TAGS + ("#자전거", "#유산소비교")),
    Topic("c_zone2_vs_hiit", "evening", "존2 vs 고강도(HIIT)", "지방연소·심폐·회복·초보 적합성 비교", _BASE_TAGS + ("#존2", "#HIIT")),
    Topic("c_vs_swimming", "evening", "슬로우조깅 vs 수영", "관절부담·전신·접근성·다이어트 비교", _BASE_TAGS + ("#수영", "#유산소비교")),
    Topic("c_vs_stairs", "evening", "슬로우조깅 vs 계단 오르기", "심폐·무릎 부담·접근성 비교", _BASE_TAGS + ("#계단운동", "#유산소비교")),
    Topic("c_vs_jump_rope", "evening", "슬로우조깅 vs 줄넘기", "강도·충격·칼로리 비교", _BASE_TAGS + ("#줄넘기", "#유산소비교")),
    Topic("c_vs_hiking", "evening", "슬로우조깅 vs 등산", "근력·심폐·부상 위험 비교", _BASE_TAGS + ("#등산", "#유산소비교")),
]

# 루틴/플랜형 — 표로 주차별 계획 제시
PLAN: list[Topic] = [
    Topic("p_4week_beginner", "evening", "초보 4주 슬로우조깅 플랜", "1~4주차 시간·빈도·강도를 주차별 표로", _BASE_TAGS + ("#운동계획", "#초보러닝")),
    Topic("p_diet_8week", "evening", "8주 다이어트 슬로우조깅 플랜", "체중감량 목표 주차별 루틴 표", _BASE_TAGS + ("#다이어트계획", "#체중감량")),
    Topic("p_weekly_routine", "evening", "주간 슬로우조깅 루틴 짜기", "요일별 운동·휴식 배분 표", _BASE_TAGS + ("#주간루틴", "#운동습관")),
    Topic("p_5k_first", "evening", "처음 5km 완주 플랜", "걷기 섞어 6주 안에 5km를 쉬지 않고 가는 표", _BASE_TAGS + ("#5km", "#초보러닝")),
    Topic("p_senior_8week", "evening", "60대 이상 8주 플랜", "주 3회, 시간보다 회복을 우선하는 주차별 표", _BASE_TAGS + ("#시니어운동", "#운동계획")),
    Topic("p_busy_week", "evening", "바쁜 주 유지 플랜", "주 2회만 할 수 있을 때 효과를 지키는 배분", _BASE_TAGS + ("#운동습관", "#주간루틴")),
]


_ALL = {"morning": MORNING, "noon": NOON, "evening": EVENING}


def pick(
    slot: str,
    exclude_keys: set[str] | None = None,
    scores: dict[str, float] | None = None,
) -> Topic:
    """슬롯에 맞는 토픽 중 최근에 안 쓴 것 하나를 뽑는다.

    scores가 주어지면 (토픽키 → 평균 성과점수) 성과 좋은 토픽을
    더 자주 뽑도록 가중 랜덤. 성과 데이터 없는 토픽도 기본 가중치로 탐색 유지.
    """
    exclude_keys = exclude_keys or set()
    pool = _ALL[slot]
    candidates = [t for t in pool if t.key not in exclude_keys]
    if not candidates:
        candidates = pool

    if not scores:
        return random.choice(candidates)

    # 가중 랜덤: 성과점수 기반 + 미검증 토픽 탐색 보너스
    avg = (sum(scores.values()) / len(scores)) if scores else 1.0
    base = max(avg, 1.0)
    weights = []
    for t in candidates:
        if t.key in scores:
            # 성과 점수 + 1 (0점 방지). 잘된 토픽일수록 큼
            w = scores[t.key] + 1.0
        else:
            # 아직 성과 데이터 없는 토픽 → 평균 수준으로 탐색 기회 부여
            w = base
        weights.append(w)
    return random.choices(candidates, weights=weights, k=1)[0]


def all_topics() -> list[Topic]:
    return MORNING + NOON + EVENING + COMPARISON + PLAN + SERIES


def sns_topics() -> list[Topic]:
    """SNS 게시용 토픽 풀 — 연재(SERIES)는 제외한다.

    연재는 블로그에서 1편부터 순서대로 나가는 콘텐츠다. 이걸 SNS 풀에 섞으면
      - 아직 발행되지 않은 편이 먼저 노출된다(실제로 5편까지 나갔을 때
        마지막 12편이 SNS에 먼저 게시됐다)
      - 편끼리 주제 축이 겹쳐("2주차 자세", "3주차 빈도") 비슷한 글이
        반복되는 것처럼 보인다
    연재 홍보가 필요하면 발행 시점에 별도로 다루는 게 맞다.
    """
    return MORNING + NOON + EVENING + COMPARISON + PLAN


# ======================================================================
# 연재 시리즈
# ----------------------------------------------------------------------
# 개별 토픽은 무작위로 뽑히니 독자가 "다음 글"을 기다릴 이유가 없다.
# 시리즈는 순서가 정해져 있어 "다음 편"을 기다리게 만드는 게 목적이다.
# 월·수·금 발행이므로 12편이면 정확히 4주 분량이다.
# ======================================================================

SERIES_KEY = "s1"
SERIES_TITLE = "슬로우조깅 4주 완성"

SERIES: list[Topic] = [
    Topic("s1_01", "morning", "[1주차 ①] 슬로우조깅이 뭔지부터",
          "왜 느리게 뛰는 게 더 효과적인지 원리부터. 첫 주 목표는 '완주'가 아니라 '나가기'",
          _BASE_TAGS + ("#슬로우조깅4주", "#1주차"), level="초급"),
    Topic("s1_02", "morning", "[1주차 ②] 첫 달리기 20분 해보기",
          "니코니코 페이스 잡는 법. 숨차면 이미 빠른 거다. 20분을 걷기 섞어 채우는 법",
          _BASE_TAGS + ("#슬로우조깅4주", "#1주차"), level="초급"),
    Topic("s1_03", "morning", "[1주차 ③] 첫 주 마무리 점검",
          "3회 다 했는지 체크. 종아리·무릎 통증 유무로 강도 재조정하는 기준",
          _BASE_TAGS + ("#슬로우조깅4주", "#1주차"), level="초급"),
    Topic("s1_04", "noon", "[2주차 ①] 30분으로 늘리기",
          "20분에서 30분으로 넘어가는 안전한 증량폭. 10% 규칙 적용법",
          _BASE_TAGS + ("#슬로우조깅4주", "#2주차"), level="초급"),
    Topic("s1_05", "noon", "[2주차 ②] 착지와 자세 교정",
          "포어풋 착지·보폭·상체 각도. 2주차에 자세를 잡아야 부상이 안 온다",
          _BASE_TAGS + ("#슬로우조깅4주", "#2주차"), level="중급"),
    Topic("s1_06", "noon", "[2주차 ③] 지루함 넘기기",
          "느린 페이스가 심심할 때 쓰는 방법들. 코스 바꾸기·팟캐스트·구간 나누기",
          _BASE_TAGS + ("#슬로우조깅4주", "#2주차"), level="초급"),
    Topic("s1_07", "noon", "[3주차 ①] 주 4회로 늘려도 될까",
          "빈도를 늘릴지 시간을 늘릴지 판단 기준. 회복이 안 되면 늘리지 마라",
          _BASE_TAGS + ("#슬로우조깅4주", "#3주차"), level="중급"),
    Topic("s1_08", "noon", "[3주차 ②] 체중이 안 빠질 때",
          "3주차 정체기의 실제 원인. 먹는 양·수면·근육량 증가 관점에서",
          _BASE_TAGS + ("#슬로우조깅4주", "#3주차"), level="중급"),
    Topic("s1_09", "evening", "[3주차 ③] 비 오는 날·추운 날",
          "날씨 때문에 끊기는 게 제일 흔한 실패 원인. 실내 대체 루틴",
          _BASE_TAGS + ("#슬로우조깅4주", "#3주차"), level="중급"),
    Topic("s1_10", "evening", "[4주차 ①] 40분 도전",
          "4주차 목표 시간. 지치지 않고 40분을 채우는 페이스 배분",
          _BASE_TAGS + ("#슬로우조깅4주", "#4주차"), level="중급"),
    Topic("s1_11", "evening", "[4주차 ②] 4주 전후 변화 점검",
          "체중·안정시 심박·회복 속도·기분. 숫자로 확인하는 변화",
          _BASE_TAGS + ("#슬로우조깅4주", "#4주차"), level="중급"),
    Topic("s1_12", "evening", "[4주차 ③] 4주 후 어떻게 이어갈까",
          "프로그램 종료 후 유지 루틴. 다음 목표 설정법과 흔한 이탈 시점",
          _BASE_TAGS + ("#슬로우조깅4주", "#4주차"), level="중급"),
]


def next_series_topic(posted_keys: set[str]) -> Topic | None:
    """아직 안 나간 시리즈 편 중 가장 앞 편. 완결됐으면 None."""
    for t in SERIES:
        if t.key not in posted_keys:
            return t
    return None


def series_position(key: str) -> tuple[int, int] | None:
    """(현재 편 번호, 전체 편수). 시리즈 토픽이 아니면 None."""
    for i, t in enumerate(SERIES, start=1):
        if t.key == key:
            return i, len(SERIES)
    return None


def series_next_of(key: str) -> Topic | None:
    """이 편의 바로 다음 편(예고용). 마지막 편이면 None."""
    pos = series_position(key)
    if not pos or pos[0] >= len(SERIES):
        return None
    return SERIES[pos[0]]
