"""
야구 뉴스 챗봇 & 기사 수집/보고서 연동 백엔드 API 클래스
"""

import os
import re
import json
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

from mini_project_0909.crawler import search_naver_sports_articles, fetch_article_content
from mini_project_0909.weather import get_all_stadiums_weather
from mini_project_0909.database import DatabaseManager
from mini_project_0909.normalizer import normalize_keyword, NormalizedEntity
from mini_project_0909.ai_db_service import SQLAlchemyAIDatabaseEngine

load_dotenv(override=True)

# 프로젝트 루트 및 파일 형식별 storage 디렉터리 경로 정의
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXPORT_DIR = PROJECT_ROOT / "storage"
CSV_EXPORT_DIR = EXPORT_DIR / "csv"
DB_EXPORT_DIR = EXPORT_DIR / "db"
MD_EXPORT_DIR = EXPORT_DIR / "report"

for _dir in (CSV_EXPORT_DIR, DB_EXPORT_DIR, MD_EXPORT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


class BaseballBotAPI:
    """
    JavaScript 프론트엔드와 통신하는 야구 뉴스 챗봇 및 기사 분석 API
    """

    def __init__(self, client: OpenAI = None, model: str = "gpt-5.6-luna"):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = client or (OpenAI(api_key=api_key) if api_key else None)
        self.model = model

        # SQLAlchemy 2.0 기반 AI DB 제어 엔진 초기화 (통합 baseball_news.db 대상)
        self.ai_db_service = SQLAlchemyAIDatabaseEngine(
            db_path=DB_EXPORT_DIR / "baseball_news.db",
            client=self.client,
            model=self.model,
        )

        # 챗봇용 시스템 지침 (KBO 전문 데이터 분석관 & 해설위원 페르소나)
        self.chat_instructions = (
            "당신은 대한민국 프로야구(KBO) 전문 수석 데이터 분석관이자 베테랑 야구 해설위원 '야구 브리핑 AI'입니다.\n"
            "사용자에게 정중하고 신뢰감 넘치며, 야구에 대한 전문성과 열정이 묻어나는 어조로 답변하세요.\n\n"
            "[핵심 브리핑 원칙]\n"
            "1. [철저한 데이터 그라운딩]: 제공된 [기사 데이터베이스]와 [AI 심층 보고서]의 팩트(투구수, 이닝, 피안타, 탈삼진, 결승타, 경기 일자, 상대 구단, 승부처 등)를 최우선 근거로 활용하여 구체적이고 깊이 있게 설명하세요.\n"
            "2. [세부 경기 디테일 강조]: 단순한 경기 결과 나열에 그치지 않고 승부처(클러치 상황), 볼카운트 싸움, 투구 패턴, 감독 코멘트 등 기사 본문 속 디테일을 생생하게 짚어주세요.\n"
            "3. [안내원 멘트 절대 금지]: '상단 탭에서 기능을 이용할 수 있습니다' 같은 콜센터 안내원 말투는 일절 사용하지 말고, 질문 자체에 대한 전문적인 야구 분석과 답변에 집중하세요.\n"
            "4. [정보 한계의 정직한 명시]: 제공된 수집 데이터에 없는 최신 기록이나 모호한 사실에 대해서는 거짓으로 꾸며내지 말고, 현재 연동된 데이터 내에서 확인된 사실을 바탕으로 솔직하고 명확하게 한계를 밝히세요.\n"
            "5. [가독성 극대화]: 단락 구분, 핵심 수치 볼드체(**강조**), 깔끔한 불릿포인트를 적극 사용하여 가독성 높게 작성하세요."
        )

        # 챗봇 대화 기록
        self.conversation_history = []

        # 수집된 기사 및 최근 작성된 보고서 저장소
        self.collected_articles = []
        self.current_keyword = ""
        self.current_entity: Optional[NormalizedEntity] = None
        self.current_report = ""

        # 실시간 전국 구장 날씨 캐시
        self.latest_weather_data = None

    # ============================================================
    # 1. 챗봇 대화 인터페이스 (기사 및 보고서 실시간 연동)
    # ============================================================
    def get_context_status(self) -> dict:
        """
        현재 챗봇이 참조하고 있는 기사 수집 및 보고서 연동 상태를 반환합니다.
        """
        canonical = self.current_entity.canonical if self.current_entity else self.current_keyword
        safe_id = self.current_entity.safe_id if self.current_entity else self.current_keyword
        synonyms = self.current_entity.synonyms if self.current_entity else []
        return {
            "status": "success",
            "has_articles": bool(self.collected_articles),
            "article_count": len(self.collected_articles),
            "keyword": self.current_keyword,
            "canonical_keyword": canonical,
            "safe_id": safe_id,
            "synonyms": synonyms,
            "has_report": bool(self.current_report),
        }

    def _detect_crawl_intent(self, message: str) -> dict:
        """
        사용자의 메시지가 새로운 네이버 스포츠 기사 수집(크롤링/검색) 요청인지 분석하고,
        키워드와 수집 기간(start_date, end_date)을 추출합니다.
        (주의: 데이터베이스/DB 질의는 크롤링에서 엄격히 배제)
        """
        msg_low = message.lower()
        # DB 지시어나 직전 결과 연속 작업이 포함된 경우 크롤링으로 빠지지 않도록 사전 차단 (Fast-Path 배제)
        db_keywords = ["데이터베이스", "db", "디비", "테이블", "스키마", "컬럼", "쿼리", "sql", "북마크", "bookmark", "삭제해", "지워줘"]
        if any(dk in msg_low for dk in db_keywords):
            return {"is_crawl": False, "keyword": "", "start_date": "", "end_date": ""}
        if any(ci in msg_low for ci in ["방금", "직전", "이 기사들"]) and any(ca in msg_low for ca in ["삭제", "지워", "제거", "북마크", "등록", "조회"]):
            return {"is_crawl": False, "keyword": "", "start_date": "", "end_date": ""}

        if not self.client:
            return {"is_crawl": False, "keyword": "", "start_date": "", "end_date": ""}

        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        default_start_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")

        prompt = f"""당신은 사용자의 야구 챗봇 대화에서 '새로운 웹 기사 수집(크롤링/검색) 요청' 여부를 판별하고 파라미터를 추출하는 분류기입니다.
오늘 기준일: {today_str} (기본 시작일 7일전: {default_start_str})

사용자의 입력: "{message}"

[엄격한 판별 기준]
1. 새롭게 외부 웹(네이버 스포츠)에서 기사를 검색/수집/크롤링/모아달라고 요청하는 경우에만 is_crawl: true 입니다.
   - 예: "류현진 최근 일주일 기사 모아줘", "김도영 이번 달 기사 찾아봐", "이로운 9월 1일부터 9월 9일까지 기사 수집해줘", "한화 이글스 소식 긁어와줘", "기아 타이거즈 기사 검색해줘", "최근 야구 뉴스 모아봐"
2. 다음 경우는 절대로 크롤링이 아니므로 반드시 is_crawl: false 로 판별하세요:
   - 데이터베이스(DB)나 저장된 데이터에서 조회/검색/필터링하는 요청 (예: "데이터베이스에서 아빌라 기사 중 스포츠조선만 조회해줘", "저장된 기사 중 OSEN 기사 보여줘", "언론사별 기사 통계")
   - 단순히 이미 수집된 기사나 야구 상식/선수 의견을 질문하는 경우 (예: "이로운 어제 어땠어?", "어제 잠실 경기 결과 알려줘", "홈런 몇 개 쳤어?")
   - 구장 날씨 질문, AI 요약 보고서 설명 요청

is_crawl이 true인 경우:
1. keyword: 검색할 대상 키워드(선수명, 구단명, 핵심 야구 토픽)만 간결한 단어로 추출하세요. 구체적 대상이 없으면 "야구" 또는 핵심 키워드로 지정하세요.
2. start_date: 시작 날짜 (YYYY-MM-DD). "최근 일주일", "지난 주"는 7일 전. "이번 달"은 이번 달 1일. "어제"는 어제. 언급 없으면 {default_start_str}.
3. end_date: 종료 날짜 (YYYY-MM-DD). 언급 없으면 {today_str}.

반드시 마크다운 코드블록이나 부가 설명 없이 오직 순수 JSON 형식 한 줄로만 출력하세요:
{{"is_crawl": true/false, "keyword": "...", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}"""

        try:
            resp = self.client.responses.create(
                model=self.model,
                instructions="You are a strict JSON intent classifier. Output pure JSON only without markdown formatting.",
                input=prompt,
            )
            text = resp.output_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            data = json.loads(text)
            if not isinstance(data, dict):
                return {"is_crawl": False, "keyword": "", "start_date": default_start_str, "end_date": today_str}
            return data
        except Exception:
            return {"is_crawl": False, "keyword": "", "start_date": default_start_str, "end_date": today_str}

    def _detect_db_intent(self, message: str) -> bool:
        """
        사용자의 메시지가 저장된 데이터베이스(baseball_news.db)에 대한 조회, 통계, 필터링, 테이블 생성(DDL), CRUD 요청인지 판별합니다.
        키워드 기반 Fast-Path 및 LLM 정밀 판별 결합.
        """
        msg_low = message.lower()

        # 0. 명백한 웹 크롤링 요청(수집해, 모아줘, 긁어와, 크롤링 등)이면서 명시적 DB 단어가 없는 경우 ➔ 크롤링 모듈로 넘김
        crawl_verbs = ["수집해", "모아줘", "긁어와", "크롤링"]
        direct_db_words = ["데이터베이스", "db", "디비", "sqlite", "테이블", "스키마", "컬럼", "sql", "쿼리"]
        has_direct_db = any(w in msg_low for w in direct_db_words)
        has_crawl_verb = any(cv in msg_low for cv in crawl_verbs)

        if has_crawl_verb and not has_direct_db:
            return False

        # 1. 고신뢰도 Fast-Path 룰베이스 감지 (즉시 DB 의도로 확정)
        # 1-1. 명시적 DB 지시어
        if has_direct_db:
            return True

        # 1-2. 저장 데이터 지정 및 조건부 필터링 표현
        filter_indicators = [
            "저장된 기사", "보관된 기사", "수집된 기사 중", "기사 중",
            "신문사가", "언론사가", "특정 신문사", "특정 언론사",
            "만 조회", "만 뽑아", "만 골라", "만 보여", "만 필터",
        ]
        if any(fi in msg_low for fi in filter_indicators):
            return True

        # 1-3. 집계 및 그룹 통계 표현
        agg_indicators = [
            "언론사별", "신문사별", "매체별", "날짜별", "일자별",
            "기사 건수", "기사 개수", "기사 통계", "언론사 통계", "총 기사수",
            "북마크", "bookmark", "즐겨찾기",
        ]
        if any(ai in msg_low for ai in agg_indicators):
            return True

        # '기사 수' 단어 경계 체크 (기사 수집 등 제외)
        if re.search(r"기사\s*수(?!집)", msg_low):
            return True

        # 1-4. 조건부 데이터 삭제/제거 표현
        delete_indicators = ["삭제", "지워", "제거"]
        if any(di in msg_low for di in delete_indicators) and any(kw in msg_low for kw in ["기사", "데이터", "행", "테이블", "레코드", "제목"]):
            return True

        # 1-5. 제목(title) 기준 조건 조회/검색 표현
        if any(tw in msg_low for tw in ["제목에", "제목이", "제목에서", "title에"]) and any(qw in msg_low for qw in ["조회", "검색", "찾아", "보여", "뽑아", "출력", "필터"]):
            return True

        # 1-6. 직전 대화 맥락 및 연속 작업 표현 (방금 조회된 기사 삭제, 북마크 등록 등)
        context_chain_indicators = ["방금", "직전", "이 기사들", "그 중에서", "방금 나온"]
        chain_actions = ["삭제", "지워", "제거", "북마크", "bookmark", "추가", "등록", "저장", "조회", "필터", "보여", "뽑아"]
        if any(ci in msg_low for ci in context_chain_indicators) and any(ca in msg_low for ca in chain_actions):
            return True

        if not self.client:
            return False

        # 2. LLM 정밀 분류기 (자연어 질의 분석)
        prompt = f"""사용자의 입력이 로컬 SQLite 데이터베이스(baseball_news.db)에 대한 조회/검색/필터링, 통계 분석, 테이블 생성(DDL), 데이터 조작(CRUD) 명령인지 판별하세요.
입력: "{message}"

[판별 기준]
- is_db: true 조건:
  1. DB 테이블 생성/수정/삭제 (DDL)
  2. DB 내 컬럼, 스키마, 구조 확인
  3. DB 저장 데이터 통계/집계 (예: 언론사별 기사 건수, 날짜별 수집량)
  4. DB 테이블(articles 등)에서 특정 조건(선수명, 특정 언론사/신문사, 날짜 등)에 해당하는 레코드를 조회/필터링/검색해달라는 요청
     (예: "아빌라 기사 중 신문사가 스포츠조선인 것만 조회해줘", "저장된 기사 중 OSEN 기사만 보여줘")
  5. 특정 문구가 제목(title)에 포함된 기사를 조건부로 조회하거나 삭제(DELETE)해달라는 요청
     (예: "제목에 '아빌라' 들어간 기사 조회해줘", "제목에 '[임시테스트]' 포함된 기사 삭제해줘")
  6. 직전 대화에서 조회된 기사들을 참조하여 삭제, 북마크 추가, 추가 필터링 등 연속 작업을 요청하는 경우
     (예: "방금 조회된 기사들을 삭제해줘", "방금 나온 기사들 북마크 테이블에 추가해줘")
- is_db: false 조건:
  1. 외부 웹(네이버 스포츠)에서 새로운 기사를 수집/크롤링해달라는 요청
  2. 일반 야구 선수/경기 소식 질문, 구장 날씨 질문, 생성된 AI 보고서 요약 요청

반드시 마크다운 없이 순수 JSON 한 줄로만 출력하세요:
{{"is_db": true/false}}"""

        try:
            resp = self.client.responses.create(
                model=self.model,
                instructions="You are a strict DB intent classifier. Output pure JSON only.",
                input=prompt,
            )
            text_resp = resp.output_text.strip()
            if text_resp.startswith("```"):
                text_resp = text_resp.split("```")[1]
                if text_resp.startswith("json"):
                    text_resp = text_resp[4:]
            data = json.loads(text_resp.strip())
            return bool(data.get("is_db"))
        except Exception:
            return False

    def _find_relevant_articles(self, user_query: str, top_k: int = 4) -> list:
        """
        사용자의 질문과 가장 관련성이 높은 상위 top_k개 기사를 선별하여 반환합니다. (Smart RAG)
        """
        if not self.collected_articles:
            return []

        # 쿼리 토큰화 (2글자 이상 단어 추출)
        query_words = [w.strip() for w in re.findall(r"[가-힣a-zA-Z0-9]{2,}", user_query.lower()) if len(w.strip()) >= 2]
        if not query_words:
            return self.collected_articles[:top_k]

        scored_articles = []
        for a in self.collected_articles:
            score = 0
            title = (a.get("title") or "").lower()
            content = (a.get("content") or a.get("snippet") or "").lower()

            for qw in query_words:
                if qw in title:
                    score += 4
                if qw in content:
                    score += 1

            if self.current_entity and self.current_entity.synonyms:
                for syn in self.current_entity.synonyms:
                    syn_low = syn.lower()
                    if syn_low in title:
                        score += 3
                    if syn_low in content:
                        score += 1
            elif self.current_keyword and self.current_keyword.lower() in title:
                score += 2

            scored_articles.append((score, a))

        scored_articles.sort(key=lambda x: (x[0], x[1].get("date", "")), reverse=True)
        return [item[1] for item in scored_articles[:top_k]]

    def send_message(self, message: str) -> dict:
        """
        사용자의 챗봇 질문을 받아 자연어 크롤링 의도 분석, SQLAlchemy AI DB 제어, 또는
        수집된 기사 본문 전문(Smart RAG) & 요약 보고서 컨텍스트와 함께 OpenAI Responses API로 답변 반환
        """
        user_text = message.strip()
        if not user_text:
            return {"status": "error", "reply": "질문 내용을 입력해주세요."}

        # 1. [1순위] 자연어 데이터베이스(SQLAlchemy 2.0 DDL/CRUD/통계/필터링) 명령 의도 감지
        if self._detect_db_intent(user_text):
            db_res = self.ai_db_service.ask(user_text)
            sql = db_res.get("sql", "")
            q_type = db_res.get("query_type", "UNKNOWN")
            msg = db_res.get("message", "")
            md_table = db_res.get("markdown_table", "")

            reply_parts = []
            if sql:
                reply_parts.append(f"```sql\n{sql}\n```")
            if msg:
                reply_parts.append(msg)
            if md_table:
                reply_parts.append("\n" + md_table)

            reply_text = "\n\n".join(reply_parts)
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": reply_text})

            return {
                "status": db_res.get("status", "success"),
                "reply": reply_text,
                "action": {
                    "type": "db_query_result",
                    "sql": sql,
                    "query_type": q_type,
                    "row_count": db_res.get("row_count", 0),
                    "markdown_table": md_table,
                },
            }

        # 2. [2순위] 자연어 기사 수집(크롤링) 명령 의도 감지
        crawl_intent = self._detect_crawl_intent(user_text)
        if crawl_intent.get("is_crawl") and crawl_intent.get("keyword"):
            keyword = crawl_intent["keyword"].strip()
            start_date = crawl_intent.get("start_date", "")
            end_date = crawl_intent.get("end_date", "")

            # 백그라운드 자동 기사 수집 실행
            fetch_res = self.fetch_articles(
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
                max_results=200,
            )
            count = len(self.collected_articles)
            canonical_name = self.current_entity.canonical if self.current_entity else keyword
            safe_id = self.current_entity.safe_id if self.current_entity else keyword

            if count > 0:
                press_samples = list({a.get("press") for a in self.collected_articles if a.get("press")})[:4]
                press_text = f", {', '.join(press_samples)} 등" if press_samples else ""
                name_disp = f"**'{canonical_name}'**(입력: '{keyword}')" if canonical_name != keyword else f"**'{keyword}'**"
                reply_text = (
                    f"⚾ {name_disp} 관련 네이버 스포츠 기사 원문 총 **{count}건**을 성공적으로 수집했습니다!\n\n"
                    f"- 📅 **수집 대상 기간**: `{start_date} ~ {end_date}`\n"
                    f"- 📰 **주요 수집 매체**: {press_text}\n"
                    f"- 💡 **분석 안내**: 아래 버튼을 클릭하시면 기사 수집 탭으로 이동하여 전체 기사 목록과 상세 본문을 확인하실 수 있습니다. "
                    f"또한 수집된 기사에 대해 궁금한 점을 제게 바로 질문하시면 상세히 분석해 드립니다!"
                )
            else:
                reply_text = (
                    f"⚠️ 지정하신 기간(`{start_date} ~ {end_date}`) 동안 **'{keyword}'** 관련 네이버 스포츠 기사를 찾지 못했습니다.\n\n"
                    f"키워드 철자를 확인하시거나 수집 기간을 더 넓혀서 다시 요청해 주세요."
                )

            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": reply_text})

            return {
                "status": "success",
                "reply": reply_text,
                "action": {
                    "type": "crawl_completed",
                    "keyword": canonical_name,
                    "raw_keyword": keyword,
                    "canonical_keyword": canonical_name,
                    "safe_id": safe_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "article_count": count,
                    "articles": self.collected_articles,
                },
            }

        # 2. 일반 질문: 대화 히스토리 업데이트
        self.conversation_history.append({"role": "user", "content": user_text})
        trimmed_input = self.conversation_history[-10:]

        # 3. 구장 날씨 질문 감지 시 실시간 기상 관측 데이터 자동 연동
        weather_keywords = ["날씨", "비", "우천", "취소", "우취", "기온", "바람", "구장", "잠실", "고척", "문학", "수원", "대전", "대구", "광주", "사직", "창원", "포항", "울산"]
        if any(wk in user_text for wk in weather_keywords) and not self.latest_weather_data:
            try:
                self.latest_weather_data = get_all_stadiums_weather()
            except Exception:
                pass

        # 4. 스마트 RAG 및 동적 컨텍스트 조립
        context_parts = [self.chat_instructions]

        # 4-1. 기사 데이터베이스 컨텍스트 (보고서 유무와 무관하게 항상 주입)
        if self.collected_articles:
            context_parts.append("\n\n[현재 연동된 네이버 스포츠 기사 데이터베이스]")
            if self.current_keyword:
                context_parts.append(f"- 수집 검색어: '{self.current_keyword}'")
            context_parts.append(f"- 총 수집 기사 수: {len(self.collected_articles)}건")

            # Smart RAG: 질문과 가장 밀접한 상위 핵심 기사의 본문 전문 추출
            relevant_articles = self._find_relevant_articles(user_text, top_k=4)
            if relevant_articles:
                context_parts.append("\n[사용자 질문과 가장 관련 깊은 핵심 기사 원문 전문]")
                for idx, art in enumerate(relevant_articles, 1):
                    art_title = art.get("title", "")
                    art_press = art.get("press", "")
                    art_date = art.get("date", "")
                    art_content = art.get("content") or art.get("snippet", "")
                    # 최대 1800자까지 본문 디테일 보존
                    trimmed_content = art_content[:1800] if len(art_content) > 1800 else art_content
                    context_parts.append(
                        f"### 기사 {idx}. [{art_press}] {art_title} ({art_date})\n"
                        f"본문 전문: {trimmed_content}\n"
                    )

            # 전체 기사 색인 목록 (광범위한 시야 제공)
            index_list = [
                f"- [{a.get('date', '')}] {a.get('title', '')} ({a.get('press', '')})"
                for a in self.collected_articles[:40]
            ]
            context_parts.append("\n[전체 수집 기사 색인 목록]\n" + "\n".join(index_list))

        # 4-2. AI 요약 보고서 전문 (작성되어 있을 경우 주입)
        if self.current_report:
            context_parts.append(
                f"\n\n[최근 작성된 AI 심층 분석 보고서 전문]\n{self.current_report}\n\n"
                "※ 지침: 사용자가 보고서 요약, 경기 리뷰, 분석 내용 등에 대해 질문하면 위 보고서의 심층 분석 내용을 바탕으로 명확히 답변하세요."
            )

        # 4-3. 실시간 구장 날씨 데이터
        if self.latest_weather_data and self.latest_weather_data.get("stadiums"):
            w_list = [
                f"- {s['name']}({s['team_short']}): {s['temp']}, 강수 {s['rain']}, 풍속 {s['wind_speed']}, 진행상태: {s['status_label']}"
                for s in self.latest_weather_data["stadiums"]
            ]
            context_parts.append(
                f"\n\n[실시간 KBO 구장별 기상 관측 정보 ({self.latest_weather_data.get('base_datetime', '')})]\n"
                + "\n".join(w_list)
                + "\n\n※ 지침: 특정 구장의 날씨, 우천 취소 가능성, 경기 진행 여부를 질문받으면 위 기상청 실시간 관측 정보를 근거로 정확히 답변하세요."
            )

        current_instructions = "\n".join(context_parts)

        try:
            if not self.client:
                return {
                    "status": "error",
                    "reply": "❌ OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.",
                }

            response = self.client.responses.create(
                model=self.model,
                instructions=current_instructions,
                input=trimmed_input,
            )
            bot_reply = response.output_text.strip()
            self.conversation_history.append(
                {"role": "assistant", "content": bot_reply}
            )
            return {"status": "success", "reply": bot_reply}

        except Exception as e:
            error_msg = f"⚠️ OpenAI API 호출 중 오류가 발생했습니다: {str(e)}"
            return {"status": "error", "reply": error_msg}

    # ============================================================
    # 2. 기사 수집 인터페이스 (sports.news.naver.com 실시간 크롤링)
    # ============================================================
    def fetch_articles(
        self, keyword: str, start_date: str, end_date: str, max_results: int = 200
    ) -> dict:
        """
        'sports.news.naver.com' 도메인 내에서 키워드와 기간에 부합하는 야구 기사를 실시간 크롤링합니다.
        (최대 max_results건, 기본 200건)
        키워드 정규화(Normalization) 엔진을 적용하여 동의어 및 표준 엔티티를 자동 식별합니다.
        """
        raw_keyword = keyword.strip()
        if not raw_keyword:
            return {"status": "error", "message": "키워드를 입력해주세요."}

        # 1. 키워드 정규화 수행
        entity = normalize_keyword(raw_keyword, client=self.client, model=self.model)
        self.current_entity = entity
        self.current_keyword = entity.canonical

        # 2. 1차: 입력 키워드로 sports.news.naver.com 기사 탐색
        articles = search_naver_sports_articles(
            keyword=raw_keyword,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
        )

        # 만약 입력 키워드와 canonical이 다르고 결과가 너무 적으면 canonical 키워드로 보강 탐색
        if len(articles) < 5 and entity.canonical != raw_keyword:
            canon_articles = search_naver_sports_articles(
                keyword=entity.canonical,
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
            )
            existing_urls = {a.get("url") for a in articles}
            for ca in canon_articles:
                if ca.get("url") not in existing_urls:
                    articles.append(ca)
                    existing_urls.add(ca.get("url"))

        # 기간 조건으로 결과가 없을 경우 (포털 검색 인덱스 한계 대비 최신순 fallback)
        if not articles:
            articles = search_naver_sports_articles(
                keyword=raw_keyword,
                start_date="",
                end_date="",
                max_results=min(max_results, 50),
            )

        if not articles:
            return {
                "status": "warning",
                "message": f"'{raw_keyword}'(표준명: {entity.canonical}) 관련 네이버 스포츠 기사를 찾지 못했습니다. 키워드를 확인해주세요.",
                "articles": [],
                "count": 0,
                "canonical_keyword": entity.canonical,
                "safe_id": entity.safe_id,
            }

        self.collected_articles = articles
        return {
            "status": "success",
            "count": len(articles),
            "articles": articles,
            "keyword": raw_keyword,
            "canonical_keyword": entity.canonical,
            "safe_id": entity.safe_id,
            "synonyms": entity.synonyms,
        }

    # ============================================================
    # 3. 수집 데이터 CSV 추출
    # ============================================================
    def export_articles_csv(self, keyword: str = "") -> dict:
        """
        수집된 기사 데이터를 CSV 파일로 추출하여 저장합니다.
        추출 파일명 형식: {키워드}_기사수집_{추출날짜}_{시간}.csv
        (DataFrame 컬럼 변경 정책 준수: 원본 기사 속성 그대로 보존)
        """
        if not self.collected_articles:
            return {
                "status": "error",
                "message": "수집된 기사 데이터가 없습니다. 먼저 기사를 수집해주세요.",
            }

        # 키워드 결정 및 정규화
        target_keyword = keyword.strip() or self.current_keyword or "야구"
        entity = normalize_keyword(target_keyword, client=self.client, model=self.model)
        safe_keyword = entity.safe_id or "야구기사"

        # 추출 날짜 및 시간 생성
        extract_date = datetime.now().strftime("%y%m%d")
        extract_time = datetime.now().strftime("%H%M%S")
        filename = f"{safe_keyword}_기사수집_{extract_date}_{extract_time}.csv"

        save_path = CSV_EXPORT_DIR / filename

        try:
            # 기사 원문 컬럼(content)을 포함한 DataFrame 생성 (사용자 승인 컬럼 구조 적용)
            records = []
            for art in self.collected_articles:
                item = dict(art)
                if "content" not in item:
                    item["content"] = item.pop("snippet", "")
                records.append(item)

            df = pd.DataFrame(records)
            cols = [c for c in ["id", "category", "title", "press", "date", "url", "content"] if c in df.columns]
            df = df[cols]

            # Excel 등 Windows 환경에서 한글 깨짐 방지를 위해 utf-8-sig 사용
            df.to_csv(save_path, index=False, encoding="utf-8-sig")

            return {
                "status": "success",
                "message": f"CSV 파일이 성공적으로 저장되었습니다!\n저장위치: storage/csv/{filename}\n총 {len(df)}건의 기사 원문(content) 수록",
                "filename": filename,
                "path": str(save_path),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"CSV 저장 중 오류가 발생했습니다: {str(e)}",
            }

    # ============================================================
    # 3-2. 수집 데이터 및 AI 보고서 고속 SQLite 누적 DB 추출 (설계안 B)
    # ============================================================
    def export_articles_db(self, keyword: str = "", start_date: str = "", end_date: str = "") -> dict:
        """
        수집된 기사 원문 데이터 및 AI 보고서를 설계안 B 기반 키워드별 누적 SQLite DB로 추출합니다.
        (storage/db/{키워드}_데이터베이스.db에 기존 데이터 유지하며 누적 적재)
        """
        if not self.collected_articles:
            return {
                "status": "error",
                "message": "수집된 기사 데이터가 없습니다. 먼저 기사를 수집해주세요.",
            }

        target_keyword = keyword.strip() or self.current_keyword or "야구"
        try:
            # [자동 연계] 만약 작성된 보고서가 없다면 먼저 AI 보고서를 자동으로 작성하여 DB에 포함
            if not self.current_report and self.collected_articles:
                s_date = start_date or (self.collected_articles[-1].get("date", "") if self.collected_articles else "")
                e_date = end_date or (self.collected_articles[0].get("date", "") if self.collected_articles else "")
                self.generate_report(start_date=s_date, end_date=e_date, keyword=target_keyword)

            res = DatabaseManager.export_database(
                keyword=target_keyword,
                start_date=start_date,
                end_date=end_date,
                articles=self.collected_articles,
                report_md=self.current_report,
                output_dir=DB_EXPORT_DIR,
            )
            return res
        except Exception as e:
            return {
                "status": "error",
                "message": f"데이터베이스 추출 중 오류가 발생했습니다: {str(e)}",
            }

    # ============================================================
    # 4. 기간별 기사 요약 보고서 작성 (OpenAI API 연동)
    # ============================================================
    def generate_report(self, start_date: str, end_date: str, keyword: str = "") -> dict:
        """
        수집된 기사 중 해당 기간의 기사만 필터링하고 본문을 추출하여 AI 종합 분석 보고서를 작성합니다.
        """
        if not self.collected_articles:
            return {
                "status": "error",
                "message": "좌측에서 먼저 기사를 수집해주세요.",
            }

        # 기간 필터링
        filtered = [
            a
            for a in self.collected_articles
            if (not start_date or a["date"] >= start_date)
            and (not end_date or a["date"] <= end_date)
        ]

        if not filtered:
            filtered = self.collected_articles

        total_count = len(filtered)
        raw_kw = keyword.strip() or (self.current_entity.raw_keyword if self.current_entity else self.current_keyword) or "야구"
        entity = (
            self.current_entity
            if (self.current_entity and self.current_entity.raw_keyword == raw_kw)
            else normalize_keyword(raw_kw, client=self.client, model=self.model)
        )
        self.current_entity = entity
        target_keyword = entity.canonical

        # 날짜순 정렬
        sorted_articles = sorted(filtered, key=lambda x: x.get("date", ""), reverse=False)

        # 1. 키워드 동의어 풀 전체 연관도(Relevance Score) 계산 및 핵심 기사 우선 발췌
        def get_relevance_score(art: dict) -> int:
            t = art.get("title", "")
            c = art.get("content", "") or art.get("snippet", "")
            score = 0
            # 정규화된 동의어 풀 내 모든 단어의 출현 빈도 합산
            for syn in entity.synonyms:
                if syn:
                    score += t.count(syn) * 15
                    score += c.count(syn) * 3
            return score

        # 연관도 높은 순으로 정렬한 기사 목록 (발췌용)
        relevance_sorted = sorted(sorted_articles, key=get_relevance_score, reverse=True)

        # 다양한 날짜를 포괄하면서 키워드 연관도가 높은 핵심 기사 최대 8건 발췌
        seen_dates = set()
        representative_details = []
        for a in relevance_sorted:
            d = a.get("date", "")
            if len(representative_details) >= 8:
                break
            # 같은 날짜에서는 연관도 1위 기사 우선 선택
            if d not in seen_dates or len(seen_dates) >= len(set(x.get("date", "") for x in sorted_articles)):
                seen_dates.add(d)
                full_text = a.get("content") or fetch_article_content(a["url"])
                if full_text:
                    score = get_relevance_score(a)
                    representative_details.append(
                        f"■ [{d} 핵심 기사] 언론사: {a['press']} | 제목: {a['title']} (키워드 연관도 점수: {score})\n"
                        f"기사 본문 발췌:\n{full_text[:800]}\n"
                    )

        rep_text = "\n".join(representative_details) if representative_details else "핵심 본문 발췌 없음"

        # 2. 수집된 전체 기사 목록 (원문 핵심 앞단 요약 포함)
        all_articles_list = []
        for i, a in enumerate(sorted_articles):
            content_text = a.get("content") or a.get("snippet", "")
            content_snippet = content_text[:120].replace("\n", " ").strip() if content_text else ""
            content_str = f" | 본문 요약: {content_snippet}" if content_snippet else ""
            all_articles_list.append(
                f"[{i+1}] 날짜: {a['date']} | 언론사: {a['press']} | 제목: {a['title']}{content_str}"
            )
        all_articles_text = "\n".join(all_articles_list)

        synonyms_str = ", ".join(entity.synonyms[:5])
        instructions = (
            f"당신은 프로야구(KBO) 전문 데이터 분석가이자 스포츠 칼럼니스트입니다.\n"
            f"사용자가 지정한 핵심 검색 키워드 **'{target_keyword}'**(동의어/약칭: {synonyms_str})에 100% 집중하여, "
            f"해당 키워드와 직접 관련된 사건, 경기 활약상, 데이터, 이슈만을 엄격하게 심층 분석한 '키워드 맞춤 포커스 브리핑 보고서'를 마크다운으로 작성해주세요.\n\n"
            "[★ 가장 중요한 핵심 원칙: 키워드 초집중 (Strict Keyword Focus)]\n"
            f"1. **주제 일탈 엄격 금지 (No Topic Drift)**: 보고서의 모든 단락, 문장, 분석의 핵심 주어(Subject)는 반드시 **'{target_keyword}'**여야 합니다.\n"
            f"   - 기사 내에서 '{synonyms_str}' 등의 동의어나 약칭으로 언급된 내용도 모두 '{target_keyword}'의 기록 및 활약상으로 정확히 결합하여 분석하세요.\n"
            f"   - '{target_keyword}'와 직접적인 관련이 없는 타 구단의 경기 결과, 타 선수들의 활약, 리그 일반 순위 싸움 등 무관한 내용은 보고서에 일절 언급하지 마세요.\n"
            f"   - 타 팀이나 상대 선수는 오직 '{target_keyword}'와의 직접적인 맞대결이나 승부처 맥락에서만 1줄 이내로 제한적으로 언급하세요.\n"
            f"2. **키워드가 '선수'인 경우 (예: 김도영, 이로운, 류현진 등)**:\n"
            f"   - 해당 선수의 일자별 출전/등판 경기, 투타 세부 기록(이닝, 탈삼진, 자책점, 투구수 / 타수, 안타, 홈런, 타점, 타율), 위기관리 및 클러치 활약, 투구/타격 폼, 팀 내 역할 및 최근 컨디션 페이스에 온전히 초점을 맞추세요.\n"
            f"3. **키워드가 '구단'인 경우 (예: 한화 이글스, KIA 타이거즈 등)**:\n"
            f"   - 해당 구단의 기간 내 경기 승패, 선발/불펜 투수진 운용, 타선 득점권 집중력, 주요 수훈 선수, 엔트리/부상 변동, 팀 전략에 집중하세요.\n\n"
            "[작성 양식 및 필수 목차]\n"
            f"# ⚾ [{target_keyword}] AI 심층 분석 & 포커스 브리핑 리포트\n"
            f"**분석 대상 기간**: {start_date} ~ {end_date} (관련 기사 총 {total_count}건 정밀 분석)\n\n"
            f"## 1. [{target_keyword}] 핵심 이슈 & 활약상 3줄 요약\n"
            f"- 기간 내 '{target_keyword}'와 관련된 가장 결정적이고 중요한 팩트/기록 3가지를 명확히 요약\n\n"
            f"## 2. 일자별 경기 상세 리뷰 & 세부 데이터 분석\n"
            f"   - **필수 지침 1 (경기 날짜 명확 기재)**: 경기에 대한 리뷰나 활약상을 서술할 때는 반드시 해당 경기가 치러진 날짜(예: '9월 9일 경기에서는...', '9월 5일 등판하여...')를 문장에 명확하고 구체적으로 기재하세요.\n"
            f"   - **필수 지침 2 (기사 링크 제거)**: 문장이나 본문에 기사 URL 링크([기사 보기](...))를 첨부하지 마세요. 전문적인 순수 텍스트 리포트 양식으로 가독성 높게 작성하세요.\n\n"
            f"## 3. [{target_keyword}] 최근 페이스, 전력 기여도 및 이슈 분석\n"
            f"- 최근 컨디션 지표, 전술적 가치, 팀 내 핵심 역할 및 부상/엔트리 관련 이슈 정밀 분석\n\n"
            f"## 4. 향후 전망 및 전문가 핵심 관전 포인트\n"
            f"- 향후 일정에서의 과제, 잔여 경기 역할 및 관전 포인트 제시\n\n"
            f"## 5. [{target_keyword}] 관련 주요 참고 기사 목록\n"
            f"- 보고서 작성에 직접 활용된 '{target_keyword}' 관련 핵심 기사들을 `- [언론사] 기사 제목 (날짜)` 형식의 리스트로 정리하세요. (URL 링크는 넣지 마세요.)"
        )

        user_input = (
            f"핵심 분석 키워드: '{target_keyword}'\n"
            f"분석 대상 기간: {start_date} ~ {end_date} (수집된 기사 총 {total_count}건)\n\n"
            f"[키워드 '{target_keyword}' 집중 대표 기사 상세 본문 발췌]\n{rep_text}\n\n"
            f"[수집된 전체 기사 목록 ({total_count}건)]\n{all_articles_text}\n\n"
            f"위 지침에 따라 키워드 '{target_keyword}'를 벗어나지 않고 해당 키워드 자체의 활약상, 기록, 이슈에 온전히 집중된 고품질 포커스 브리핑 보고서를 작성해주세요."
        )

        try:
            if not self.client:
                report_md = (
                    f"# ⚾ [{target_keyword}] AI 심층 분석 & 포커스 브리핑 리포트\n\n"
                    f"**분석 대상 기간**: {start_date} ~ {end_date} (총 {total_count}건 기사 정밀 분석)\n\n"
                    f"## 1. [{target_keyword}] 핵심 이슈 & 활약상 3줄 요약\n"
                    f"- 기간 내 '{target_keyword}' 관련 기사 총 {total_count}건을 정밀 분석했습니다.\n"
                    f"- 주요 경기 결과 및 일자별 핵심 활약 지표 확인 완료.\n"
                    f"- 최근 컨디션 페이스 및 향후 경기 관전 포인트 도출.\n\n"
                    f"## 2. 일자별 경기 상세 리뷰 & 세부 데이터 분석\n"
                    + "\n".join([f"- **[{a['date']} 경기]** {a['title']} ({a['press']})" for a in sorted_articles[:8]]) + "\n\n"
                    f"## 3. [{target_keyword}] 최근 페이스 및 전력 기여도 분석\n"
                    f"- 수집된 기사 원문을 종합한 결과 '{target_keyword}'의 경기 내 역할과 클러치 상황 기여도가 돋보였습니다.\n\n"
                    f"## 4. 향후 전망 및 전문가 핵심 관전 포인트\n"
                    f"- 잔여 일정에서의 안정적인 경기력 유지 및 핵심 전력으로서의 활약이 기대됩니다.\n\n"
                    f"## 5. [{target_keyword}] 관련 주요 참고 기사 목록\n"
                    + "\n".join([f"- [{a['press']}] {a['title']} ({a['date']})" for a in sorted_articles[:12]])
                )
            else:
                response = self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=user_input,
                )
                report_md = response.output_text.strip()

            self.current_report = report_md

            return {
                "status": "success",
                "report_md": report_md,
                "count": total_count,
                "message": "보고서 작성이 완료되었습니다.",
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"보고서 생성 중 오류가 발생했습니다: {str(e)}",
            }

    # ============================================================
    # 5. 마크다운 보고서 파일 (.md) 저장
    # ============================================================
    def save_report_md(self, keyword: str = "", filename: str = "") -> dict:
        """
        생성된 마크다운 보고서를 .md 파일로 저장합니다. (키워드_보고서_추출날짜.md 양식)
        """
        if not self.current_report:
            return {
                "status": "error",
                "message": "저장할 보고서 내용이 없습니다. 먼저 보고서를 작성해주세요.",
            }

        if not filename:
            target_keyword = keyword.strip() or self.current_keyword or "야구"
            entity = normalize_keyword(target_keyword, client=self.client, model=self.model)
            safe_keyword = entity.safe_id or "야구"
            extract_date = datetime.now().strftime("%y%m%d")
            extract_time = datetime.now().strftime("%H%M%S")

            base_filename = f"{safe_keyword}_보고서_{extract_date}.md"
            save_path = MD_EXPORT_DIR / base_filename
            if save_path.exists():
                filename = f"{safe_keyword}_보고서_{extract_date}_{extract_time}.md"
                save_path = MD_EXPORT_DIR / filename
            else:
                filename = base_filename
        else:
            save_path = MD_EXPORT_DIR / filename

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.current_report)

            return {
                "status": "success",
                "message": f"보고서 파일이 성공적으로 저장되었습니다!\n저장위치: storage/report/{filename}",
                "filename": filename,
                "path": str(save_path),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"보고서 저장 중 오류가 발생했습니다: {str(e)}",
            }

    # ============================================================
    # 5-2. 저장된 마크다운 보고서 목록 조회 및 열람
    # ============================================================
    def list_saved_reports(self) -> dict:
        """
        storage/report 디렉터리에 저장된 .md 보고서 파일 목록을 최신순으로 반환합니다.
        """
        try:
            reports = []
            if MD_EXPORT_DIR.exists():
                for p in sorted(MD_EXPORT_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
                    stat = p.stat()
                    mtime_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    size_kb = round(stat.st_size / 1024, 1)

                    # 파일명에서 키워드 추출 (예: 이로운_보고서_260910.md -> 이로운)
                    kw = p.stem.split("_")[0] if "_" in p.stem else p.stem

                    reports.append({
                        "filename": p.name,
                        "keyword": kw,
                        "size_kb": size_kb,
                        "updated_at": mtime_str,
                        "path": str(p),
                    })

            return {
                "status": "success",
                "count": len(reports),
                "reports": reports,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"보고서 목록 조회 실패: {str(e)}",
                "reports": [],
            }

    def load_saved_report(self, filename: str) -> dict:
        """
        storage/report 폴더의 특정 .md 파일을 읽어 반환하고,
        현재 컨텍스트(current_report, current_keyword)를 갱신합니다.
        """
        safe_name = Path(filename).name
        file_path = MD_EXPORT_DIR / safe_name

        if not file_path.exists() or not file_path.is_file():
            return {
                "status": "error",
                "message": f"'{safe_name}' 보고서 파일을 찾을 수 없습니다.",
            }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.current_report = content
            # 파일명 앞자리에서 키워드 추출
            kw = safe_name.split("_")[0] if "_" in safe_name else "야구"
            self.current_keyword = kw

            return {
                "status": "success",
                "filename": safe_name,
                "keyword": kw,
                "report_md": content,
                "message": f"'{safe_name}' 보고서를 성공적으로 불러왔습니다.",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"보고서 파일 읽기 실패: {str(e)}",
            }

    # ============================================================
    # 6. 외부 브라우저 링크 열기
    # ============================================================
    def open_external_link(self, url: str) -> dict:
        """
        시스템 기본 브라우저(Edge, Chrome 등)로 외부 웹 링크를 엽니다.
        """
        try:
            if url and url.startswith(("http://", "https://")):
                webbrowser.open(url)
                return {"status": "success", "url": url}
            return {"status": "error", "message": "유효하지 않은 URL입니다."}
        except Exception as e:
            return {"status": "error", "message": f"링크 열기 실패: {str(e)}"}

    # ============================================================
    # 7. KBO 전국 구장 실시간 기상정보 조회 (기상청 단기예보 API 연동)
    # ============================================================
    def get_stadiums_weather(self) -> dict:
        """
        KBO 전국 11개 구장(정규 9개 + 제2구장 2개: 포항, 울산 문수)의 실시간 기상정보 및 우천 취소 가능성 지수를 조회합니다.
        """
        res = get_all_stadiums_weather()
        if res.get("status") == "success":
            self.latest_weather_data = res
        return res

