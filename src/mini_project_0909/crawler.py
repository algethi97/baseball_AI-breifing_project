"""
네이버 스포츠 (sports.news.naver.com) 야구(KBO / 해외야구) 전용 크롤러 모듈
허용 도메인: sports.naver.com/kbaseball/ 및 sports.naver.com/wbaseball/
"""

import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 엄격하게 허용할 네이버 야구 전용 도메인 및 경로
ALLOWED_BASEBALL_PATHS = [
    "sports.naver.com/kbaseball/",  # 국내야구 (KBO)
    "sports.naver.com/wbaseball/",  # 해외야구 (MLB/NPB)
    "sports.news.naver.com/kbaseball/",
    "sports.news.naver.com/wbaseball/",
    "m.sports.naver.com/kbaseball/",
    "m.sports.naver.com/wbaseball/",
]


def is_baseball_article_url(url: str) -> bool:
    """
    URL이 국내야구(/kbaseball/) 또는 해외야구(/wbaseball/) 기사인지 판별합니다.
    축구, 농구, 골프, 배구 등 타 종목 기사는 False를 반환합니다.
    """
    return any(path in url for path in ALLOWED_BASEBALL_PATHS)


def normalize_baseball_url(url: str) -> str:
    """
    모바일 또는 구형 URL을 데스크톱 표준 네이버 스포츠 기사 URL로 정규화합니다.
    """
    norm = url.replace("m.sports.naver.com", "sports.news.naver.com")
    norm = norm.replace("https://sports.naver.com", "https://sports.news.naver.com")
    norm = norm.replace("http://sports.naver.com", "https://sports.news.naver.com")
    return norm


