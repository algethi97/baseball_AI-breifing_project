"""
기상청_단기예보 조회서비스 (초단기실황 API) 기반 KBO 전국 프로야구 구장 실시간 기상정보 모듈
"""

import os
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "storage" / "db" / "baseball_news.db"

# KBO 10개 구단 주요 홈구장 및 제2구장 (총 11개 구장) 메타데이터
STADIUMS = [
    {
        "id": "jamsil",
        "name": "서울 잠실야구장",
        "teams": ["LG 트윈스", "두산 베어스"],
        "team_short": "LG / 두산",
        "city": "서울 송파",
        "nx": 61,
        "ny": 126,
        "color": "#C30452",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "gocheok",
        "name": "서울 고척스카이돔",
        "teams": ["키움 히어로즈"],
        "team_short": "키움",
        "city": "서울 구로",
        "nx": 58,
        "ny": 125,
        "color": "#820024",
        "is_dome": True,
        "is_secondary": False,
    },
    {
        "id": "munhak",
        "name": "인천 SSG랜더스필드",
        "teams": ["SSG 랜더스"],
        "team_short": "SSG",
        "city": "인천 미추홀",
        "nx": 55,
        "ny": 124,
        "color": "#CE0E2D",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "suwon",
        "name": "수원 KT위즈파크",
        "teams": ["kt wiz"],
        "team_short": "KT",
        "city": "경기 수원",
        "nx": 60,
        "ny": 121,
        "color": "#000000",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "daejeon",
        "name": "대전 한화생명이글스파크",
        "teams": ["한화 이글스"],
        "team_short": "한화",
        "city": "대전 중구",
        "nx": 68,
        "ny": 100,
        "color": "#FF6600",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "daegu",
        "name": "대구 삼성라이온즈파크",
        "teams": ["삼성 라이온즈"],
        "team_short": "삼성",
        "city": "대구 수성",
        "nx": 90,
        "ny": 90,
        "color": "#074CA1",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "gwangju",
        "name": "광주-기아 챔피언스필드",
        "teams": ["KIA 타이거즈"],
        "team_short": "KIA",
        "city": "광주 북구",
        "nx": 59,
        "ny": 75,
        "color": "#EA0029",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "sajik",
        "name": "부산 사직야구장",
        "teams": ["롯데 자이언츠"],
        "team_short": "롯데",
        "city": "부산 동래",
        "nx": 98,
        "ny": 76,
        "color": "#002955",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "changwon",
        "name": "창원 NC파크",
        "teams": ["NC 다이노스"],
        "team_short": "NC",
        "city": "경남 창원",
        "nx": 89,
        "ny": 76,
        "color": "#315288",
        "is_dome": False,
        "is_secondary": False,
    },
    {
        "id": "pohang",
        "name": "포항야구장 (제2구장)",
        "teams": ["삼성 라이온즈"],
        "team_short": "삼성 (제2구장)",
        "city": "경북 포항",
        "nx": 102,
        "ny": 94,
        "color": "#074CA1",
        "is_dome": False,
        "is_secondary": True,
    },
    {
        "id": "ulsan",
        "name": "울산문수야구장 (제2구장)",
        "teams": ["롯데 자이언츠", "울산 웨일즈"],
        "team_short": "롯데 / 울산",
        "city": "울산 남구",
        "nx": 101,
        "ny": 84,
        "color": "linear-gradient(90deg, #002955 50%, #c70000 50%)",
        "is_dome": False,
        "is_secondary": True,
    },
]


def get_kma_base_datetime() -> tuple[str, str]:
    """
    기상청 초단기실황 API 발표시각 계산
    - 매시 정시 40분 이후 최신 자료 생성되므로, 45분 미만인 경우 이전 정시 데이터 사용
    """
    now = datetime.now()
    if now.minute < 45:
        target = now - timedelta(hours=1)
    else:
        target = now
    return target.strftime("%Y%m%d"), target.strftime("%H00")


