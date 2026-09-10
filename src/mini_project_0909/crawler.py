"""
네이버 스포츠 (sports.news.naver.com) 야구(KBO / 해외야구) 전용 크롤러 모듈
허용 도메인: sports.naver.com/kbaseball/ 및 sports.naver.com/wbaseball/
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional
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


def extract_article_snippet(card, title: str = "", press: str = "") -> str:
    """
    네이버 검색 결과 카드에서 기사 요약문(스니펫)을 다단계로 안전하게 추출합니다.
    (네이버 HTML 태그가 향후 변경되더라도 깨지지 않는 태그 독립적 3단계 방어막 적용)

    1단계: 최신 네이버 검색 SDS 컴포넌트 셀렉터 (data-heatmap-target=".body" 또는 .sds-comps-text-type-body1)
    2단계: 시맨틱 클래스 키워드 확장 탐색 (body, lead, desc, dsc, summary 등)
    3단계: 태그 무관 텍스트 차집합 휴리스틱 (제목, 언론사, 날짜 등 메타 텍스트를 제외한 최장 본문 문장 자동 판별)
    """
    if not card:
        return ""

    # 1단계: 최신 네이버 검색 SDS 컴포넌트 정밀 셀렉터
    target = card.find("a", {"data-heatmap-target": ".body"}) or card.find(
        class_=lambda c: c and ("body1" in c or "lead" in c or "dsc" in c)
    )
    if target:
        txt = target.get_text(separator=" ", strip=True).replace("새 창 열림", "").strip()
        txt = re.sub(r"\s+", " ", txt)
        if len(txt) >= 15:
            return txt

    # 2단계: 시맨틱 클래스 확장 탐색
    for c_elem in card.find_all(class_=True):
        classes = " ".join(c_elem.get("class", []))
        if any(k in classes for k in ["body", "lead", "desc", "dsc", "summary", "preview", "snippet"]):
            txt = c_elem.get_text(separator=" ", strip=True).replace("새 창 열림", "").strip()
            txt = re.sub(r"\s+", " ", txt)
            if len(txt) >= 20 and (not title or title not in txt):
                return txt

    # 3단계: 태그 무관 텍스트 차집합 휴리스틱 (Class-agnostic Fallback)
    noise_keywords = [
        "새 창 열림", "네이버뉴스", "언론사 선정", "Keep", "바로가기",
        "더보기", "문서 저장", "공유", "동영상", "재생시간"
    ]
    card_lines = [
        line.strip()
        for line in card.get_text(separator="\n", strip=True).splitlines()
        if line.strip()
    ]

    candidates = []
    for line in card_lines:
        line_clean = re.sub(r"\s+", " ", line)
        if len(line_clean) < 15:
            continue
        if title and (line_clean in title or title in line_clean):
            continue
        if press and press in line_clean:
            continue
        if any(k in line_clean for k in noise_keywords):
            continue
        # 날짜 형식 제외
        if re.search(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$", line_clean):
            continue
        if re.search(r"^\d+\s*(?:시간|분|초|일)\s*전$", line_clean):
            continue
        candidates.append(line_clean)

    if candidates:
        # 가장 길고 정보량이 풍부한 본문 문장을 스니펫으로 선정
        candidates.sort(key=len, reverse=True)
        return candidates[0]

    return ""


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

                    snippet = extract_article_snippet(card, title=title, press=press)

                    category = "국내야구" if "kbaseball" in norm_url else "해외야구"

                    articles.append({
                        "id": len(articles) + 1,
                        "category": category,
                        "title": title,
                        "press": press,
                        "date": art_date,
                        "url": norm_url,
                        "content": snippet,  # 1차로 스니펫을 임시 보관 (본문 수집 실패 시 안전 폴백용)
                    })
                    day_collected += 1

                if len(articles) == count_before:
                    break

        final_articles = articles[:max_results]

        # 2. 수집된 전체 기사의 원문(Full Text) 초고속 병렬 수집 (차단 방지 세션 풀 적용)
        if final_articles:
            with requests.Session() as p_session:
                p_session.headers.update({
                    **HEADERS,
                    "Referer": "https://sports.news.naver.com/",
                })
                with ThreadPoolExecutor(max_workers=6) as executor:
                    future_to_art = {
                        executor.submit(fetch_article_content, a["url"], p_session): a
                        for a in final_articles
                    }
                    for future in as_completed(future_to_art):
                        art = future_to_art[future]
                        try:
                            full_text = future.result()
                            if full_text and len(full_text) >= 40:
                                art["content"] = full_text
                        except Exception:
                            pass

        return final_articles

    except Exception as e:
        print(f"네이버 야구 기사 크롤링 중 오류: {e}")
        return []


def fetch_article_content(url: str, session: Optional[requests.Session] = None) -> str:
    """
    네이버 스포츠 야구 기사 상세 페이지 본문 텍스트 전체(Full Text)를 정제하여 추출합니다.
    (광고, 스크립트, 저작권 문구, 사진 캡션 등 노이즈 제거)
    """
    try:
        requester = session or requests
        headers = {
            **HEADERS,
            "Referer": "https://sports.news.naver.com/",
        }
        resp = requester.get(url, headers=headers, timeout=6)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        # 1순위: 헤더 메타(입력일시, 음성듣기 등)를 배제한 순수 기사 본체 정밀 셀렉터
        content_div = (
            soup.select_one("#comp_news_article > div")
            or soup.select_one("._article_content")
            or soup.find("div", id="newsEndContents")
            or soup.find(id="dic_area")
            or soup.find(id="articleBody")
        )

        if not content_div:
            return ""

        # 광고, 스크립트, 사진 캡션 등 노이즈 태그 제거
        for tag in content_div(["script", "style", "iframe", "button", "form", "figure", "figcaption", "em"]):
            tag.decompose()

        # 사진 및 캡션 전용 클래스 태그 제거 (span.end_photo_org, em.img_desc 등)
        for photo_tag in content_div.find_all(class_=lambda c: c and any(k in c for k in ["end_photo_org", "img_desc", "photo_caption"])):
            photo_tag.decompose()

        # 줄바꿈 태그 변환 및 텍스트 추출 (인라인 태그로 인한 과도한 줄바꿈 방지)
        for br in content_div.find_all("br"):
            br.replace_with("\n")
        for p in content_div.find_all("p"):
            p.append("\n")

        raw_text = content_div.get_text().strip()
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        # 저작권, 기사제공, 무단전재 등 하단 노이즈 라인 필터링
        clean_lines = []
        for l in lines:
            if any(k in l for k in ["기사제공", "ⓒ", "Copyright", "무단 전재", "재배포 금지", "무단전재"]):
                continue
            clean_lines.append(l)

        full_text = "\n".join(clean_lines).strip()
        return full_text

    except Exception as e:
        return ""