def search_naver_sports_articles(
    keyword: str,
    start_date: str = "",
    end_date: str = "",
    max_results: int = 200,
) -> list[dict]:
    """
    오직 'sports.naver.com/kbaseball/' 및 'sports.naver.com/wbaseball/' 도메인 내의
    순수 야구 뉴스 기사를 기간 전체에 걸쳐 일자별로 골고루 최대 max_results건(기본 200건) 수집합니다.
    """
    keyword = keyword.strip()
    if not keyword:
        return []

    articles = []
    seen_urls = set()
    query_str = quote(keyword)

    # 1. 일자별 분할 탐색 구간 생성 (기간 내 모든 날짜를 고르게 훑기 위함)
    date_ranges = []
    if start_date and end_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if s_dt <= e_dt:
                curr = e_dt
                while curr >= s_dt:
                    d_str = curr.strftime("%Y-%m-%d")
                    date_ranges.append((d_str, d_str))
                    curr -= timedelta(days=1)
        except Exception:
            date_ranges = [(start_date, end_date)]
    else:
        date_ranges = [(start_date, end_date)]

    # 하루당 권장 수집 목표 (날짜별로 균등 배분)
    num_days = max(1, len(date_ranges))
    per_day_target = max(15, (max_results + num_days - 1) // num_days)

    session = requests.Session()
    session.headers.update({
        **HEADERS,
        "Referer": "https://search.naver.com/",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    try:
        for s_d, e_d in date_ranges:
            if len(articles) >= max_results:
                break

            day_collected = 0
            date_params = "&sort=1"
            if s_d and e_d:
                s_dot = s_d.replace("-", ".")
                e_dot = e_d.replace("-", ".")
                s_num = s_d.replace("-", "")
                e_num = e_d.replace("-", "")
                date_params = f"&sort=1&pd=3&ds={s_dot}&de={e_dot}&nso=so:dd,p:from{s_num}to{e_num}"

            # 해당 일자의 기사를 페이징하며 수집 (최대 30위까지 탐색하여 균등 분배)
            for page_start in range(1, 31, 10):
                if day_collected >= per_day_target or len(articles) >= max_results:
                    break

                search_url = (
                    f"https://search.naver.com/search.naver?where=news&query={query_str}"
                    f"&sm=tab_opt&photo=0&field=0{date_params}&start={page_start}"
                )

                response = None
                for attempt in range(2):
                    time.sleep(0.35)  # 연속 요청 시 403 Rate Limit 차단 방지 딜레이
                    try:
                        resp = session.get(search_url, timeout=6)
                        if resp.status_code == 200:
                            response = resp
                            break
                        elif resp.status_code == 403:
                            time.sleep(0.8)  # 403 시 잠시 대기 후 1회 재시도
                    except Exception:
                        break

                if not response or response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                # 카드 식별
                tab = soup.find(class_="fds-news-item-list-tab")
                if tab:
                    cards = [
                        c
                        for c in tab.find_all(recursive=False)
                        if c.find("a", {"data-heatmap-target": ".tit"})
                    ]
                else:
                    cards = (
                        soup.select("ul.list_news > li")
                        or soup.find_all("li", class_="bx")
                        or soup.find_all("div", class_="news_wrap")
                    )

                if not cards:
                    break

                count_before = len(articles)

                for card in cards:
                    if day_collected >= per_day_target or len(articles) >= max_results:
                        break

                    # 야구 전용 링크 확인
                    baseball_a = None
                    for a in card.find_all("a", href=True):
                        href = a["href"]
                        if is_baseball_article_url(href):
                            baseball_a = a
                            break

                    if not baseball_a:
                        continue

                    raw_url = baseball_a["href"]
                    norm_url = normalize_baseball_url(raw_url)
                    if norm_url in seen_urls:
                        continue
                    seen_urls.add(norm_url)

                    # 제목 추출
                    tit_elem = card.find(
                        "a", {"data-heatmap-target": ".tit"}
                    ) or card.find("a", class_=lambda c: c and "tit" in c)
                    title = (
                        tit_elem.text.replace("새 창 열림", "").strip()
                        if tit_elem
                        else baseball_a.text.replace("새 창 열림", "").strip()
                    )
                    if not title or "네이버뉴스" in title:
                        continue

                    # 언론사 추출
                    press = "스포츠언론사"
                    press_elem = card.find(
                        class_=lambda c: c
                        and (
                            "profile-info-title-text" in c
                            or "profile-info-title" in c
                            or "press" in c
                        )
                    )
                    if press_elem:
                        p_text = (
                            press_elem.text.replace("새 창 열림", "")
                            .replace("언론사 선정", "")
                            .strip()
                        )
                        if p_text and p_text != "새 창 열림":
                            press = p_text

                    # 날짜 추출
                    art_date = s_d if (s_d and s_d == e_d) else ""
                    if not art_date:
                        card_text = card.get_text(separator=" ", strip=True)
                        abs_match = re.search(
                            r"(202\d)[.\-]([01]\d)[.\-]([0-3]\d)", card_text
                        )
                        if abs_match:
                            art_date = f"{abs_match.group(1)}-{abs_match.group(2)}-{abs_match.group(3)}"
                        else:
                            rel_day = re.search(r"(\d+)\s*일\s*전", card_text)
                            rel_hour = re.search(r"(\d+)\s*(?:시간|분|초)\s*전", card_text)
                            if rel_day:
                                art_date = (
                                    datetime.now()
                                    - timedelta(days=int(rel_day.group(1)))
                                ).strftime("%Y-%m-%d")
                            elif "어제" in card_text:
                                art_date = (
                                    datetime.now() - timedelta(days=1)
                                ).strftime("%Y-%m-%d")
                            elif rel_hour:
                                art_date = datetime.now().strftime("%Y-%m-%d")
                            else:
                                art_date = s_d or datetime.now().strftime("%Y-%m-%d")

                    dsc = card.find(class_=lambda c: c and "dsc" in c)
                    snippet = (
                        dsc.text.replace("새 창 열림", "").strip() if dsc else ""
                    )

                    category = "국내야구" if "kbaseball" in norm_url else "해외야구"

                    articles.append({
                        "id": len(articles) + 1,
                        "category": category,
                        "title": title,
                        "press": press,
                        "date": art_date,
                        "url": norm_url,
                        "snippet": snippet,
                    })
                    day_collected += 1

                if len(articles) == count_before:
                    break

        return articles[:max_results]

    except Exception as e:
        print(f"네이버 야구 기사 크롤링 중 오류: {e}")
        return []



def fetch_article_content(url: str) -> str:
    """
    네이버 스포츠 야구 기사 상세 페이지 본문 텍스트를 추출합니다.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        content_div = soup.find("div", id="newsEndContents") or soup.find(
            "div", class_=lambda c: c and ("news_end" in c or "artice_body" in c)
        )

        if content_div:
            for tag in content_div(["script", "style", "div", "iframe"]):
                tag.decompose()
            text = content_div.get_text(separator="\n").strip()
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text[:1500]

        return ""
    except Exception as e:
        print(f"기사 상세 본문 추출 오류 ({url}): {e}")
        return ""
