"""
HTML, CSS, JavaScript 기반 야구 뉴스 챗봇 & 기사 수집/보고서 탭 UI 템플릿
"""

HTML_CODE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>야구 뉴스 브리핑 & 분석 시스템</title>
    <style>
        :root {
            --primary: #0f2b5c;
            --primary-light: #1e3d7a;
            --accent: #e63946;
            --accent-hover: #d62839;
            --bg: #f1f5f9;
            --card-bg: #ffffff;
            --text-dark: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --border-focus: #3b82f6;
            --bot-bubble: #ffffff;
            --user-bubble: #0f2b5c;
            --success: #10b981;
            --tag-bg: #e0f2fe;
            --tag-text: #0369a1;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Pretendard', 'Malgun Gothic', sans-serif;
        }

        body {
            background: var(--bg);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            color: var(--text-dark);
        }

        /* Top Header & Tab Navigation */
        .app-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            color: white;
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 10px rgba(0,0,0,0.12);
            z-index: 100;
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .header-logo {
            font-size: 24px;
            background: rgba(255, 255, 255, 0.15);
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.25);
        }

        .header-title h1 {
            font-size: 1.12rem;
            font-weight: 700;
            letter-spacing: -0.3px;
        }

        .header-title p {
            font-size: 0.76rem;
            color: rgba(255, 255, 255, 0.8);
            margin-top: 2px;
        }

        /* Nav Tabs */
        .tab-nav {
            display: flex;
            background: rgba(0, 0, 0, 0.2);
            padding: 4px;
            border-radius: 12px;
            gap: 4px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: rgba(255, 255, 255, 0.8);
            padding: 8px 16px;
            font-size: 0.88rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .tab-btn:hover {
            color: white;
            background: rgba(255, 255, 255, 0.1);
        }

        .tab-btn.active {
            background: white;
            color: var(--primary);
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }

        /* Content Container */
        .main-content {
            flex: 1;
            position: relative;
            overflow: hidden;
        }

        .tab-panel {
            display: none;
            width: 100%;
            height: 100%;
        }

        .tab-panel.active {
            display: flex;
        }

        /* ============================================================
           TAB 1: AI 챗봇
           ============================================================ */
        .chat-container {
            width: 100%;
            height: 100%;
            background: var(--card-bg);
            display: flex;
            flex-direction: column;
        }

        .chat-messages {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 18px;
            background: #f8fafc;
        }

        .message-row {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            max-width: 82%;
            animation: fadeIn 0.25s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message-row.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }

        .avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }

        .avatar.bot {
            background: #e2e8f0;
            border: 1px solid #cbd5e1;
        }

        .avatar.user {
            background: #dbeafe;
            border: 1px solid #bfdbfe;
        }

        .bubble {
            padding: 13px 18px;
            border-radius: 16px;
            font-size: 0.93rem;
            line-height: 1.55;
            word-break: break-word;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            position: relative;
        }

        .message-row.bot .bubble {
            background: var(--bot-bubble);
            color: var(--text-dark);
            border: 1px solid var(--border);
            border-top-left-radius: 4px;
        }

        .message-row.user .bubble {
            background: var(--user-bubble);
            color: #ffffff;
            border-top-right-radius: 4px;
        }

        .timestamp {
            font-size: 0.7rem;
            color: var(--text-muted);
            margin-top: 4px;
            display: block;
        }

        .message-row.user .timestamp {
            text-align: right;
            color: rgba(255,255,255,0.7);
        }

        .quick-actions {
            padding: 8px 24px;
            background: #f8fafc;
            display: flex;
            gap: 8px;
            overflow-x: auto;
            border-top: 1px solid #f1f5f9;
        }

        .quick-btn {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 0.82rem;
            color: var(--text-dark);
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .quick-btn:hover {
            background: #eff6ff;
            border-color: #93c5fd;
            color: var(--primary);
            transform: translateY(-1px);
        }

        .typing-indicator {
            display: none;
            align-items: center;
            gap: 4px;
            padding: 12px 18px;
            background: white;
            border: 1px solid var(--border);
            border-radius: 16px;
            border-top-left-radius: 4px;
            width: fit-content;
        }

        .typing-dot {
            width: 7px;
            height: 7px;
            background: #94a3b8;
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        .chat-input-container {
            padding: 16px 24px 20px;
            background: white;
            border-top: 1px solid var(--border);
        }

        .input-form {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .chat-input {
            flex: 1;
            padding: 13px 18px;
            border: 1.5px solid var(--border);
            border-radius: 24px;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .chat-input:focus {
            border-color: var(--primary-light);
            box-shadow: 0 0 0 3px rgba(30, 61, 122, 0.12);
        }

        .send-button {
            background: var(--accent);
            color: white;
            border: none;
            width: 46px;
            height: 46px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 3px 8px rgba(230, 57, 70, 0.3);
        }

        .send-button:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
        }

        .send-button svg {
            width: 20px;
            height: 20px;
            fill: white;
        }

        /* ============================================================
           TAB 2: 기사 수집 & 요약 보고서 (좌우 2분할 뷰)
           ============================================================ */
        .research-split-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            width: 100%;
            height: 100%;
            background: #f1f5f9;
            overflow: hidden;
        }

        .split-panel {
            display: flex;
            flex-direction: column;
            height: 100%;
            background: white;
            overflow: hidden;
        }

        .split-panel.left {
            border-right: 2px solid var(--border);
        }

        /* Panel Header */
        .panel-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            background: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .panel-header-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--primary);
        }

        .panel-badge {
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 12px;
            font-weight: 600;
            background: #e2e8f0;
            color: var(--text-muted);
        }

        /* Controls Section */
        .panel-controls {
            padding: 18px 20px;
            background: white;
            border-bottom: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .form-row {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
            flex: 1;
        }

        .form-label {
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text-muted);
        }

        .form-input {
            padding: 9px 12px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 0.88rem;
            outline: none;
            transition: all 0.2s ease;
        }

        .form-input:focus {
            border-color: var(--border-focus);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
        }

        .date-range-wrap {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-group {
            display: flex;
            gap: 8px;
            margin-top: 4px;
        }

        /* Modern Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 9px 16px;
            border-radius: 8px;
            font-size: 0.86rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid transparent;
            white-space: nowrap;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-light);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: #10b981;
            color: white;
        }

        .btn-secondary:hover {
            background: #059669;
            transform: translateY(-1px);
        }

        .btn-accent {
            background: var(--accent);
            color: white;
        }

        .btn-accent:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
        }

        .btn-outline {
            background: white;
            border: 1px solid #cbd5e1;
            color: var(--text-dark);
        }

        .btn-outline:hover {
            background: #f1f5f9;
            border-color: #94a3b8;
        }

        .btn:disabled {
            opacity: 0.55;
            cursor: not-allowed;
            transform: none !important;
        }

        /* Panel Body / Results Area */
        .panel-body {
            flex: 1;
            padding: 18px 20px;
            overflow-y: auto;
            background: #f8fafc;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        /* Empty State */
        .empty-state {
            margin: auto;
            text-align: center;
            color: var(--text-muted);
            padding: 30px;
        }

        .empty-state-icon {
            font-size: 40px;
            margin-bottom: 12px;
            opacity: 0.7;
        }

        .empty-state-text {
            font-size: 0.9rem;
            line-height: 1.5;
        }

        /* Article Card */
        .article-card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }

        .article-card:hover {
            border-color: #93c5fd;
            box-shadow: 0 4px 12px rgba(15, 43, 92, 0.08);
            transform: translateY(-1px);
        }

        .article-card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .article-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .category-badge {
            background: #dbeafe;
            color: #1e40af;
            padding: 2px 7px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.72rem;
        }

        .press-badge {
            background: #e2e8f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            color: #334155;
        }

        .article-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #0f172a;
            text-decoration: none;
            line-height: 1.4;
        }

        .article-title:hover {
            color: var(--accent);
        }

        .article-snippet {
            font-size: 0.82rem;
            color: #475569;
            line-height: 1.45;
        }

        /* Report Preview Area */
        .report-preview {
            background: white;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            font-size: 0.9rem;
            line-height: 1.65;
            color: #1e293b;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
            white-space: pre-wrap;
            word-break: break-word;
        }

        .report-preview h1, .report-preview h2, .report-preview h3 {
            color: var(--primary);
            margin-top: 14px;
            margin-bottom: 8px;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 4px;
        }

        .report-preview h1 { font-size: 1.25rem; }
        .report-preview h2 { font-size: 1.08rem; }
        .report-preview h3 { font-size: 0.98rem; }

        .report-preview ul {
            padding-left: 20px;
            margin: 8px 0;
        }

        .report-preview li {
            margin-bottom: 4px;
        }

        /* Toast Notice */
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: rgba(15, 43, 92, 0.95);
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            font-size: 0.88rem;
            font-weight: 500;
            box-shadow: 0 6px 20px rgba(0,0,0,0.2);
            display: none;
            align-items: center;
            gap: 8px;
            z-index: 1000;
            animation: slideUp 0.3s ease;
        }

        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <!-- Top Header with Tab Navigation -->
    <header class="app-header">
        <div class="header-brand">
            <div class="header-logo">⚾</div>
            <div class="header-title">
                <h1>야구 뉴스 브리핑 & 분석 시스템</h1>
                <p>기사 실시간 수집 · 맞춤 요약 보고서 · CSV/MD 데이터 추출</p>
            </div>
        </div>

        <!-- Tab Buttons -->
        <nav class="tab-nav">
            <button class="tab-btn active" onclick="switchTab('chat')" id="tabBtn-chat">
                <span>💬</span> AI 챗봇
            </button>
            <button class="tab-btn" onclick="switchTab('research')" id="tabBtn-research">
                <span>📰</span> 기사 수집 & 요약 보고서
            </button>
        </nav>
    </header>

    <!-- Main Content Area -->
    <main class="main-content">
        <!-- =======================================================
             TAB 1: AI 챗봇
             ======================================================= -->
        <section class="tab-panel active" id="panel-chat">
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="message-row bot">
                        <div class="avatar bot">⚾</div>
                        <div>
                            <div class="bubble">
                                안녕하세요! <strong>야구 브리핑 AI</strong>입니다. ⚾<br><br>
                                OpenAI API와 연결되어 실시간 질의응답이 가능합니다.<br>
                                특정 기사 수집이나 요약 보고서가 필요하시면 상단의 <strong>[📰 기사 수집 & 요약 보고서]</strong> 탭을 이용해보세요!
                                <span class="timestamp">시스템 안내</span>
                            </div>
                        </div>
                    </div>

                    <div class="message-row bot typing-indicator" id="typingIndicator">
                        <div class="avatar bot">⚾</div>
                        <div class="bubble" style="display:flex; align-items:center; gap:5px; padding: 12px 16px;">
                            <span class="typing-dot"></span>
                            <span class="typing-dot"></span>
                            <span class="typing-dot"></span>
                        </div>
                    </div>
                </div>

                <div class="quick-actions">
                    <button class="quick-btn" onclick="switchTab('research')">📰 기사 수집 탭으로 이동</button>
                    <button class="quick-btn" onclick="sendQuickMessage('최근 KBO 리그 주요 관전 포인트 알려줘')">⚾ 주요 관전 포인트</button>
                    <button class="quick-btn" onclick="sendQuickMessage('야구 기사 스크랩 및 요약 보고서 활용 팁 알려줘')">💡 보고서 활용 팁</button>
                </div>

                <div class="chat-input-container">
                    <form class="input-form" id="chatForm" onsubmit="handleSubmit(event)">
                        <input type="text" id="userInput" class="chat-input" placeholder="야구에 대해 자유롭게 질문해보세요..." autocomplete="off">
                        <button type="submit" class="send-button" title="전송">
                            <svg viewBox="0 0 24 24">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                            </svg>
                        </button>
                    </form>
                </div>
            </div>
        </section>

        <!-- =======================================================
             TAB 2: 기사 수집 & 요약 보고서 (좌우 2분할 뷰)
             ======================================================= -->
        <section class="tab-panel" id="panel-research">
            <div class="research-split-container">
                
                <!-- 1. 좌측 패널: 기사 수집 영역 -->
                <div class="split-panel left">
                    <div class="panel-header">
                        <div class="panel-header-title">
                            <span>🔍</span>
                            <span>야구 기사 수집</span>
                        </div>
                        <span class="panel-badge" id="articleCountBadge">수집된 기사: 0건</span>
                    </div>

                    <div class="panel-controls">
                        <div class="form-group">
                            <label class="form-label" for="crawlKeyword">검색 키워드</label>
                            <input type="text" id="crawlKeyword" class="form-input" placeholder="예: 한화 이글스, 류현진, 포스트시즌, 가을야구">
                        </div>

                        <div class="form-group">
                            <label class="form-label">수집 기간</label>
                            <div class="date-range-wrap">
                                <input type="date" id="crawlStartDate" class="form-input" style="flex:1;">
                                <span style="color:var(--text-muted);">~</span>
                                <input type="date" id="crawlEndDate" class="form-input" style="flex:1;">
                            </div>
                        </div>

                        <div class="btn-group">
                            <button class="btn btn-primary" id="btnCrawl" onclick="handleCrawlArticles()">
                                <span>📥</span> 기사 수집
                            </button>
                            <button class="btn btn-secondary" id="btnExportCsv" onclick="handleExportCsv()">
                                <span>💾</span> 데이터 CSV 추출
                            </button>
                        </div>
                    </div>

                    <div class="panel-body" id="articleListContainer">
                        <div class="empty-state">
                            <div class="empty-state-icon">📰</div>
                            <div class="empty-state-text">
                                키워드와 기간을 설정한 후<br>
                                <strong>[기사 수집]</strong> 버튼을 누르면 기사 목록이 출력됩니다.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 2. 우측 패널: 보고서 작성 영역 -->
                <div class="split-panel right">
                    <div class="panel-header">
                        <div class="panel-header-title">
                            <span>📝</span>
                            <span>AI 요약 보고서 작성</span>
                        </div>
                        <span class="panel-badge" id="reportStatusBadge">대기 중</span>
                    </div>

                    <div class="panel-controls">
                        <div class="form-group">
                            <label class="form-label">보고서 대상 기간 (수집 기사 필터링)</label>
                            <div class="date-range-wrap">
                                <input type="date" id="reportStartDate" class="form-input" style="flex:1;">
                                <span style="color:var(--text-muted);">~</span>
                                <input type="date" id="reportEndDate" class="form-input" style="flex:1;">
                            </div>
                        </div>

                        <div class="btn-group">
                            <button class="btn btn-accent" id="btnGenerateReport" onclick="handleGenerateReport()">
                                <span>⚡</span> 보고서 작성
                            </button>
                            <button class="btn btn-outline" id="btnSaveReportMd" onclick="handleSaveReportMd()">
                                <span>📄</span> 보고서 저장 (.md)
                            </button>
                        </div>
                    </div>

                    <div class="panel-body" id="reportOutputContainer">
                        <div class="empty-state">
                            <div class="empty-state-icon">📋</div>
                            <div class="empty-state-text">
                                좌측에서 기사를 수집한 뒤 기간을 설정하고<br>
                                <strong>[보고서 작성]</strong> 버튼을 누르면 AI 맞춤 분석 보고서가 생성됩니다.
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </section>
    </main>

    <!-- Global Toast Alert -->
    <div class="toast" id="toastNotice">
        <span id="toastIcon">ℹ️</span>
        <span id="toastMessage">알림 내용</span>
    </div>

    <script>
        // 전역 상태
        let currentArticles = [];
        let currentReportText = '';

        // 초기 날짜 기본값 세팅 (최근 7일)
        window.addEventListener('DOMContentLoaded', () => {
            const today = new Date();
            const lastWeek = new Date();
            lastWeek.setDate(today.getDate() - 7);

            const formatDate = (d) => d.toISOString().split('T')[0];
            
            document.getElementById('crawlStartDate').value = formatDate(lastWeek);
            document.getElementById('crawlEndDate').value = formatDate(today);
            document.getElementById('reportStartDate').value = formatDate(lastWeek);
            document.getElementById('reportEndDate').value = formatDate(today);
        });

        // 토스트 알림
        function showToast(msg, icon = 'ℹ️') {
            const toast = document.getElementById('toastNotice');
            document.getElementById('toastIcon').innerText = icon;
            document.getElementById('toastMessage').innerText = msg;
            toast.style.display = 'flex';
            setTimeout(() => { toast.style.display = 'none'; }, 3200);
        }

        // 탭 전환
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));

            document.getElementById(`tabBtn-${tabId}`).classList.add('active');
            document.getElementById(`panel-${tabId}`).classList.add('active');
        }

        // ============================================================
        // 챗봇 관련 로직
        // ============================================================
        const messagesContainer = document.getElementById('chatMessages');
        const userInput = document.getElementById('userInput');
        const typingIndicator = document.getElementById('typingIndicator');

        function getTimeString() {
            const now = new Date();
            return now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        }

        function scrollToBottom() {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function appendMessage(sender, text) {
            const row = document.createElement('div');
            row.className = `message-row ${sender}`;

            const avatar = document.createElement('div');
            avatar.className = `avatar ${sender}`;
            avatar.innerText = sender === 'bot' ? '⚾' : '👤';

            const bubbleWrap = document.createElement('div');
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            
            let formatted = text
                .replace(/\\n/g, '<br>')
                .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
            
            bubble.innerHTML = formatted + `<span class=\"timestamp\">${getTimeString()}</span>`;
            
            bubbleWrap.appendChild(bubble);
            row.appendChild(avatar);
            row.appendChild(bubbleWrap);

            messagesContainer.insertBefore(row, typingIndicator);
            scrollToBottom();
        }

        function showTyping(show) {
            typingIndicator.style.display = show ? 'flex' : 'none';
            if (show) scrollToBottom();
        }

        async function handleSubmit(e) {
            if (e) e.preventDefault();
            const text = userInput.value.trim();
            if (!text) return;

            appendMessage('user', text);
            userInput.value = '';
            showTyping(true);

            try {
                if (window.pywebview && window.pywebview.api) {
                    const response = await window.pywebview.api.send_message(text);
                    showTyping(false);
                    if (response && response.reply) {
                        appendMessage('bot', response.reply);
                    } else {
                        appendMessage('bot', '응답을 가져오지 못했습니다.');
                    }
                } else {
                    setTimeout(() => {
                        showTyping(false);
                        appendMessage('bot', `[테스트 모드] '${text}' 요청이 접수되었습니다.`);
                    }, 600);
                }
            } catch (err) {
                showTyping(false);
                appendMessage('bot', `오류가 발생했습니다: ${err.message || err}`);
            }
        }

        function sendQuickMessage(text) {
            userInput.value = text;
            handleSubmit();
        }

        // ============================================================
        // 기사 수집 & CSV 추출 로직
        // ============================================================
        async function handleCrawlArticles() {
            const keyword = document.getElementById('crawlKeyword').value.trim();
            const startDate = document.getElementById('crawlStartDate').value;
            const endDate = document.getElementById('crawlEndDate').value;

            if (!keyword) {
                showToast('검색할 키워드를 입력해주세요.', '⚠️');
                document.getElementById('crawlKeyword').focus();
                return;
            }

            const btn = document.getElementById('btnCrawl');
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> 수집 중...';

            const container = document.getElementById('articleListContainer');
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⏳</div>
                    <div class="empty-state-text">
                        '${keyword}' 관련 기사를 수집하고 있습니다...<br>잠시만 기다려 주세요.
                    </div>
                </div>`;

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.fetch_articles(keyword, startDate, endDate);
                    btn.disabled = false;
                    btn.innerHTML = '<span>📥</span> 기사 수집';

                    if (res && res.status === 'success') {
                        currentArticles = res.articles || [];
                        renderArticles(currentArticles);
                        showToast(`${currentArticles.length}건의 기사를 수집했습니다!`, '✅');
                    } else {
                        showToast(res.message || '기사 수집에 실패했습니다.', '❌');
                    }
                } else {
                    // 브라우저 단독 테스트용 더미
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = '<span>📥</span> 기사 수집';
                        currentArticles = [
                            { id: 1, title: `[KBO] '${keyword}' 가을야구 향한 총력전 돌입`, press: '스포츠조선', date: endDate, url: 'https://sports.news.naver.com/kbaseball/', snippet: '선수단 전원이 결집하여 후반기 순위 싸움에 박차를 가하고 있다.' },
                            { id: 2, title: `전문가 분석: 이번 주 '${keyword}' 핵심 관전 포인트는?`, press: 'OSEN', date: startDate, url: 'https://sports.news.naver.com/kbaseball/', snippet: '선발 투수진의 안정세와 중심 타선의 득점권 타율이 승패를 가를 전망이다.' }
                        ];
                        renderArticles(currentArticles);
                        showToast(`${currentArticles.length}건의 기사를 수집했습니다. (테스트)`, '✅');
                    }, 800);
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>📥</span> 기사 수집';
                showToast(`에러: ${err.message || err}`, '❌');
            }
        }

        function renderArticles(articles) {
            const container = document.getElementById('articleListContainer');
            const countBadge = document.getElementById('articleCountBadge');
            countBadge.innerText = `수집된 기사: ${articles.length}건`;

            if (!articles || articles.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">🔍</div>
                        <div class="empty-state-text">조건에 맞는 기사를 찾지 못했습니다.</div>
                    </div>`;
                return;
            }

            let html = '';
            articles.forEach(art => {
                html += `
                    <div class="article-card">
                        <div class="article-card-header">
                            <div class="article-meta">
                                <span class="category-badge">${art.category || '국내야구'}</span>
                                <span class="press-badge">${art.press || '언론사'}</span>
                                <span>📅 ${art.date || ''}</span>
                            </div>
                        </div>
                        <a href="${art.url || '#'}" target="_blank" class="article-title">${art.title}</a>
                        <p class="article-snippet">${art.snippet || ''}</p>
                    </div>`;
            });
            container.innerHTML = html;
        }

        async function handleExportCsv() {
            if (!currentArticles || currentArticles.length === 0) {
                showToast('먼저 기사를 수집해주세요.', '⚠️');
                return;
            }

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.export_articles_csv();
                    if (res && res.status === 'success') {
                        showToast(res.message || 'CSV 파일이 성공적으로 저장되었습니다!', '💾');
                    } else {
                        showToast(res.message || 'CSV 저장 실패', '❌');
                    }
                } else {
                    showToast('CSV 추출이 요청되었습니다. (테스트)', '💾');
                }
            } catch (err) {
                showToast(`저장 오류: ${err.message || err}`, '❌');
            }
        }

        // ============================================================
        // 보고서 작성 & MD 저장 로직
        // ============================================================
        async function handleGenerateReport() {
            if (!currentArticles || currentArticles.length === 0) {
                showToast('좌측에서 먼저 기사를 수집해주세요.', '⚠️');
                return;
            }

            const startDate = document.getElementById('reportStartDate').value;
            const endDate = document.getElementById('reportEndDate').value;

            const btn = document.getElementById('btnGenerateReport');
            const statusBadge = document.getElementById('reportStatusBadge');
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> 작성 중...';
            statusBadge.innerText = 'AI 분석 중...';

            const container = document.getElementById('reportOutputContainer');
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🤖</div>
                    <div class="empty-state-text">
                        해당 기간(${startDate} ~ ${endDate})의 기사를 선별하여<br>
                        AI가 종합 요약 보고서를 작성하고 있습니다...
                    </div>
                </div>`;

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.generate_report(startDate, endDate);
                    btn.disabled = false;
                    btn.innerHTML = '<span>⚡</span> 보고서 작성';
                    statusBadge.innerText = '작성 완료';

                    if (res && res.status === 'success') {
                        currentReportText = res.report_md;
                        renderReport(currentReportText);
                        showToast('AI 요약 보고서 작성이 완료되었습니다!', '✅');
                    } else {
                        showToast(res.message || '보고서 생성 실패', '❌');
                    }
                } else {
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = '<span>⚡</span> 보고서 작성';
                        statusBadge.innerText = '작성 완료';
                        currentReportText = `# ⚾ KBO 야구 뉴스 AI 브리핑 보고서\\n\\n**분석 기간**: ${startDate} ~ ${endDate}\\n\\n## 1. 핵심 3줄 요약\\n- 수집된 기사를 기반으로 경기 및 선수단 주요 이슈 분석 완료\\n- 선발 마운드와 클러치 타선의 활약이 주요 화두로 부상\\n- 순위 다툼이 치열해짐에 따라 경기별 불펜 운용이 승패 좌우\\n\\n## 2. 세부 이슈 및 시사점\\n- 주요 선수들의 부상 복귀와 엔트리 변동 체크 필요\\n- 향후 잔여 경기 일정에 따른 맞춤형 전략 수립 전망`;
                        renderReport(currentReportText);
                        showToast('보고서 작성 완료 (테스트)', '✅');
                    }, 1000);
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡</span> 보고서 작성';
                statusBadge.innerText = '오류';
                showToast(`오류: ${err.message || err}`, '❌');
            }
        }

        function renderReport(mdText) {
            const container = document.getElementById('reportOutputContainer');
            
            // 기본적인 Markdown 변환 (헤더, 볼드, 불릿 등)
            let html = mdText
                .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                .replace(/\\*\\*(.*?)\\*\\*/gim, '<strong>$1</strong>')
                .replace(/^\\- (.*$)/gim, '<li>$1</li>')
                .replace(/\\n/gim, '<br>');

            container.innerHTML = `<div class="report-preview">${html}</div>`;
        }

        async function handleSaveReportMd() {
            if (!currentReportText) {
                showToast('먼저 보고서를 작성해주세요.', '⚠️');
                return;
            }

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.save_report_md();
                    if (res && res.status === 'success') {
                        showToast(res.message || '보고서가 .md 파일로 저장되었습니다!', '📄');
                    } else {
                        showToast(res.message || '보고서 저장 실패', '❌');
                    }
                } else {
                    showToast('보고서 .md 저장이 요청되었습니다. (테스트)', '📄');
                }
            } catch (err) {
                showToast(`저장 오류: ${err.message || err}`, '❌');
            }
        }

        window.addEventListener('pywebviewready', () => {
            console.log('pywebview 브릿지가 준비되었습니다.');
        });
    </script>
</body>
</html>"""
