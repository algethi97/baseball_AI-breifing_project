"""
야구 뉴스 브리핑 AI 챗봇 pywebview 데스크톱 애플리케이션 진입점
"""

import webview
from mini_project_0909.templates import HTML_CODE
from mini_project_0909.api import BaseballBotAPI

def start_chatbot():
    """
    야구 뉴스 AI 챗봇 창을 띄웁니다.
    """
    api = BaseballBotAPI()
    
    # 웹뷰 윈도우 생성
    window = webview.create_window(
        title="야구 뉴스 브리핑 AI 챗봇",
        html=HTML_CODE,
        js_api=api,
        width=920,
        height=720,
        resizable=True,
        min_size=(640, 480)
    )
    
    # 창 실행 (F12 개발자 도구 활성화)
    webview.start(debug=True)

if __name__ == "__main__":
    start_chatbot()

