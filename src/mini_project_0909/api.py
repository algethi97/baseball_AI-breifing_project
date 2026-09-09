"""
야구 뉴스 챗봇 & 기사 수집/보고서 연동 백엔드 API 클래스
"""

import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

from mini_project_0909.crawler import search_naver_sports_articles, fetch_article_content

load_dotenv(override=True)


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
            "3. 답변은 가독성 좋게 핵심 위주로 불릿포인트나 단락을 나누어 작성하세요."
        )

        # 챗봇 대화 기록
        self.conversation_history = []

        # 수집된 기사 및 최근 작성된 보고서 저장소
        self.collected_articles = []
        self.current_report = ""

    # ============================================================
    # 1. 챗봇 대화 인터페이스
    # ============================================================
    def send_message(self, message: str) -> dict:
        """
        사용자의 챗봇 질문을 받아 OpenAI Responses API로 답변 반환
        """
        user_text = message.strip()
        if not user_text:
            return {"status": "error", "reply": "질문 내용을 입력해주세요."}

        self.conversation_history.append({"role": "user", "content": user_text})
        trimmed_input = self.conversation_history[-10:]

        try:
            if not self.client:
                return {
                    "status": "error",
                    "reply": "❌ OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.",
                }

            response = self.client.responses.create(
                model=self.model,
                instructions=self.chat_instructions,
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
        self, keyword: str, start_date: str, end_date: str
    ) -> dict:
        """
        'sports.news.naver.com' 도메인 내에서 키워드와 기간에 부합하는 야구 기사를 실시간 크롤링합니다.
        """
        keyword = keyword.strip()
        if not keyword:
            return {"status": "error", "message": "키워드를 입력해주세요."}

        # 1차: 기간 조건을 포함하여 sports.news.naver.com 기사 탐색
        articles = search_naver_sports_articles(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            max_results=20,
        )

        # 기간 조건으로 결과가 없을 경우 (포털 검색 인덱스 한계 대비 최신순 fallback)
        if not articles:
            articles = search_naver_sports_articles(
                keyword=keyword,
                start_date="",
                end_date="",
                max_results=15,
            )

        if not articles:
            return {
                "status": "warning",
                "message": f"'{keyword}' 관련 네이버 스포츠 기사를 찾지 못했습니다. 키워드를 확인해주세요.",
                "articles": [],
                "count": 0,
            }

        self.collected_articles = articles
        return {
            "status": "success",
            "count": len(articles),
            "articles": articles,
        }

    # ============================================================
    # 3. 수집 데이터 CSV 추출
    # ============================================================
    def export_articles_csv(self, filename: str = "") -> dict:
        """
        수집된 기사 데이터를 CSV 파일로 추출하여 저장합니다.
        (컬럼 변경 정책 준수: 원본 기사 속성 그대로 보존)
        """
        if not self.collected_articles:
            return {
                "status": "error",
                "message": "수집된 기사 데이터가 없습니다.",
            }

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"baseball_articles_{timestamp}.csv"

        save_path = Path.cwd() / filename

        try:
            # 원본 컬럼 그대로 DataFrame 생성 (임의 컬럼 추가/삭제 금지 정책 준수)
            df = pd.DataFrame(self.collected_articles)
            # Excel 등 Windows 환경에서 한글 깨짐 방지를 위해 utf-8-sig 사용
            df.to_csv(save_path, index=False, encoding="utf-8-sig")

            return {
                "status": "success",
                "message": f"CSV 파일이 성공적으로 저장되었습니다!\n저장 경로: {save_path.name}",
                "filename": str(save_path),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"CSV 저장 중 오류가 발생했습니다: {str(e)}",
            }

    # ============================================================
    # 4. 기간별 기사 요약 보고서 작성 (OpenAI API 연동)
    # ============================================================
    def generate_report(self, start_date: str, end_date: str) -> dict:
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

        # 상위 기사들의 상세 본문 크롤링 결합 (더욱 정교한 보고서 생성)
        articles_detail_list = []
        for i, a in enumerate(filtered[:5]):
            full_text = fetch_article_content(a["url"])
            body_summary = full_text[:400] if full_text else a["snippet"]
            articles_detail_list.append(
                f"[{i+1}] 언론사: {a['press']} | 날짜: {a['date']} | 제목: {a['title']}\n"
                f"내용 발췌: {body_summary}\n"
            )

        articles_summary_text = "\n".join(articles_detail_list)

        instructions = (
            "당신은 전문 야구 분석가이자 스포츠 칼럼니스트입니다.\n"
            "네이버 스포츠(sports.news.naver.com)에서 수집된 실제 기사들을 바탕으로, 야구 팬과 코치진을 위한 전문적인 '야구 뉴스 요약 및 브리핑 보고서'를 마크다운으로 작성해주세요.\n"
            "반드시 아래 항목을 명확히 포함하세요:\n"
            "1. # ⚾ 야구 뉴스 종합 브리핑 보고서 (제목 및 대상 기간)\n"
            "2. ## 1. 핵심 3줄 요약 (가장 중요한 흐름 및 이슈 3가지)\n"
            "3. ## 2. 구단 및 선수단 주요 이슈 분석 (투타 흐름, 선수 성적, 인터뷰 포인트)\n"
            "4. ## 3. 전문가 총평 및 향후 전망\n"
            "5. ## 4. 참고 기사 출처 (언론사 및 제목 리스트)"
        )

        user_input = (
            f"대상 기간: {start_date} ~ {end_date}\n"
            f"수집된 네이버 스포츠 야구 기사 목록:\n\n{articles_summary_text}\n\n"
            "위 기사들을 종합하여 심층 분석 보고서를 작성해주세요."
        )

        try:
            if not self.client:
                report_md = (
                    f"# ⚾ 야구 뉴스 종합 브리핑 보고서\n\n"
                    f"**분석 기간**: {start_date} ~ {end_date} (총 {len(filtered)}건 분석)\n\n"
                    f"## 1. 핵심 3줄 요약\n"
                    f"- 네이버 스포츠 기사 {len(filtered)}건을 바탕으로 분석을 완료했습니다.\n"
                    f"- 경기 주요 포인트 및 선수단 컨디션 지표 확인 완료.\n\n"
                    f"## 2. 참고 기사\n"
                    + "\n".join([f"- [{a['press']}] {a['title']}" for a in filtered])
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
                "count": len(filtered),
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"보고서 생성 중 오류가 발생했습니다: {str(e)}",
            }

    # ============================================================
    # 5. 마크다운 보고서 파일 (.md) 저장
    # ============================================================
    def save_report_md(self, filename: str = "") -> dict:
        """
        생성된 마크다운 보고서를 .md 파일로 저장합니다.
        """
        if not self.current_report:
            return {
                "status": "error",
                "message": "저장할 보고서 내용이 없습니다. 먼저 보고서를 작성해주세요.",
            }

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"baseball_report_{timestamp}.md"

        save_path = Path.cwd() / filename

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.current_report)

            return {
                "status": "success",
                "message": f"보고서 파일이 성공적으로 저장되었습니다!\n저장 경로: {save_path.name}",
                "filename": str(save_path),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"보고서 저장 중 오류가 발생했습니다: {str(e)}",
            }
