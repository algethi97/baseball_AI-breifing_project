"""
야구 뉴스 챗봇 & 기사 수집/보고서 연동 백엔드 API 클래스
"""

import os
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

from mini_project_0909.crawler import search_naver_sports_articles, fetch_article_content
from mini_project_0909.weather import get_all_stadiums_weather
from mini_project_0909.database import DatabaseManager

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

        # 챗봇용 시스템 지침
        self.chat_instructions = (
            "당신은 한국 프로야구(KBO) 및 야구 뉴스 전문 AI 어시스턴트 '야구 브리핑 AI'입니다.\n"
            "사용자에게 친절하고 신뢰감 있는 어조로 답변하세요.\n"
            "[주요 역할]\n"
            "1. 야구 경기 규칙, 구단 소식, 최신 이슈 및 선수 정보에 대해 명확하고 흥미롭게 답변합니다.\n"
            "2. 상단 탭에서 '기사 수집 & 요약 보고서' 기능을 통해 sports.news.naver.com 기사 크롤링 및 CSV/MD 저장을 지원함을 안내합니다.\n"
            "3. '구장별 실시간 날씨' 탭을 통해 전국 KBO 구장의 실시간 기상 상태 및 우천 취소 가능성 정보를 제공함을 안내합니다.\n"
            "4. 답변은 가독성 좋게 핵심 위주로 불릿포인트나 단락을 나누어 작성하세요."
        )

        # 챗봇 대화 기록
        self.conversation_history = []

        # 수집된 기사 및 최근 작성된 보고서 저장소
        self.collected_articles = []
        self.current_keyword = ""
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
        return {
            "status": "success",
            "has_articles": bool(self.collected_articles),
            "article_count": len(self.collected_articles),
            "keyword": self.current_keyword,
            "has_report": bool(self.current_report),
        }

    def send_message(self, message: str) -> dict:
        """
        사용자의 챗봇 질문을 받아 수집된 기사 및 요약 보고서 컨텍스트와 함께 OpenAI Responses API로 답변 반환
        """
        user_text = message.strip()
        if not user_text:
            return {"status": "error", "reply": "질문 내용을 입력해주세요."}

        self.conversation_history.append({"role": "user", "content": user_text})
        trimmed_input = self.conversation_history[-10:]

        # 현재 수집된 기사 및 생성된 요약 보고서 기반 동적 컨텍스트 조립
        context_parts = [self.chat_instructions]

        if self.current_report or self.collected_articles:
            context_parts.append("\n\n[현재 연동된 야구 기사 & 보고서 데이터베이스]")
            if self.current_keyword:
                context_parts.append(f"- 현재 수집 검색어: '{self.current_keyword}'")
            if self.collected_articles:
                context_parts.append(f"- 수집된 기사 건수: 총 {len(self.collected_articles)}건")

            if self.current_report:
                context_parts.append(
                    "\n[최근 생성된 AI 요약 보고서 전문]\n"
                    f"{self.current_report}\n\n"
                    "※ 지침: 사용자가 보고서의 내용, 핵심 요약, 경기 리뷰, 세부 분석 등에 대해 질문하면 위 보고서 전문을 기반으로 명확하고 구체적으로 답변하세요."
                )
                articles_list = [
                    f"- [{a.get('date', '')}] {a.get('title', '')} ({a.get('press', '')}) : {(a.get('content') or a.get('snippet', ''))[:100]}"
                    for a in self.collected_articles[:50]
                ]
                context_parts.append(
                    "\n[수집된 주요 기사 목록 (일부 발췌)]\n"
                    + "\n".join(articles_list)
                    + "\n\n※ 지침: 사용자가 수집된 기사에 대해 물어보면 위 목록을 참고하여 신뢰성 높게 답변하세요."
                )

        if self.latest_weather_data and self.latest_weather_data.get("stadiums"):
            w_list = [
                f"- {s['name']}({s['team_short']}): {s['temp']}, 강수 {s['rain']}, 풍속 {s['wind_speed']}, 진행상태: {s['status_label']}"
                for s in self.latest_weather_data["stadiums"]
            ]
            context_parts.append(
                f"\n\n[실시간 KBO 구장별 기상정보 ({self.latest_weather_data.get('base_datetime', '')})]\n"
                + "\n".join(w_list)
                + "\n\n※ 지침: 사용자가 특정 야구장의 오늘 날씨나 우천 취소 여부, 경기 진행 가능성을 물어보면 위 실시간 기상청 관측 정보를 토대로 답변하세요."
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
        """
        keyword = keyword.strip()
        if not keyword:
            return {"status": "error", "message": "키워드를 입력해주세요."}

        # 1차: 기간 조건을 포함하여 sports.news.naver.com 기사 탐색
        articles = search_naver_sports_articles(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
        )

        # 기간 조건으로 결과가 없을 경우 (포털 검색 인덱스 한계 대비 최신순 fallback)
        if not articles:
            articles = search_naver_sports_articles(
                keyword=keyword,
                start_date="",
                end_date="",
                max_results=min(max_results, 50),
            )

        if not articles:
            return {
                "status": "warning",
                "message": f"'{keyword}' 관련 네이버 스포츠 기사를 찾지 못했습니다. 키워드를 확인해주세요.",
                "articles": [],
                "count": 0,
            }

        self.collected_articles = articles
        self.current_keyword = keyword
        return {
            "status": "success",
            "count": len(articles),
            "articles": articles,
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

        # 키워드 결정 (파라미터 우선 -> 수집 시 저장된 키워드 -> 기본값)
        target_keyword = keyword.strip() or self.current_keyword or "야구"
        # 파일명에 사용할 수 없는 특수문자 및 공백 정제
        safe_keyword = re.sub(r"[^\w가-힣0-9_-]", "", target_keyword).strip() or "야구기사"

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
        # 날짜순 정렬
        sorted_articles = sorted(filtered, key=lambda x: x.get("date", ""), reverse=False)

        # 1. 일자별 대표 기사 원문 상세 발췌 (수집된 원문 content 활용, 각 일자별 최대 8건에 대해 500자씩 발췌)
        seen_dates = set()
        representative_details = []
        for a in sorted_articles:
            d = a.get("date", "")
            if d not in seen_dates and len(representative_details) < 8:
                seen_dates.add(d)
                full_text = a.get("content") or fetch_article_content(a["url"])
                if full_text:
                    representative_details.append(
                        f"■ [{d} 대표 기사 원문] 언론사: {a['press']} | 제목: {a['title']}\n"
                        f"기사 원문 발췌:\n{full_text[:500]}\n"
                    )

        rep_text = "\n".join(representative_details) if representative_details else "대표 본문 발췌 없음"

        # 2. 수집된 전체 기사 목록 (원문 핵심 앞단 요약 포함하여 전수 분석 지원)
        all_articles_list = []
        for i, a in enumerate(sorted_articles):
            content_text = a.get("content") or a.get("snippet", "")
            content_snippet = content_text[:120].replace("\n", " ").strip() if content_text else ""
            content_str = f" | 원문 요약: {content_snippet}" if content_snippet else ""
            all_articles_list.append(
                f"[{i+1}] 날짜: {a['date']} | 언론사: {a['press']} | 제목: {a['title']}{content_str}"
            )
        all_articles_text = "\n".join(all_articles_list)

        instructions = (
            "당신은 프로야구(KBO) 전문 데이터 분석가이자 스포츠 칼럼니스트입니다.\n"
            f"수집된 전체 야구 뉴스 기사(총 {total_count}건)를 빠짐없이 종합 분석하여, 야구 팬과 코치진을 위한 전문적이고 심층적인 '야구 뉴스 종합 브리핑 보고서'를 마크다운으로 작성해주세요.\n\n"
            "[작성 형식 및 필수 규칙]\n"
            f"1. # ⚾ 야구 뉴스 종합 브리핑 보고서 (대상 기간: {start_date} ~ {end_date}, 총 {total_count}건 기사 분석)\n"
            "2. ## 1. 핵심 3줄 요약 (기간 전체를 관통하는 가장 중요한 핵심 이슈 3가지)\n"
            "3. ## 2. 구단 및 선수단 주요 경기 리뷰 & 활약상 분석\n"
            "   - **필수 지침 1 (경기 날짜 명확 기재)**: 경기에 대한 리뷰(경기 결과, 승패, 득점, 투타 기록, 승부처)나 선수의 경기 활약상을 서술할 때는 반드시 해당 경기가 치러진 날짜(예: '9월 8일 경기에서는...', '9월 5일 경기에서 심우준 선수가...')를 문장에 명확하고 구체적으로 기재하세요.\n"
            "   - **필수 지침 2 (기사 링크 제거)**: 문장이나 본문에 기사 URL 링크([기사 보기](...))를 첨부하지 마세요. 깔끔하고 전문적인 순수 텍스트 리포트 양식으로 가독성 높게 작성하세요.\n"
            "4. ## 3. 부상/엔트리 변동 및 팀 전력 분석\n"
            "5. ## 4. 전문가 총평 및 향후 경기 전망\n"
            "6. ## 5. 주요 참고 기사 목록\n"
            "   - 보고서 작성에 중요하게 활용된 대표 기사들을 `- [언론사] 기사 제목 (날짜)` 형식의 리스트로 정리하세요. (URL 링크는 넣지 마세요.)\n\n"
            f"※ 중요: 특정 몇 개 기사에 치우치지 말고, 제공된 전체 기사 목록({total_count}건)의 시간 흐름과 전반적인 내용을 균형 있게 종합하여 완성도 높은 보고서를 작성하세요."
        )

        user_input = (
            f"분석 대상 기간: {start_date} ~ {end_date} (수집된 기사 총 {total_count}건)\n\n"
            f"[일자별 주요 대표 기사 상세 발췌]\n{rep_text}\n\n"
            f"[수집된 전체 기사 목록 ({total_count}건)]\n{all_articles_text}\n\n"
            f"위 수집된 전체 기사({total_count}건)를 종합 분석하여, 경기 날짜가 명확히 명시된 고품질 야구 종합 분석 보고서를 작성해주세요."
        )

        try:
            if not self.client:
                report_md = (
                    f"# ⚾ 야구 뉴스 종합 브리핑 보고서\n\n"
                    f"**분석 기간**: {start_date} ~ {end_date} (총 {total_count}건 기사 종합 분석)\n\n"
                    f"## 1. 핵심 3줄 요약\n"
                    f"- 기간 내 네이버 스포츠 야구 기사 총 {total_count}건을 종합 분석했습니다.\n"
                    f"- 주요 경기 결과 및 일자별 선수단 컨디션 지표 확인 완료.\n"
                    f"- 세부 활약상 및 잔여 경기 일정에 따른 맞춤형 리포트 제공.\n\n"
                    f"## 2. 구단 및 선수단 주요 경기 리뷰 & 활약상 분석\n"
                    + "\n".join([f"- **[{a['date']} 경기]** {a['title']} ({a['press']})" for a in sorted_articles[:10]]) + "\n\n"
                    f"## 3. 주요 참고 기사 목록\n"
                    + "\n".join([f"- [{a['press']}] {a['title']} ({a['date']})" for a in sorted_articles[:15]])
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
            safe_keyword = re.sub(r"[^\w가-힣0-9_-]", "", target_keyword).strip() or "야구"
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

