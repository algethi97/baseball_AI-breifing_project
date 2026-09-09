"""
야구 뉴스 챗봇 & 기사 수집/보고서 연동 백엔드 API 클래스
"""

import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

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
            "2. 상단 탭에서 '기사 수집 & 요약 보고서' 기능을 통해 기사 크롤링 및 CSV/MD 저장을 지원함을 안내합니다.\n"
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
    # 2. 기사 수집 인터페이스 (외형 및 프로토타입)
    # ============================================================
    def fetch_articles(
        self, keyword: str, start_date: str, end_date: str
    ) -> dict:
        """
        키워드와 기간을 전달받아 연관된 야구 뉴스 기사를 수집합니다.
        (현재 외형 및 프로토타입 단계로, 추후 네이버 뉴스 크롤러 모듈과 직접 연결됩니다)
        """
        keyword = keyword.strip()
        if not keyword:
            return {"status": "error", "message": "키워드를 입력해주세요."}

        # [프로토타입 데이터 생성]
        # 향후 requests, BeautifulSoup, selenium 또는 Naver News API 연동으로 교체됩니다.
        sample_press_list = [
            "스포츠조선",
            "OSEN",
            "일간스포츠",
            "MK스포츠",
            "스타뉴스",
        ]
        articles = [
            {
                "id": 1,
                "title": f"[KBO 기획] '{keyword}' 후반기 승부처, 전문가들이 꼽은 핵심 변수는?",
                "press": sample_press_list[0],
                "date": end_date or datetime.now().strftime("%Y-%m-%d"),
                "url": "https://sports.news.naver.com/kbaseball/",
                "snippet": f"{keyword} 관련 최근 경기 흐름과 감독의 경기 후 인터뷰를 바탕으로 팀의 전략적 방향성을 분석했다.",
            },
            {
                "id": 2,
                "title": f"'{keyword}' 뜨거운 타격감 이어가나... 중심 타선 득점권 집중력 주목",
                "press": sample_press_list[1],
                "date": end_date or datetime.now().strftime("%Y-%m-%d"),
                "url": "https://sports.news.naver.com/kbaseball/",
                "snippet": f"득점권 찬스에서의 결정력이 승부를 가르고 있으며, {keyword}에 대한 팬들의 관심이 집중되고 있다.",
            },
            {
                "id": 3,
                "title": f"마운드 재정비 나선 '{keyword}', 불펜진 투구수 관리와 필승조 점검",
                "press": sample_press_list[2],
                "date": start_date or datetime.now().strftime("%Y-%m-%d"),
                "url": "https://sports.news.naver.com/kbaseball/",
                "snippet": "선발 로테이션의 안정과 불펜 계투진의 연투 방지가 향후 연전 일정의 최대 승부처가 될 전망이다.",
            },
            {
                "id": 4,
                "title": f"[현장 리포트] '{keyword}' 부상 복귀 선수단 훈련 합류... 엔트리 강화 예고",
                "press": sample_press_list[3],
                "date": start_date or datetime.now().strftime("%Y-%m-%d"),
                "url": "https://sports.news.naver.com/kbaseball/",
                "snippet": "코칭스태프는 주전 선수들의 컨디션 회복 상태를 면밀히 점검하며 1군 복귀 시점을 조율 중이라고 전했다.",
            },
        ]

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
        수집된 기사 중 해당 기간의 기사만 필터링하여 AI 종합 분석 보고서를 작성합니다.
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
            # 필터 조건에 맞는 기사가 없을 경우 전체 기사 사용 안내
            filtered = self.collected_articles

        # 기사 내용 요약 프롬프트 조립
        articles_summary_text = "\n".join(
            [
                f"- [{a['press']}] {a['title']} ({a['date']}): {a['snippet']}"
                for a in filtered
            ]
        )

        instructions = (
            "당신은 전문 야구 분석가이자 스포츠 칼럼니스트입니다.\n"
            "주어진 야구 뉴스 기사 목록을 바탕으로, 코치진과 야구 팬들을 위한 구조화된 '야구 뉴스 요약 및 브리핑 보고서'를 마크다운 형식으로 작성해주세요.\n"
            "반드시 아래 항목을 포함해야 합니다:\n"
            "1. # ⚾ 야구 뉴스 종합 브리핑 보고서 (보고서 제목 및 기간)\n"
            "2. ## 1. 핵심 3줄 요약 (가장 중요한 흐름 요약)\n"
            "3. ## 2. 구단 및 선수단 주요 이슈 분석 (투타 흐름, 부상/엔트리, 경기 포인트)\n"
            "4. ## 3. 전문가 총평 및 향후 전망\n"
            "5. ## 4. 참고 기사 목록 (언론사 및 제목 표기)"
        )

        user_input = f"다음은 {start_date}부터 {end_date}까지 수집된 야구 뉴스 기사 목록입니다:\n\n{articles_summary_text}\n\n위 기사들을 종합 분석하여 보고서를 작성해주세요."

        try:
            if not self.client:
                # API 클라이언트가 없을 경우의 프로토타입 템플릿
                report_md = (
                    f"# ⚾ 야구 뉴스 종합 브리핑 보고서\n\n"
                    f"**분석 기간**: {start_date} ~ {end_date} (총 {len(filtered)}건 분석)\n\n"
                    f"## 1. 핵심 3줄 요약\n"
                    f"- 수집된 {len(filtered)}건의 기사를 토대로 주요 경기 및 선수단 동향 분석을 완료했습니다.\n"
                    f"- 득점권 타선의 집중력과 선발/불펜 투수진의 안정세가 향후 경기력의 핵심 요인으로 부각되었습니다.\n"
                    f"- 부상자 복귀와 엔트리 변동에 따른 라인업 최적화가 본격화되고 있습니다.\n\n"
                    f"## 2. 구단 및 선수단 주요 이슈\n"
                    f"- **투수진 운용**: 불펜진 연투 관리 및 필승조의 이닝 소화 능력이 승패를 결정짓는 핵심 지표로 관측됨.\n"
                    f"- **타선 흐름**: 중심 타선의 클러치 능력 향상과 하위 타선의 출루율 보강이 요구됨.\n\n"
                    f"## 3. 전문가 총평 및 향후 전망\n"
                    f"- 후반기 순위 싸움이 치열해지는 만큼, 매 경기 벤치의 작전 수행 능력과 선수단의 컨디션 유지가 중요합니다.\n\n"
                    f"## 4. 참고 기사\n"
                    + "\n".join([f"- [{a['press']}] {a['title']}" for a in filtered])
                )
            else:
                # OpenAI Responses API 호출 (사용자 지정 모델: gpt-5.6-luna)
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
