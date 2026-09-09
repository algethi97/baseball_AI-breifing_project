"""
pywebview JS API 바인딩 클래스
"""

class BaseballBotAPI:
    """
    JavaScript 프론트엔드와 통신하는 백엔드 API 클래스
    """
    def __init__(self):
        # 향후 기사 크롤러, LLM 요약기, CSV 저장기 등의 인스턴스를 여기에 바인딩할 수 있습니다.
        pass

    def send_message(self, message: str) -> dict:
        """
        사용자의 메시지를 받아 야구 챗봇 응답을 반환합니다.
        """
        query = message.strip()
        if not query:
            return {"status": "error", "reply": "질문 내용을 입력해주세요."}

        # [테스트 및 안내 응답 로직]
        # 추후 BeautifulSoup / Selenium 크롤링 및 OpenAI API 요약 함수가 연결될 자리입니다.
        if any(keyword in query for keyword in ["뉴스", "브리핑", "오늘"]):
            reply = (
                "📰 **[야구 뉴스 AI 브리핑 준비 완료]**\n\n"
                "기본 AI 챗봇 뼈대와 pywebview 통신 환경이 성공적으로 구축되었습니다!\n\n"
                "다음 단계에서 연결될 세부 기능:\n"
                "1. **네이버 스포츠 야구 기사 크롤링**: `requests`, `beautifulsoup4`, `selenium` 연동\n"
                "2. **AI 기사 요약 및 리포트**: `openai` API를 이용한 주요 경기·선수 동향 3줄 요약\n"
                "3. **스크랩 데이터 저장**: 날짜, 제목, 기자, 본문 요약, 원문 링크를 `pandas` DataFrame으로 수집 후 CSV 파일로 내보내기"
            )
        elif any(keyword in query for keyword in ["순위", "이슈", "팀"]):
            reply = (
                "🏆 **[구단별 순위 & 이슈 분석 모듈]**\n\n"
                "현재 구단별 경기 일정, 최신 순위 데이터, 주요 부상/엔트리 변동 이슈를 크롤링하여 요약할 수 있도록 API 구조가 대기 중입니다."
            )
        elif any(keyword in query for keyword in ["저장", "csv", "CSV", "스크랩"]):
            reply = (
                "💾 **[기사 스크랩 및 CSV 저장 모듈]**\n\n"
                "수집된 기사 데이터를 Pandas DataFrame으로 변환한 뒤, CSV 파일로 안전하게 저장할 수 있는 함수 스텁이 준비되어 있습니다."
            )
        else:
            reply = (
                f"⚾ 전달받은 질문: '{query}'\n\n"
                "HTML/CSS/JS 및 pywebview 브릿지가 안정적으로 연결되어 정상 동작하고 있습니다!\n"
                "여기에 기사 크롤러와 AI 요약 프롬프트 코드를 순차적으로 추가하시면 완성본 프로그램이 됩니다."
            )

        return {"status": "success", "reply": reply}

    def export_csv(self) -> dict:
        """
        (추후 확장용) 스크랩된 기사 데이터를 CSV로 저장하는 함수
        """
        return {"status": "success", "message": "CSV 저장 기능 준비 중"}

