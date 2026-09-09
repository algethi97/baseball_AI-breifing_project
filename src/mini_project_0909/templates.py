"""
HTML, CSS, JavaScript 기반 야구 뉴스 챗봇 UI 템플릿
"""

HTML_CODE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>야구 뉴스 브리핑 AI</title>
    <style>
        :root {
            --primary: #0f2b5c;
            --primary-light: #1e3d7a;
            --accent: #e63946;
            --accent-hover: #d62839;
            --bg: #f4f6f9;
            --card-bg: #ffffff;
            --text-dark: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --bot-bubble: #ffffff;
            --user-bubble: #0f2b5c;
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
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        .chat-container {
            width: 100%;
            height: 100vh;
            background: var(--card-bg);
            display: flex;
            flex-direction: column;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
        }

        /* Header */
        .chat-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            color: white;
            padding: 18px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .header-title-wrap {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-badge {
            font-size: 26px;
            background: rgba(255, 255, 255, 0.15);
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.25);
        }

        .header-text h1 {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.3px;
        }

        .header-text p {
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.8);
            margin-top: 2px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.2);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #34d399;
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 600;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 8px #10b981;
        }

        /* Message Area */
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

        /* Quick Buttons */
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

        /* Typing Indicator */
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

        /* Input Area */
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
            box-shadow: 0 4px 12px rgba(230, 57, 70, 0.4);
        }

        .send-button:active {
            transform: translateY(1px);
        }

        .send-button svg {
            width: 20px;
            height: 20px;
            fill: white;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <!-- 헤더 -->
        <header class="chat-header">
            <div class="header-title-wrap">
                <div class="logo-badge">⚾</div>
                <div class="header-text">
                    <h1>야구 뉴스 브리핑 AI</h1>
                    <p>기사 수집 · 요약 보고서 · 데이터 저장 챗봇</p>
                </div>
            </div>
            <div class="status-badge">
                <span class="status-dot"></span>
                <span>온라인</span>
            </div>
        </header>

        <!-- 채팅 메시지 영역 -->
        <div class="chat-messages" id="chatMessages">
            <div class="message-row bot">
                <div class="avatar bot">⚾</div>
                <div>
                    <div class="bubble">
                        안녕하세요! <strong>야구 뉴스 브리핑 AI</strong>입니다.<br><br>
                        KBO 리그 및 야구 뉴스 기사 수집, 요약 리포트 작성, 데이터 저장을 도와드립니다.<br>
                        궁금하신 팀이나 선수의 소식을 질문하시거나 아래 퀵 버튼을 눌러보세요!
                        <span class="timestamp">시스템 안내</span>
                    </div>
                </div>
            </div>

            <!-- 로딩 인디케이터 -->
            <div class="message-row bot typing-indicator" id="typingIndicator">
                <div class="avatar bot">⚾</div>
                <div class="bubble" style="display:flex; align-items:center; gap:5px; padding: 12px 16px;">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        </div>

        <!-- 퀵 추천 질문 버튼 -->
        <div class="quick-actions">
            <button class="quick-btn" onclick="sendQuickMessage('📰 오늘의 주요 야구 뉴스 브리핑해줘')">📰 오늘 주요 뉴스</button>
            <button class="quick-btn" onclick="sendQuickMessage('🏆 팀별 순위 및 이슈 요약해줘')">🏆 순위 & 이슈 요약</button>
            <button class="quick-btn" onclick="sendQuickMessage('💾 최신 기사 스크랩 및 CSV 저장 준비해줘')">💾 기사 CSV 저장</button>
        </div>

        <!-- 입력창 -->
        <div class="chat-input-container">
            <form class="input-form" id="chatForm" onsubmit="handleSubmit(event)">
                <input type="text" id="userInput" class="chat-input" placeholder="야구 뉴스에 대해 질문해보세요... (예: 오늘의 한화 이글스 소식)" autocomplete="off" autofocus>
                <button type="submit" class="send-button" title="전송">
                    <svg viewBox="0 0 24 24">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                    </svg>
                </button>
            </form>
        </div>
    </div>

    <script>
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
            
            // 줄바꿈 및 강조 포맷팅 처리
            let formatted = text
                .replace(/\\n/g, '<br>')
                .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
            
            bubble.innerHTML = formatted + `<span class="timestamp">${getTimeString()}</span>`;
            
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

            // 유저 메시지 화면 추가
            appendMessage('user', text);
            userInput.value = '';
            showTyping(true);

            try {
                // pywebview 백엔드 API 호출
                if (window.pywebview && window.pywebview.api) {
                    const response = await window.pywebview.api.send_message(text);
                    showTyping(false);
                    if (response && response.reply) {
                        appendMessage('bot', response.reply);
                    } else {
                        appendMessage('bot', '응답을 가져오지 못했습니다.');
                    }
                } else {
                    // 브라우저 단독 실행 테스트용 fallback
                    setTimeout(() => {
                        showTyping(false);
                        appendMessage('bot', `[웹 브라우저 테스트 모드]\\n'${text}' 요청이 접수되었습니다. pywebview 환경에서 실행 시 파이썬 백엔드와 실시간 연동됩니다.`);
                    }, 700);
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

        window.addEventListener('pywebviewready', () => {
            console.log('pywebview 브릿지가 준비되었습니다.');
        });
    </script>
</body>
</html>"""

