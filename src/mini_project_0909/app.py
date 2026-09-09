"""
야구 뉴스 브리핑 & 분석 시스템 pywebview 데스크톱 애플리케이션 진입점
"""

from pathlib import Path
import webview
from mini_project_0909.api import BaseballBotAPI

# UI 파일 경로 (ui/index.html)
CURRENT_DIR = Path(__file__).resolve().parent
UI_HTML_PATH = CURRENT_DIR / "ui" / "index.html"


def start_chatbot():
    """
    야구 뉴스 AI 챗봇 및 기사 분석 시스템 데스크톱 창을 띄웁니다.
    (src/mini_project_0909/ui/index.html 로드)
    """
    api = BaseballBotAPI()

    # 웹뷰 윈도우 생성 (분리된 HTML/CSS/JS 파일 로드)
    window = webview.create_window(
        title="⚾ 야구 뉴스 브리핑 & 분석 시스템",
        url=str(UI_HTML_PATH),
        js_api=api,
        width=1180,
        height=820,
        resizable=True,
        min_size=(800, 600),
    )

    # 데스크톱 창 실행 (DevTools 팝업 비활성화)
    webview.start(debug=False)


if __name__ == "__main__":
    start_chatbot()
