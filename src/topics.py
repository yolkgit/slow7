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


def topic_cluster(topic_key: str) -> str:
    """토픽이 속한 주제군. 내용 중복 회피에 사용."""
    for name, kws in _CLUSTERS.items():
        if any(k in topic_key for k in kws):
            return name
    return topic_key  # 못 찾으면 자기 자신 (고유 취급)


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
]

# 루틴/플랜형 — 표로 주차별 계획 제시
PLAN: list[Topic] = [
    Topic("p_4week_beginner", "evening", "초보 4주 슬로우조깅 플랜", "1~4주차 시간·빈도·강도를 주차별 표로", _BASE_TAGS + ("#운동계획", "#초보러닝")),
    Topic("p_diet_8week", "evening", "8주 다이어트 슬로우조깅 플랜", "체중감량 목표 주차별 루틴 표", _BASE_TAGS + ("#다이어트계획", "#체중감량")),
    Topic("p_weekly_routine", "evening", "주간 슬로우조깅 루틴 짜기", "요일별 운동·휴식 배분 표", _BASE_TAGS + ("#주간루틴", "#운동습관")),
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
    return MORNING + NOON + EVENING + COMPARISON + PLAN