def evaluate_game_condition(pty: int, rn1: float, wsd: float, is_dome: bool) -> tuple[str, str, str]:
    """
    야구 경기 진행 가능성 및 우천 취소 우려 상태 평가
    반환값: (상태 레이블, 상태 뱃지 클래스, 상태 설명)
    """
    if is_dome:
        return "🔵 돔구장", "badge-dome", "실내 돔구장으로 날씨와 상관없이 100% 정상 진행됩니다."

    # 강수 형태: 0 없음, 1 비, 2 비/눈, 3 눈, 5 빗방울, 6 빗방울눈날림, 7 눈날림
    if pty == 0:
        if wsd >= 10.0:
            return "⚠️ 강풍 주의", "badge-warning", f"강풍(풍속 {wsd}m/s)으로 타구 판단 및 경기 진행에 주의가 필요합니다."
        return "🟢 정상 진행 가능", "badge-safe", "강수가 없어 쾌적하게 경기가 진행될 예정입니다."
    elif pty in (1, 2):
        if rn1 >= 5.0:
            return "🔴 우천 취소 우려", "badge-danger", f"시간당 {rn1}mm의 많은 비가 내려 우천 취소 가능성이 높습니다."
        elif rn1 >= 1.0:
            return "🟡 우천 주의 (방수포)", "badge-caution", f"시간당 {rn1}mm의 비로 경기 지연 및 방수포 설치 가능성이 있습니다."
        else:
            return "🟡 약한 비 (관망)", "badge-caution", "약한 비가 내리고 있어 경기 개시 여부를 지켜보고 있습니다."
    elif pty == 5:
        return "🟡 빗방울 (관망)", "badge-caution", "약한 빗방울이 관측되고 있으나 경기 진행은 가능한 수준입니다."
    elif pty in (3, 6, 7):
        return "❄️ 강설 주의", "badge-danger", "눈으로 인해 그라운드 정비가 필요합니다."

    return "🟢 정상 진행 가능", "badge-safe", "경기 진행에 특이사항이 없습니다."


def parse_weather_icon(pty: int, rn1: float) -> str:
    """날씨 상태 아이콘 반환"""
    if pty == 0:
        return "☀️"
    elif pty in (1, 2, 5):
        if rn1 >= 5.0:
            return "⛈️"
        return "🌧️"
    elif pty in (3, 6, 7):
        return "🌨️"
    return "⛅"


