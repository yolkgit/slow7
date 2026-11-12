"""오늘 날씨·미세먼지·계절 정보를 모아 SNS 정보 글의 재료로 만든다.

Open-Meteo(무료, API 키 없음)의 예보 API와 대기질 API를 쓴다.
    https://api.open-meteo.com/v1/forecast
    https://air-quality-api.open-meteo.com/v1/air-quality

글을 쓰는 모델이 숫자를 지어내지 않도록, 여기서 실제 값과
"오늘 짚을 만한 포인트"를 미리 계산해 사실 묶음(facts)으로 넘긴다.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")

# 위치 (기본 서울시청). .env 에서 바꿀 수 있다.
LAT = float(os.getenv("SNS_WEATHER_LAT", "37.5665"))
LON = float(os.getenv("SNS_WEATHER_LON", "126.9780"))
PLACE = os.getenv("SNS_WEATHER_PLACE", "서울")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# 시간대 (KST 시 단위, 끝 포함)
WINDOWS = {
    "출근길(6~9시)": (6, 9),
    "점심(11~14시)": (11, 14),
    "퇴근 후(18~21시)": (18, 21),
}

# 슬롯별로 글에서 다룰 시간대
SLOT_WINDOWS = {
    "morning": ["출근길(6~9시)", "점심(11~14시)", "퇴근 후(18~21시)"],
    "lunch": ["점심(11~14시)", "퇴근 후(18~21시)"],
}

# WMO 날씨 코드 → 한국어
_WMO = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
    45: "안개", 48: "짙은 안개",
    51: "약한 이슬비", 53: "이슬비", 55: "강한 이슬비", 56: "어는 이슬비", 57: "어는 이슬비",
    61: "약한 비", 63: "비", 65: "강한 비", 66: "어는 비", 67: "어는 비",
    71: "약한 눈", 73: "눈", 75: "많은 눈", 77: "싸락눈",
    80: "약한 소나기", 81: "소나기", 82: "강한 소나기",
    85: "약한 눈 소나기", 86: "강한 눈 소나기",
    95: "뇌우", 96: "우박 동반 뇌우", 99: "우박 동반 뇌우",
}

# 24절기 (해마다 하루 정도 차이 — 글에 "무렵" 정도로만 쓴다)
_SOLAR_TERMS = [
    (1, 5, "소한"), (1, 20, "대한"), (2, 4, "입춘"), (2, 19, "우수"),
    (3, 5, "경칩"), (3, 20, "춘분"), (4, 5, "청명"), (4, 20, "곡우"),
    (5, 5, "입하"), (5, 21, "소만"), (6, 6, "망종"), (6, 21, "하지"),
    (7, 7, "소서"), (7, 22, "대서"), (8, 7, "입추"), (8, 23, "처서"),
    (9, 7, "백로"), (9, 23, "추분"), (10, 8, "한로"), (10, 23, "상강"),
    (11, 7, "입동"), (11, 22, "소설"), (12, 7, "대설"), (12, 22, "동지"),
]


def wmo_text(code: int | None) -> str:
    if code is None:
        return "알 수 없음"
    return _WMO.get(int(code), "흐림")


def pm10_grade(v: float | None) -> str:
    """환경부 미세먼지(PM10) 예보 등급."""
    if v is None:
        return "정보 없음"
    if v <= 30:
        return "좋음"
    if v <= 80:
        return "보통"
    if v <= 150:
        return "나쁨"
    return "매우나쁨"


def pm25_grade(v: float | None) -> str:
    """환경부 초미세먼지(PM2.5) 예보 등급."""
    if v is None:
        return "정보 없음"
    if v <= 15:
        return "좋음"
    if v <= 35:
        return "보통"
    if v <= 75:
        return "나쁨"
    return "매우나쁨"


_GRADE_RANK = {"정보 없음": -1, "좋음": 0, "보통": 1, "나쁨": 2, "매우나쁨": 3}


def worse_grade(a: str, b: str) -> str:
    return a if _GRADE_RANK.get(a, -1) >= _GRADE_RANK.get(b, -1) else b


def uv_grade(v: float | None) -> str:
    if v is None:
        return "정보 없음"
    if v < 3:
        return "낮음"
    if v < 6:
        return "보통"
    if v < 8:
        return "높음"
    if v < 11:
        return "매우 높음"
    return "위험"


def solar_term_note(today: dt.date) -> str:
    """오늘 기준 가장 가까운 절기 이야기 (앞뒤 7일 안일 때만)."""
    best = None
    for m, d, name in _SOLAR_TERMS:
        for y in (today.year - 1, today.year, today.year + 1):
            day = dt.date(y, m, d)
            diff = (day - today).days
            if abs(diff) <= 7 and (best is None or abs(diff) < abs(best[0])):
                best = (diff, name)
    if not best:
        return ""
    diff, name = best
    if diff == 0:
        return f"오늘이 절기 '{name}' 무렵"
    if diff > 0:
        return f"{diff}일 뒤가 절기 '{name}'"
    return f"절기 '{name}'이 {-diff}일 지남"


def season_of(month: int) -> str:
    return {12: "겨울", 1: "한겨울", 2: "늦겨울", 3: "초봄", 4: "봄", 5: "늦봄",
            6: "초여름", 7: "한여름", 8: "늦여름", 9: "초가을", 10: "가을",
            11: "늦가을(초겨울)"}[month]


@dataclass
class WindowStat:
    name: str
    temp_min: float
    temp_max: float
    feels_min: float
    feels_max: float
    rain_prob: int
    rain_mm: float
    wind_max: float
    uv_max: float
    humidity_avg: float
    sky: str
    pm10: float | None = None
    pm25: float | None = None

    @property
    def dust_grade(self) -> str:
        return worse_grade(pm10_grade(self.pm10), pm25_grade(self.pm25))


@dataclass
class DayWeather:
    date: dt.date
    place: str
    temp_min: float
    temp_max: float
    rain_prob_max: int
    uv_max: float
    sunrise: str
    sunset: str
    windows: dict[str, WindowStat] = field(default_factory=dict)
    yesterday_max: float | None = None


def _get(url: str, params: dict) -> dict:
    last = None
    for _ in range(2):
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # 네트워크 일시 오류면 한 번 더
            last = e
    raise RuntimeError(f"날씨 API 실패: {url} ({last})")


def fetch(today: dt.date | None = None) -> DayWeather:
    """오늘 하루 날씨·대기질을 받아 정리한다."""
    fc = _get(FORECAST_URL, {
        "latitude": LAT, "longitude": LON, "timezone": "Asia/Seoul",
        "past_days": 1, "forecast_days": 1, "wind_speed_unit": "ms",
        "hourly": ",".join([
            "temperature_2m", "apparent_temperature", "precipitation_probability",
            "precipitation", "weather_code", "wind_speed_10m", "uv_index",
            "relative_humidity_2m",
        ]),
        "daily": ",".join([
            "temperature_2m_max", "temperature_2m_min", "sunrise", "sunset",
            "precipitation_probability_max", "uv_index_max",
        ]),
    })
    try:
        air = _get(AIR_URL, {
            "latitude": LAT, "longitude": LON, "timezone": "Asia/Seoul",
            "forecast_days": 1, "hourly": "pm10,pm2_5",
        })
    except RuntimeError as e:
        print(f"[weather] 대기질 못 받음 — 미세먼지 없이 진행: {e}")
        air = {}
    return parse(fc, air, today)


def _val(seq, i):
    try:
        v = seq[i]
    except (IndexError, TypeError):
        return None
    return v


def parse(fc: dict, air: dict, today: dt.date | None = None) -> DayWeather:
    """API 응답(JSON) → DayWeather. 테스트에서 가짜 응답으로 직접 부를 수 있게 분리."""
    today = today or dt.datetime.now(KST).date()
    iso = today.isoformat()
    daily = fc["daily"]
    days = daily["time"]
    di = days.index(iso) if iso in days else len(days) - 1
    yi = di - 1 if di >= 1 else None

    hourly = fc["hourly"]
    times = hourly["time"]
    a_hourly = (air or {}).get("hourly", {})
    a_index = {t: i for i, t in enumerate(a_hourly.get("time", []))}

    def hours_for(h0: int, h1: int) -> list[int]:
        out = []
        for i, t in enumerate(times):
            if not t.startswith(iso):
                continue
            hour = int(t[11:13])
            if h0 <= hour <= h1:
                out.append(i)
        return out

    def nums(key: str, idx: list[int]) -> list[float]:
        seq = hourly.get(key) or []
        return [v for v in (_val(seq, i) for i in idx) if v is not None]

    def air_nums(key: str, idx: list[int]) -> list[float]:
        seq = a_hourly.get(key) or []
        out = []
        for i in idx:
            j = a_index.get(times[i])
            v = _val(seq, j) if j is not None else None
            if v is not None:
                out.append(v)
        return out

    windows: dict[str, WindowStat] = {}
    for name, (h0, h1) in WINDOWS.items():
        idx = hours_for(h0, h1)
        temps = nums("temperature_2m", idx)
        if not temps:
            continue
        feels = nums("apparent_temperature", idx) or temps
        codes = [int(c) for c in nums("weather_code", idx)]
        # 그 시간대에서 가장 '궂은' 날씨 코드를 대표로 (비·눈이 한 시간이라도 있으면 알려야 함)
        sky = wmo_text(max(codes) if codes else None)
        pm10 = air_nums("pm10", idx)
        pm25 = air_nums("pm2_5", idx)
        hum = nums("relative_humidity_2m", idx)
        windows[name] = WindowStat(
            name=name,
            temp_min=round(min(temps), 1), temp_max=round(max(temps), 1),
            feels_min=round(min(feels), 1), feels_max=round(max(feels), 1),
            rain_prob=int(max(nums("precipitation_probability", idx) or [0])),
            rain_mm=round(sum(nums("precipitation", idx)), 1),
            wind_max=round(max(nums("wind_speed_10m", idx) or [0]), 1),
            uv_max=round(max(nums("uv_index", idx) or [0]), 1),
            humidity_avg=round(sum(hum) / len(hum)) if hum else 0,
            sky=sky,
            pm10=round(max(pm10)) if pm10 else None,
            pm25=round(max(pm25)) if pm25 else None,
        )

    return DayWeather(
        date=today,
        place=PLACE,
        temp_min=round(daily["temperature_2m_min"][di], 1),
        temp_max=round(daily["temperature_2m_max"][di], 1),
        rain_prob_max=int(daily.get("precipitation_probability_max", [0] * len(days))[di] or 0),
        uv_max=round(daily.get("uv_index_max", [0] * len(days))[di] or 0, 1),
        sunrise=(daily.get("sunrise") or [""] * len(days))[di][11:16],
        sunset=(daily.get("sunset") or [""] * len(days))[di][11:16],
        windows=windows,
        yesterday_max=round(daily["temperature_2m_max"][yi], 1) if yi is not None else None,
    )


# ---------- 오늘 짚을 만한 포인트 ----------

def check_points(w: DayWeather, slot: str) -> list[tuple[str, str]]:
    """(각도, 사실 문장) 목록. 글의 중심 각도를 고르는 재료.

    각도: 옷차림 / 비·눈 / 미세먼지 / 자외선 / 일교차 / 바람 / 건조 / 더위 / 어두움 / 운동시간
    """
    pts: list[tuple[str, str]] = []
    wins = [w.windows[n] for n in SLOT_WINDOWS[slot] if n in w.windows]
    first = wins[0] if wins else None

    if first:
        if first.feels_min <= -5:
            pts.append(("옷차림", f"{first.name} 체감 {first.feels_min}℃ — 한파 수준, 장갑·귀 덮개·목 보온 필요"))
        elif first.feels_min <= 5:
            pts.append(("옷차림", f"{first.name} 체감 {first.feels_min}℃ — 두꺼운 겉옷, 손·목 보온"))
        elif first.feels_min <= 10:
            pts.append(("옷차림", f"{first.name} 체감 {first.feels_min}℃ — 얇은 겹옷이 편한 기온"))
        if first.feels_max >= 31:
            pts.append(("더위", f"{first.name} 체감 {first.feels_max}℃ — 한낮 야외 활동은 짧게, 물 자주"))

    wet = [x for x in wins if x.rain_prob >= 50 or x.rain_mm >= 0.5]
    if wet:
        x = wet[0]
        kind = "눈" if "눈" in x.sky else "비"
        pts.append(("비·눈", f"{x.name} {x.sky}, 강수확률 {x.rain_prob}%" + (f", 약 {x.rain_mm}mm" if x.rain_mm else "") + f" — {kind} 대비"))
    elif w.rain_prob_max >= 40:
        pts.append(("비·눈", f"하루 중 강수확률 최고 {w.rain_prob_max}% — 작은 우산 챙길 만함"))

    dusty = [x for x in wins if _GRADE_RANK.get(x.dust_grade, -1) >= 2]
    clean = [x for x in wins if x.dust_grade == "좋음"]
    if dusty:
        x = dusty[0]
        pts.append(("미세먼지", f"{x.name} 미세먼지 {x.dust_grade} (PM10 {x.pm10}, PM2.5 {x.pm25}㎍/㎥) — 야외 운동은 줄이거나 실내로"))
    elif clean and len(clean) == len(wins):
        pts.append(("미세먼지", "오늘 미세먼지 좋음 — 환기·야외 활동하기 좋은 날"))

    if w.uv_max >= 6:
        pts.append(("자외선", f"자외선 지수 최고 {w.uv_max} ({uv_grade(w.uv_max)}) — 11~15시 햇빛 주의"))

    spread = w.temp_max - w.temp_min
    if spread >= 10:
        pts.append(("일교차", f"최저 {w.temp_min}℃ / 최고 {w.temp_max}℃, 일교차 {spread:.0f}℃ — 벗고 입기 쉬운 옷"))

    if w.yesterday_max is not None:
        diff = w.temp_max - w.yesterday_max
        if abs(diff) >= 5:
            word = "높음" if diff > 0 else "낮음"
            pts.append(("옷차림", f"어제보다 낮 최고기온이 {abs(diff):.0f}℃ {word}"))

    windy = [x for x in wins if x.wind_max >= 7]
    if windy:
        x = windy[0]
        pts.append(("바람", f"{x.name} 바람 최대 {x.wind_max}m/s — 체감온도가 더 내려감"))

    dry = [x for x in wins if x.humidity_avg and x.humidity_avg <= 35]
    if dry:
        pts.append(("건조", f"{dry[0].name} 습도 {dry[0].humidity_avg}% — 공기가 건조함, 수분·입술·피부 관리"))

    if slot == "morning" and w.sunrise and w.sunrise >= "07:00":
        pts.append(("어두움", f"해 뜨는 시각 {w.sunrise} — 이른 아침엔 아직 어두움, 밝은 색 옷"))
    if slot == "lunch" and w.sunset and w.sunset <= "18:00":
        pts.append(("어두움", f"해 지는 시각 {w.sunset} — 퇴근 후엔 이미 어두움"))

    # 오늘 바깥 활동하기 가장 나은 시간대
    def score(x: WindowStat) -> float:
        s = 0.0
        s += abs(((x.feels_min + x.feels_max) / 2) - 15) * 1.0
        s += x.rain_prob * 0.2
        s += _GRADE_RANK.get(x.dust_grade, 0) * 8
        s += max(0.0, x.wind_max - 4) * 2
        return s

    if len(wins) >= 2:
        best = min(wins, key=score)
        pts.append(("운동시간", f"오늘 걷기·가벼운 달리기엔 {best.name}이 가장 나음 (체감 {best.feels_min}~{best.feels_max}℃, {best.sky}, 미세먼지 {best.dust_grade})"))

    return pts


def facts_text(w: DayWeather, slot: str) -> str:
    """모델에게 넘길 사실 묶음 (숫자는 여기 있는 것만 쓰게 한다)."""
    wd = "월화수목금토일"[w.date.weekday()]
    lines = [
        f"날짜: {w.date.month}월 {w.date.day}일 ({wd}요일), 계절: {season_of(w.date.month)}",
        f"지역: {w.place}",
        f"오늘 최저 {w.temp_min}℃ / 최고 {w.temp_max}℃"
        + (f" (어제 최고 {w.yesterday_max}℃)" if w.yesterday_max is not None else ""),
        f"해 뜨는 시각 {w.sunrise}, 해 지는 시각 {w.sunset}",
        f"하루 강수확률 최고 {w.rain_prob_max}%, 자외선 최고 {w.uv_max} ({uv_grade(w.uv_max)})",
    ]
    term = solar_term_note(w.date)
    if term:
        lines.append(f"절기: {term}")
    for n in SLOT_WINDOWS[slot]:
        x = w.windows.get(n)
        if not x:
            continue
        dust = (f"미세먼지 {x.dust_grade} (PM10 {x.pm10}, PM2.5 {x.pm25})"
                if x.pm10 is not None else "미세먼지 정보 없음")
        lines.append(
            f"{n}: {x.sky}, 기온 {x.temp_min}~{x.temp_max}℃, 체감 {x.feels_min}~{x.feels_max}℃, "
            f"강수확률 {x.rain_prob}%, 바람 최대 {x.wind_max}m/s, 습도 {x.humidity_avg}%, {dust}"
        )
    return "\n".join(lines)
