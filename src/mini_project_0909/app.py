"""
야구 뉴스 브리핑 & 분석 시스템 pywebview 데스크톱 애플리케이션 진입점
"""

import webview
from mini_project_0909.templates import HTML_CODE
from mini_project_0909.api import BaseballBotAPI

def start_chatbot():
    """
    야구 뉴스 AI 챗봇 및 기사 분석 시스템 데스크톱 창을 띄웁니다.
    """
    api = BaseballBotAPI()
    
    # 웹뷰 윈도우 생성 (좌우 2분할 뷰에 맞춰 창 크기 확장)
    window = webview.create_window(
        title="⚾ 야구 뉴스 브리핑 & 분석 시스템",
        html=HTML_CODE,
        js_api=api,
        width=1180,
        height=820,
        resizable=True,
        min_size=(800, 600)
    )
    
    # 데스크톱 창 실행 (debug=False로 설정하여 DevTool 창 자동 팝업 방지)
    webview.start(debug=False)

if __name__ == "__main__":
    start_chatbot()