def fetch_stadium_weather(stadium: Dict, api_key: str, base_date: str, base_time: str) -> Dict:
    """단일 구장 초단기실황 조회"""
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
    decoded_key = urllib.parse.unquote(api_key).strip()

    params = {
        "serviceKey": decoded_key,
        "pageNo": "1",
        "numOfRows": "10",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": stadium["nx"],
        "ny": stadium["ny"],
    }

    result = {
        "id": stadium["id"],
        "name": stadium["name"],
        "teams": stadium["teams"],
        "team_short": stadium["team_short"],
        "city": stadium["city"],
        "color": stadium["color"],
        "is_dome": stadium["is_dome"],
        "is_secondary": stadium["is_secondary"],
        "base_date": base_date,
        "base_time": f"{base_time[:2]}:{base_time[2:]}",
        "temp": "--",
        "rain": "0.0 mm",
        "humidity": "--",
        "wind_speed": "0.0 m/s",
        "pty": 0,
        "status_label": "🟢 정상 진행 가능",
        "badge_class": "badge-safe",
        "status_desc": "기상 관측 데이터 수신 완료",
        "icon": "☀️",
    }

    try:
        resp = requests.get(url, params=params, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            items = (
                data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
            )
            obs_map = {}
            for item in items:
                obs_map[item.get("category")] = item.get("obsrValue")

            # T1H (기온 ℃), RN1 (1시간 강수량 mm), PTY (강수형태), REH (습도 %), WSD (풍속 m/s)
            temp = obs_map.get("T1H", "--")
            rain = float(obs_map.get("RN1", 0) or 0)
            humidity = obs_map.get("REH", "--")
            wind_speed = float(obs_map.get("WSD", 0) or 0)
            pty = int(obs_map.get("PTY", 0) or 0)

            status_label, badge_class, status_desc = evaluate_game_condition(
                pty=pty, rn1=rain, wsd=wind_speed, is_dome=stadium["is_dome"]
            )

            temp_num = None
            if temp != "--":
                try:
                    temp_num = float(temp)
                except ValueError:
                    temp_num = None

            humidity_num = None
            if humidity != "--":
                try:
                    humidity_num = float(humidity)
                except ValueError:
                    humidity_num = None

            result.update({
                "temp": f"{temp}℃" if temp != "--" else "--",
                "temp_num": temp_num,
                "rain": f"{rain:.1f} mm",
                "rain_num": rain,
                "humidity": f"{humidity}%" if humidity != "--" else "--",
                "humidity_num": humidity_num,
                "wind_speed": f"{wind_speed:.1f} m/s",
                "wind_num": wind_speed,
                "pty": pty,
                "status_label": status_label,
                "badge_class": badge_class,
                "status_desc": status_desc,
                "icon": parse_weather_icon(pty, rain),
            })
    except Exception as e:
        print(f"[{stadium['name']}] 기상 데이터 조회 실패: {e}")
        if stadium["is_dome"]:
            result["status_label"] = "🛡️ 돔구장 (기상 무관)"
            result["badge_class"] = "badge-dome"
            result["status_desc"] = "실내 돔구장으로 기상과 무관하게 정상 진행"

    return result


def get_all_stadiums_weather() -> Dict:
    """
    KBO 11개 구장(정규 9개 + 제2구장 2개) 전체 실시간 기상정보 조회
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        return {
            "status": "error",
            "message": "DATA_GO_KR_API_KEY 환경변수가 설정되지 않았습니다.",
            "stadiums": [],
        }

    base_date, base_time = get_kma_base_datetime()
    formatted_time = f"{base_date[:4]}.{base_date[4:6]}.{base_date[6:]} {base_time[:2]}:00 발표 기준"

    stadiums_data = []
    for stadium in STADIUMS:
        w_data = fetch_stadium_weather(stadium, api_key, base_date, base_time)
        stadiums_data.append(w_data)

    return {
        "status": "success",
        "base_datetime": formatted_time,
        "count": len(stadiums_data),
        "stadiums": stadiums_data,
    }


def save_current_weather_to_db(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    현재 기상청 초단기실황 기준 11개 구장 날씨를 수집하여 stadium_weather_history 테이블에 고속 UPSERT 적재합니다.
    """
    from mini_project_0909.database import DatabaseManager

    target_db = db_path or DEFAULT_DB_PATH
    res = get_all_stadiums_weather()
    if res.get("status") != "success":
        return {
            "status": "error",
            "message": res.get("message", "기상 데이터 수집에 실패했습니다."),
            "saved_count": 0,
        }

    stadiums_data = res.get("stadiums", [])
    if not stadiums_data:
        return {"status": "error", "message": "수집된 구장 날씨 데이터가 없습니다.", "saved_count": 0}

    # base_date를 YYYY-MM-DD, base_time을 HH:00 형식으로 통일
    records_to_save = []
    for s in stadiums_data:
        raw_date = str(s.get("base_date", "")).replace("-", "")
        raw_time = str(s.get("base_time", "")).replace(":", "")

        formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
        formatted_time = f"{raw_time[:2]}:00" if len(raw_time) >= 2 else raw_time

        item = dict(s)
        item["base_date"] = formatted_date
        item["base_time"] = formatted_time
        records_to_save.append(item)

    saved_count = DatabaseManager.save_stadium_weather_records(records_to_save, target_db)

    return {
        "status": "success",
        "message": f"전국 11개 구장 기상 데이터 DB 적재 완료! (기준: {records_to_save[0]['base_date']} {records_to_save[0]['base_time']})",
        "saved_count": saved_count,
        "base_date": records_to_save[0]["base_date"],
        "base_time": records_to_save[0]["base_time"],
        "stadiums": records_to_save,
    }


def archive_target_time_weather(
    base_date: str,
    base_time: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    지정된 날짜(YYYY-MM-DD 또는 YYYYMMDD) 및 정시 시각(HH:00 또는 HH00)의
    전국 11개 구장 기상 데이터를 기상청 API로 조회하여 DB에 적재합니다.
    """
    from mini_project_0909.database import DatabaseManager

    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "DATA_GO_KR_API_KEY가 없습니다.", "saved_count": 0}

    target_db = db_path or DEFAULT_DB_PATH
    clean_date = base_date.replace("-", "").strip()
    clean_time = base_time.replace(":", "").strip()
    if len(clean_time) == 2:
        clean_time += "00"

    formatted_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}" if len(clean_date) == 8 else clean_date
    formatted_time = f"{clean_time[:2]}:00"

    records = []
    for stadium in STADIUMS:
        w_data = fetch_stadium_weather(stadium, api_key, clean_date, clean_time)
        w_data["base_date"] = formatted_date
        w_data["base_time"] = formatted_time
        records.append(w_data)

    saved_count = DatabaseManager.save_stadium_weather_records(records, target_db)
    return {
        "status": "success",
        "message": f"{formatted_date} {formatted_time} 11개 구장 날씨 {saved_count}건 DB 적재 완료!",
        "saved_count": saved_count,
        "base_date": formatted_date,
        "base_time": formatted_time,
        "stadiums": records,
    }


