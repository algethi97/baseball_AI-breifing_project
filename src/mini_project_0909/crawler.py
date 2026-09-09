"""
네이버 스포츠 (sports.news.naver.com) 야구(KBO / 해외야구) 전용 크롤러 모듈
허용 도메인: sports.naver.com/kbaseball/ 및 sports.naver.com/wbaseball/
"""

import re
from datetime import datetime
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
    max_results: int = 20,
) -> list[dict]:
    """
    오직 'sports.naver.com/kbaseball/' 및 'sports.naver.com/wbaseball/' 도메인 내의
    순수 야구 뉴스 기사만 정밀하게 수집합니다.
    """
    keyword = keyword.strip()
    if not keyword:
        return []

    # 네이버 날짜 포맷 변환 (YYYY-MM-DD -> YYYY.MM.DD & YYYYMMDD)
    date_params = ""
    if start_date and end_date:
        s_dot = start_date.replace("-", ".")
        e_dot = end_date.replace("-", ".")
        s_num = start_date.replace("-", "")
        e_num = end_date.replace("-", "")
        date_params = f"&pd=3&ds={s_dot}&de={e_dot}&nso=so:r,p:from{s_num}to{e_num}"

    # 네이버 뉴스 검색 URL
    query_str = quote(keyword)
    search_url = (
        f"https://search.naver.com/search.naver?where=news&query={query_str}"
        f"&sm=tab_opt&sort=0&photo=0&field=0{date_params}"
    )

    try:
        response = requests.get(search_url, headers=HEADERS, timeout=8)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        articles = []
        seen_urls = set()

        # 링크 중 오직 kbaseball 또는 wbaseball 경로만 필터링
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # 타 스포츠(축구, 농구, 골프 등) 및 일반 뉴스 원천 배제
            if not is_baseball_article_url(href):
                continue

            # 표준 데스크톱 URL로 정규화
            norm_url = normalize_baseball_url(href)
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            # 기사 카드 블록(부모 컨테이너) 탐색
            parent_container = a_tag
            for _ in range(8):
                if parent_container.parent:
                    parent_container = parent_container.parent
                    title_candidate = parent_container.find(
                        "a", {"data-heatmap-target": ".tit"}
                    ) or parent_container.find(
                        "a", class_=lambda c: c and "tit" in c
                    )
                    if title_candidate and title_candidate.text.strip():
                        break

            # 1. 제목 추출
            title = ""
            if title_candidate:
                title = title_candidate.text.replace("새 창 열림", "").strip()

            if not title:
                title = a_tag.text.replace("새 창 열림", "").strip()
                if "네이버뉴스" in title or not title:
                    continue

            # 2. 언론사 추출 (네이버 SDS 개편 UI 대응 및 '새 창 열림' 접근성 텍스트 제거)
            press = "스포츠언론사"
            press_elem = parent_container.find(
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
            else:
                # 보조 탐색 (클래스 info, source 태그 중 유효 언론사 필터)
                info_elems = parent_container.find_all(
                    class_=lambda c: c and ("info" in c or "source" in c)
                )
                for ie in info_elems:
                    txt = (
                        ie.text.replace("새 창 열림", "")
                        .replace("언론사 선정", "")
                        .strip()
                    )
                    if (
                        txt
                        and txt != "새 창 열림"
                        and "네이버뉴스" not in txt
                        and "면" not in txt
                        and "전" not in txt
                        and len(txt) <= 20
                    ):
                        press = txt
                        break

            # 3. 날짜 추출
            article_date = end_date or datetime.now().strftime("%Y-%m-%d")
            date_match = re.search(
                r"(202\d[.\-]?[01]\d[.\-]?[0-3]\d)", parent_container.text
            )
            if date_match:
                raw_d = date_match.group(1).replace(".", "-")
                article_date = raw_d
            else:
                rel_match = re.search(r"(\d+)\s*(시간|일|분)\s*전", parent_container.text)
                if rel_match:
                    article_date = datetime.now().strftime("%Y-%m-%d")

            # 4. 스니펫 (본문 요약)
            snippet = ""
            dsc_elem = parent_container.find(
                "a", class_=lambda c: c and "dsc" in c
            ) or parent_container.find(
                "div", class_=lambda c: c and "dsc" in c
            )
            if dsc_elem:
                snippet = dsc_elem.text.replace("새 창 열림", "").strip()

            # 카테고리 태그 (국내야구 vs 해외야구)
            category = "국내야구" if "kbaseball" in href else "해외야구"

            articles.append({
                "id": len(articles) + 1,
                "category": category,
                "title": title,
                "press": press,
                "date": article_date,
                "url": norm_url,
                "snippet": snippet,
            })

            if len(articles) >= max_results:
                break

        return articles

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
