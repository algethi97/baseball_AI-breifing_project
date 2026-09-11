// 전역 상태
        let currentArticles = [];
        let currentReportText = '';
        let currentStadiumWeather = [];
        let currentWeatherFilter = 'all';
        let weatherLoaded = false;

        // 초기 날짜 기본값 세팅 (최근 7일) 및 기간 연동
        window.addEventListener('DOMContentLoaded', () => {
            const today = new Date();
            const lastWeek = new Date();
            lastWeek.setDate(today.getDate() - 7);

            const formatDate = (d) => d.toISOString().split('T')[0];
            
            const crawlStart = document.getElementById('crawlStartDate');
            const crawlEnd = document.getElementById('crawlEndDate');
            const reportStart = document.getElementById('reportStartDate');
            const reportEnd = document.getElementById('reportEndDate');

            crawlStart.value = formatDate(lastWeek);
            crawlEnd.value = formatDate(today);
            reportStart.value = formatDate(lastWeek);
            reportEnd.value = formatDate(today);

            // [기능 추가] 수집 기간 변경 시 보고서 작성 탭의 기간도 자동 연동
            crawlStart.addEventListener('change', () => {
                if (crawlStart.value) reportStart.value = crawlStart.value;
            });
            crawlEnd.addEventListener('change', () => {
                if (crawlEnd.value) reportEnd.value = crawlEnd.value;
            });
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

            const targetBtn = document.getElementById(`tabBtn-${tabId}`);
            const targetPanel = document.getElementById(`panel-${tabId}`);
            if (targetBtn) targetBtn.classList.add('active');
            if (targetPanel) targetPanel.classList.add('active');

            // 구장 날씨 탭 최초 전환 시 자동 로드
            if (tabId === 'weather' && !weatherLoaded) {
                loadStadiumWeather();
            }
        }

        // ============================================================
        // 챗봇 ↔ 기사/보고서 연동 상태 동기화 UI 로직
        // ============================================================
        function updateChatContextUI(keyword = '', articleCount = 0, hasReport = false) {
            const dot = document.getElementById('contextDot');
            const text = document.getElementById('contextText');
            const btn = document.getElementById('btnContextAction');
            const quickActions = document.getElementById('quickActions');

            if (!dot || !text || !btn) return;
            dot.className = 'context-dot';

            if (hasReport) {
                dot.classList.add('active-report');
                text.innerHTML = `연동 완료: <strong>'${keyword || '야구'}'</strong> AI 심층 보고서 & 기사 원문 ${articleCount}건 참조 중`;
                btn.innerText = '📄 보고서 보러가기';
                btn.onclick = () => switchTab('research');

                if (quickActions) {
                    quickActions.innerHTML = `
                        <button class="quick-btn" onclick="sendQuickMessage('방금 작성된 보고서의 핵심 요약 3줄을 더 쉽게 설명해줘')">📄 보고서 핵심 요약</button>
                        <button class="quick-btn" onclick="sendQuickMessage('보고서에서 언급된 주요 경기 승부처와 선수 활약상 알려줘')">⚾ 경기별 승부처</button>
                        <button class="quick-btn" onclick="sendQuickMessage('보고서 내용 바탕으로 앞으로 팀의 전력 전망을 분석해줘')">📊 향후 전력 전망</button>
                    `;
                }
            } else if (articleCount > 0) {
                dot.classList.add('active-articles');
                text.innerHTML = `연동 중: <strong>'${keyword || '야구'}'</strong> 기사 원문 ${articleCount}건 참조 중`;
                btn.innerText = '⚡ AI 보고서 작성하러 가기';
                btn.onclick = () => switchTab('research');

                if (quickActions) {
                    quickActions.innerHTML = `
                        <button class="quick-btn" onclick="sendQuickMessage('수집된 기사들에서 가장 활약이 돋보인 선수는 누구야?')">🔥 주요 활약 선수</button>
                        <button class="quick-btn" onclick="sendQuickMessage('DB에 저장된 언론사별 기사 건수 상위 5곳 통계 내줘')">📊 DB 언론사별 기사 통계</button>
                        <button class="quick-btn" onclick="sendQuickMessage('수집된 전체 기사의 전반적인 이슈와 분위기를 요약해줘')">📰 수집 기사 분위기</button>
                        <button class="quick-btn" onclick="switchTab('research')">📝 AI 분석 보고서 탭</button>
                    `;
                }
            } else {
                text.innerText = '연동 상태: 일반 야구 지식 & SQLAlchemy 2.0 DB 제어 모드';
                btn.innerText = '📰 기사 수집 & 분석';
                btn.onclick = () => switchTab('research');

                if (quickActions) {
                    quickActions.innerHTML = `
                        <button class="quick-btn" onclick="switchTab('research')">📰 기사 수집 & 분석 탭으로 이동</button>
                        <button class="quick-btn" onclick="sendQuickMessage('DB에 저장된 언론사별 기사 건수 상위 5곳 통계 내줘')">📊 DB 언론사별 기사 통계</button>
                        <button class="quick-btn" onclick="sendQuickMessage('현재 데이터베이스에 어떤 테이블들이 있고 구조가 어떻게 돼?')">📋 DB 스키마 확인</button>
                        <button class="quick-btn" onclick="sendQuickMessage('DB에 저장된 최근 수집 세션 이력 5개 보여줘')">🔍 수집 세션 이력</button>
                        <button class="quick-btn" onclick="sendQuickMessage('최근 KBO 리그 주요 관전 포인트 알려줘')">⚾ 주요 관전 포인트</button>
                    `;
                }
            }
        }

        function handleAskBotAboutReport() {
            switchTab('chat');
            const defaultPrompt = "방금 작성된 AI 요약 보고서의 주요 핵심 내용과 경기 승부처를 알기 쉽게 풀어서 설명해줘.";
            userInput.value = defaultPrompt;
            handleSubmit();
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

        function formatChatText(text) {
            if (!text) return '';
            
            // 1. 코드 블록 처리 (```sql ... ```)
            let formatted = text.replace(/```(?:sql)?\s*([\s\S]*?)\s*```/gi, (match, code) => {
                const safeCode = code.trim().replace(/"/g, '&quot;');
                return `
                    <div class="sql-code-box">
                        <div class="sql-code-header">
                            <span>🗄️ SQLAlchemy 2.0 SQL Query</span>
                            <button class="sql-copy-btn" type="button" onclick="navigator.clipboard.writeText(decodeURIComponent('${encodeURIComponent(code.trim())}')).then(() => showToast('SQL 쿼리가 복사되었습니다.', '📋'))">복사</button>
                        </div>
                        <pre class="sql-code-content"><code>${code.trim()}</code></pre>
                    </div>
                `;
            });

            // 2. 마크다운 표(| col1 | col2 |) HTML <table> 변환
            const lines = formatted.split('\n');
            let inTable = false;
            let tableHtml = '';
            let resultLines = [];

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (line.startsWith('|') && line.endsWith('|')) {
                    const cells = line.split('|').slice(1, -1).map(c => c.trim());
                    // 구분선 (|---|---|) 스킵
                    if (cells.every(c => /^[-:]+$/.test(c))) {
                        continue;
                    }

                    if (!inTable) {
                        inTable = true;
                        tableHtml = '<div class="markdown-table-wrap"><table class="db-result-table"><thead><tr>';
                        cells.forEach(c => { tableHtml += `<th>${c}</th>`; });
                        tableHtml += '</tr></thead><tbody>';
                    } else {
                        tableHtml += '<tr>';
                        cells.forEach(c => { tableHtml += `<td>${c}</td>`; });
                        tableHtml += '</tr>';
                    }
                } else {
                    if (inTable) {
                        inTable = false;
                        tableHtml += '</tbody></table></div>';
                        resultLines.push(tableHtml);
                        tableHtml = '';
                    }
                    resultLines.push(lines[i]);
                }
            }
            if (inTable) {
                tableHtml += '</tbody></table></div>';
                resultLines.push(tableHtml);
            }

            formatted = resultLines.join('\n');

            // 3. 인라인 서식 적용
            formatted = formatted
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
                .replace(/\n/g, '<br>');

            formatted = formatted.replace(/<\/div><br>/g, '</div>');
            return formatted;
        }

        function appendMessage(sender, text, action = null) {
            const row = document.createElement('div');
            row.className = `message-row ${sender}`;

            const avatar = document.createElement('div');
            avatar.className = `avatar ${sender}`;
            avatar.innerText = sender === 'bot' ? '⚾' : '👤';

            const bubbleWrap = document.createElement('div');
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            
            let formatted = formatChatText(text);
            
            bubble.innerHTML = formatted + `<span class="timestamp">${getTimeString()}</span>`;
            bubbleWrap.appendChild(bubble);

            // [기능 추가] 자연어 기사 수집 완료 액션 카드 및 탭 이동 버튼 연동
            if (sender === 'bot' && action && action.type === 'crawl_completed' && action.article_count > 0) {
                const actionCard = document.createElement('div');
                actionCard.className = 'chat-action-card';
                actionCard.innerHTML = `
                    <div class="action-card-header">
                        <span class="action-badge">✅ 기사 원문 수집 완료</span>
                        <span class="action-count">총 <strong>${action.article_count}</strong>건</span>
                    </div>
                    <div class="action-card-meta">
                        <span>🔍 <strong>'${action.keyword}'</strong></span>
                        <span>📅 ${action.start_date} ~ ${action.end_date}</span>
                    </div>
                `;
                const jumpBtn = document.createElement('button');
                jumpBtn.className = 'action-jump-btn';
                jumpBtn.type = 'button';
                jumpBtn.innerHTML = '<span>📰</span> <strong>[기사 수집 & 분석]</strong> 탭에서 결과 보기 ➔';
                jumpBtn.onclick = () => goToResearchWithArticles(action);
                actionCard.appendChild(jumpBtn);
                bubbleWrap.appendChild(actionCard);
            }

            // [기능 추가] SQLAlchemy 2.0 AI DB 쿼리 실행 결과 상태 배지 카드
            if (sender === 'bot' && action && action.type === 'db_query_result') {
                const dbBadge = document.createElement('div');
                const isDelete = action.query_type === 'DELETE';
                const actionLabel = isDelete ? '삭제' : (action.query_type === 'READ' ? '조회' : '처리');
                dbBadge.className = `chat-db-badge-card ${isDelete ? 'delete-badge' : ''}`;
                dbBadge.innerHTML = `
                    <span class="db-badge-type ${isDelete ? 'delete-type' : ''}">⚡ ${action.query_type}</span>
                    <span class="db-badge-info">SQLAlchemy 2.0 엔진 실행 완료 (${actionLabel}: <strong>${action.row_count}</strong>건)</span>
                `;
                bubbleWrap.appendChild(dbBadge);
            }
            
            row.appendChild(avatar);
            row.appendChild(bubbleWrap);

            messagesContainer.insertBefore(row, typingIndicator);
            scrollToBottom();
        }

        // [신규 기능] 챗봇에서 수집된 기사 데이터를 가지고 기사 수집 & 분석 탭으로 즉시 이동
        function goToResearchWithArticles(action) {
            if (!action) return;

            const { keyword, start_date, end_date, articles, article_count } = action;

            // 1. 입력 필드 자동 채움
            const crawlKeyword = document.getElementById('crawlKeyword');
            const crawlStartDate = document.getElementById('crawlStartDate');
            const crawlEndDate = document.getElementById('crawlEndDate');
            const reportStartDate = document.getElementById('reportStartDate');
            const reportEndDate = document.getElementById('reportEndDate');

            if (crawlKeyword && keyword) crawlKeyword.value = keyword;
            if (crawlStartDate && start_date) crawlStartDate.value = start_date;
            if (crawlEndDate && end_date) crawlEndDate.value = end_date;
            if (reportStartDate && start_date) reportStartDate.value = start_date;
            if (reportEndDate && end_date) reportEndDate.value = end_date;

            // 2. 기사 목록 렌더링 및 전역 상태 동기화
            if (articles && articles.length > 0) {
                currentArticles = articles;
                renderArticles(currentArticles);
                updateChatContextUI(keyword, currentArticles.length, !!currentReportText);
            }

            // 3. 탭 전환
            switchTab('research');
            showToast(`'${keyword}' 기사 수집 결과 탭으로 이동했습니다. (${article_count || (articles ? articles.length : 0)}건)`, '📰');
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
                        // 백그라운드 수집 결과가 있으면 전역 기사 상태 및 상단 연동 바 사전 동기화
                        if (response.action && response.action.type === 'crawl_completed' && response.action.articles) {
                            currentArticles = response.action.articles;
                            renderArticles(currentArticles);
                            updateChatContextUI(response.action.keyword, currentArticles.length, !!currentReportText);
                        }
                        appendMessage('bot', response.reply, response.action);
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

            // [기능 추가] 기사 수집 기간을 우측 보고서 작성 탭의 기간과 자동 연동
            if (startDate) {
                document.getElementById('reportStartDate').value = startDate;
            }
            if (endDate) {
                document.getElementById('reportEndDate').value = endDate;
            }

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
                        '${keyword}' 관련 기사 원문을 수집하고 있습니다...<br>잠시만 기다려 주세요.
                    </div>
                </div>`;

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.fetch_articles(keyword, startDate, endDate);
                    btn.disabled = false;
                    btn.innerHTML = '<span>📥</span> 기사 원문 수집 (최대 200건)';

                    if (res && res.status === 'success') {
                        currentArticles = res.articles || [];
                        renderArticles(currentArticles);
                        showToast(`${currentArticles.length}건의 기사 원문을 수집했습니다! (최대 200건)`, '✅');
                        updateChatContextUI(keyword, currentArticles.length, !!currentReportText);
                    } else {
                        showToast(res.message || '기사 수집에 실패했습니다.', '❌');
                    }
                } else {
                    // 브라우저 단독 테스트용 더미
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = '<span>📥</span> 기사 원문 수집 (최대 200건)';
                        currentArticles = [
                            { id: 1, title: `[KBO] '${keyword}' 가을야구 향한 총력전 돌입`, press: '스포츠조선', date: endDate, url: 'https://sports.news.naver.com/kbaseball/', snippet: '선수단 전원이 결집하여 후반기 순위 싸움에 박차를 가하고 있다.' },
                            { id: 2, title: `전문가 분석: 이번 주 '${keyword}' 핵심 관전 포인트는?`, press: 'OSEN', date: startDate, url: 'https://sports.news.naver.com/kbaseball/', snippet: '선발 투수진의 안정세와 중심 타선의 득점권 타율이 승패를 가를 전망이다.' }
                        ];
                        renderArticles(currentArticles);
                        showToast(`${currentArticles.length}건의 기사 원문을 수집했습니다. (테스트)`, '✅');
                        updateChatContextUI(keyword, currentArticles.length, !!currentReportText);
                    }, 800);
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>📥</span> 기사 원문 수집 (최대 200건)';
                showToast(`에러: ${err.message || err}`, '❌');
            }
        }

        function openExternalLink(url) {
            if (!url || url === '#') return;
            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external_link) {
                    window.pywebview.api.open_external_link(url);
                } else {
                    window.open(url, '_blank');
                }
            } catch (e) {
                window.open(url, '_blank');
            }
        }

        function renderArticles(articles) {
            const container = document.getElementById('articleListContainer');
            const countBadge = document.getElementById('articleCountBadge');
            countBadge.innerText = `수집된 기사 원문: ${articles.length}건 (최대 200건)`;

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
                const url = art.url || '#';
                const bodyText = art.content || art.snippet || '';
                const snippetText = bodyText.length > 180 ? bodyText.slice(0, 180) + '...' : bodyText;
                html += `
                    <div class="article-card">
                        <div class="article-card-header">
                            <div class="article-meta">
                                <span class="category-badge">${art.category || '국내야구'}</span>
                                <span class="press-badge">${art.press || '언론사'}</span>
                                <span>📅 ${art.date || ''}</span>
                            </div>
                        </div>
                        <a href="${url}" target="_blank" onclick="event.preventDefault(); openExternalLink('${url}');" class="article-title">${art.title}</a>
                        <p class="article-snippet">${snippetText}</p>
                    </div>`;
            });
            container.innerHTML = html;
        }

        async function handleExportCsv() {
            if (!currentArticles || currentArticles.length === 0) {
                showToast('먼저 기사 원문을 수집해주세요.', '⚠️');
                return;
            }

            const keyword = document.getElementById('crawlKeyword').value.trim();

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.export_articles_csv(keyword);
                    if (res && res.status === 'success') {
                        showToast(res.message || '기사 원문 CSV 파일이 성공적으로 저장되었습니다!', '💾');
                    } else {
                        showToast(res.message || 'CSV 저장 실패', '❌');
                    }
                } else {
                    const today = new Date().toISOString().split('T')[0].replace(/-/g, '');
                    showToast(`[테스트 모드] ${keyword || '야구'}_기사수집_${today}.csv 추출 완료`, '💾');
                }
            } catch (err) {
                showToast(`저장 오류: ${err.message || err}`, '❌');
            }
        }

        async function handleExportDb() {
            if (!currentArticles || currentArticles.length === 0) {
                showToast('먼저 기사 원문을 수집해주세요.', '⚠️');
                return;
            }

            const keyword = document.getElementById('crawlKeyword').value.trim();
            const startDate = document.getElementById('crawlStartDate').value;
            const endDate = document.getElementById('crawlEndDate').value;

            const btn = document.getElementById('btnExportDb');
            const originalHtml = btn ? btn.innerHTML : '<span>🗄️</span> 데이터베이스 추출 (.db)';
            let autoGeneratedReport = false;

            try {
                // [신규 기능] 만약 작성된 보고서가 없다면 먼저 AI 보고서를 자동으로 작성 후 DB 추출
                if (!currentReportText) {
                    autoGeneratedReport = true;
                    if (btn) {
                        btn.disabled = true;
                        btn.innerHTML = '<span>⏳</span> 1/2: AI 보고서 작성 중...';
                    }

                    // 보고서 기간 기본값 동기화
                    const repStartInput = document.getElementById('reportStartDate');
                    const repEndInput = document.getElementById('reportEndDate');
                    const reportStart = (repStartInput && repStartInput.value) ? repStartInput.value : startDate;
                    const reportEnd = (repEndInput && repEndInput.value) ? repEndInput.value : endDate;

                    const statusBadge = document.getElementById('reportStatusBadge');
                    if (statusBadge) statusBadge.innerText = 'AI 분석 중...';

                    const container = document.getElementById('reportOutputContainer');
                    if (container) {
                        container.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">🤖</div>
                                <div class="empty-state-text">
                                    데이터베이스 통합 저장을 위해<br>
                                    AI가 기사 원문을 정밀 분석하여 보고서를 작성하고 있습니다...
                                </div>
                            </div>`;
                    }

                    if (window.pywebview && window.pywebview.api) {
                        const repRes = await window.pywebview.api.generate_report(reportStart, reportEnd, keyword);
                        if (repRes && repRes.status === 'success') {
                            currentReportText = repRes.report_md;
                            renderReport(currentReportText);
                            if (statusBadge) statusBadge.innerText = '작성 완료';
                            const askBotBtn = document.getElementById('btnAskBotAboutReport');
                            if (askBotBtn) askBotBtn.style.display = 'inline-flex';
                            updateChatContextUI(keyword, currentArticles.length, true);
                        } else {
                            showToast(repRes.message || 'AI 보고서 자동 작성 실패', '❌');
                            if (statusBadge) statusBadge.innerText = '오류';
                            return;
                        }
                    } else {
                        // 브라우저 단독 테스트 모드 더미
                        currentReportText = `# ⚾ KBO 야구 뉴스 AI 브리핑 보고서\n\n**분석 기간**: ${reportStart} ~ ${reportEnd}\n\n## 1. 핵심 3줄 요약\n- 자동 작성된 AI 보고서와 기사 원문이 데이터베이스에 통합 저장됩니다.`;
                        renderReport(currentReportText);
                        if (statusBadge) statusBadge.innerText = '작성 완료';
                        updateChatContextUI(keyword, currentArticles.length, true);
                    }
                }

                // 2단계: 데이터베이스 추출
                if (btn) {
                    btn.disabled = true;
                    btn.innerHTML = autoGeneratedReport ? '<span>⏳</span> 2/2: DB 추출 중...' : '<span>⏳</span> DB 추출 중...';
                }

                if (window.pywebview && window.pywebview.api && window.pywebview.api.export_articles_db) {
                    const res = await window.pywebview.api.export_articles_db(keyword, startDate, endDate);
                    if (res && res.status === 'success') {
                        const successMsg = autoGeneratedReport 
                            ? 'AI 보고서 자동 작성 및 데이터베이스(.db) 추출 완료!' 
                            : (res.message || '데이터베이스(.db) 파일이 성공적으로 추출되었습니다!');
                        showToast(successMsg, '🗄️');
                    } else {
                        showToast(res.message || '데이터베이스 추출 실패', '❌');
                    }
                } else {
                    const msg = autoGeneratedReport 
                        ? `[테스트 모드] ${keyword || '야구'}_데이터베이스.db (AI 보고서 자동 포함) 추출 완료` 
                        : `[테스트 모드] ${keyword || '야구'}_데이터베이스.db 누적 적재 완료`;
                    showToast(msg, '🗄️');
                }
            } catch (err) {
                showToast(`DB 저장 오류: ${err.message || err}`, '❌');
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            }
        }

        // ============================================================
        // 보고서 작성 & MD 저장 로직
        // ============================================================
        async function handleGenerateReport() {
            if (!currentArticles || currentArticles.length === 0) {
                showToast('좌측에서 먼저 기사 원문을 수집해주세요.', '⚠️');
                return;
            }

            const startDate = document.getElementById('reportStartDate').value;
            const endDate = document.getElementById('reportEndDate').value;
            const keyword = document.getElementById('crawlKeyword').value.trim();

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
                        해당 기간(${startDate} ~ ${endDate})의 기사 원문을 정밀 분석하여<br>
                        AI가 맞춤 심층 분석 보고서를 작성하고 있습니다...
                    </div>
                </div>`;

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.generate_report(startDate, endDate, keyword);
                    btn.disabled = false;
                    btn.innerHTML = '<span>⚡</span> AI 보고서 작성';
                    statusBadge.innerText = '작성 완료';

                    if (res && res.status === 'success') {
                        currentReportText = res.report_md;
                        renderReport(currentReportText);
                        const askBotBtn = document.getElementById('btnAskBotAboutReport');
                        if (askBotBtn) askBotBtn.style.display = 'inline-flex';
                        updateChatContextUI(keyword, currentArticles.length, true);

                        if (res.saved_file) {
                            showToast(`보고서 작성 & 파일 저장 완료! (${res.saved_file})`, '📄');
                        } else {
                            showToast('AI 심층 분석 보고서 작성이 완료되었습니다!', '✅');
                        }
                    } else {
                        showToast(res.message || '보고서 생성 실패', '❌');
                    }
                } else {
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = '<span>⚡</span> AI 보고서 작성';
                        statusBadge.innerText = '작성 완료';
                        currentReportText = `# ⚾ [${keyword || '야구'}] AI 심층 분석 & 포커스 브리핑 리포트\n\n**분석 대상 기간**: ${startDate} ~ ${endDate}\n\n## 1. [${keyword || '야구'}] 핵심 활약상 3줄 요약\n- 기간 내 '${keyword || '야구'}' 관련 주요 경기 결과 및 출전 데이터 분석 완료\n- 핵심 승부처에서의 활약과 팀 내 기여도 지표 점검\n- 최근 컨디션 페이스 및 향후 경기 관전 포인트 도출\n\n## 2. 일자별 경기 상세 리뷰 & 세부 데이터 분석\n- [최근 경기]: 주요 투타 기록 및 클러치 상황 활약상\n\n## 3. 최근 페이스 및 전력 기여도 분석\n- 안정적인 경기력 유지 및 핵심 전력으로서의 가치 분석 완료`;
                        renderReport(currentReportText);
                        const askBotBtn = document.getElementById('btnAskBotAboutReport');
                        if (askBotBtn) askBotBtn.style.display = 'inline-flex';
                        updateChatContextUI(keyword, currentArticles.length, true);

                        const today = new Date().toISOString().split('T')[0].slice(2).replace(/-/g, '');
                        showToast(`[테스트] 보고서 작성 및 ${keyword || '야구'}_보고서_${today}.md 저장 완료`, '📄');
                    }, 1000);
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡</span> AI 보고서 작성';
                statusBadge.innerText = '오류';
                showToast(`오류: ${err.message || err}`, '❌');
            }
        }

        function renderReport(mdText) {
            const container = document.getElementById('reportOutputContainer');
            
            // 구조화된 Markdown 변환 (헤더, 볼드, 불릿, 번호, 인용, 줄바꿈)
            let html = mdText
                .replace(/^# (.*$)/gim, '<h1 class="report-h1">$1</h1>')
                .replace(/^## (.*$)/gim, '<h2 class="report-h2">$1</h2>')
                .replace(/^### (.*$)/gim, '<h3 class="report-h3">$1</h3>')
                .replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/gim, '<a href="$2" target="_blank" class="report-link" onclick="event.preventDefault(); openExternalLink(\'$2\');" title="$2">$1 ↗</a>')
                .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
                .replace(/^---$/gim, '<hr class="report-hr">')
                .replace(/^> (.*$)/gim, '<blockquote class="report-quote">$1</blockquote>')
                .replace(/^\- (.*$)/gim, '<li class="report-item">$1</li>')
                .replace(/^\* (.*$)/gim, '<li class="report-item">$1</li>')
                .replace(/^(\d+)\. (.*$)/gim, '<li class="report-item-num"><span class="num-badge">$1.</span> <span>$2</span></li>')
                .replace(/\n/gim, '<br>');

            container.innerHTML = `
                <div class="report-preview">
                    <div class="report-header-banner">
                        <span>📊</span>
                        <span>AI 야구 뉴스 심층 분석 리포트 생성이 완료되었습니다.</span>
                    </div>
                    <div class="report-content-body">${html}</div>
                </div>`;
        }

        async function handleSaveReportMd() {
            if (!currentReportText) {
                showToast('먼저 보고서를 작성해주세요.', '⚠️');
                return;
            }

            const keyword = document.getElementById('crawlKeyword').value.trim();

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.save_report_md(keyword);
                    if (res && res.status === 'success') {
                        showToast(res.message || '보고서가 .md 파일로 저장되었습니다!', '📄');
                    } else {
                        showToast(res.message || '보고서 저장 실패', '❌');
                    }
                } else {
                    const today = new Date().toISOString().split('T')[0].slice(2).replace(/-/g, '');
                    showToast(`[테스트] ${keyword || '야구'}_보고서_${today}.md 저장 완료`, '📄');
                }
            } catch (err) {
                showToast(`저장 오류: ${err.message || err}`, '❌');
            }
        }

        // ============================================================
        // 저장된 보고서 (.md) 보관함 열람 로직
        // ============================================================
        function handleOpenSavedReportsModal() {
            const modal = document.getElementById('savedReportsModal');
            if (modal) {
                modal.style.display = 'flex';
                loadSavedReportsList();
            }
        }

        function handleCloseSavedReportsModal(e) {
            if (e && e.target && e.target.id !== 'savedReportsModal' && !e.target.classList.contains('close-btn')) {
                return;
            }
            const modal = document.getElementById('savedReportsModal');
            if (modal) {
                modal.style.display = 'none';
            }
        }

        async function loadSavedReportsList() {
            const container = document.getElementById('savedReportsListContainer');
            const badge = document.getElementById('savedReportsCountBadge');
            if (!container) return;

            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⏳</div>
                    <div class="empty-state-text">저장된 보고서 목록을 불러오는 중...</div>
                </div>`;

            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.list_saved_reports) {
                    const res = await window.pywebview.api.list_saved_reports();
                    if (res && res.status === 'success') {
                        const reports = res.reports || [];
                        if (badge) badge.innerText = `${reports.length}건`;
                        renderSavedReportsList(reports);
                    } else {
                        container.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">⚠️</div>
                                <div class="empty-state-text">${res.message || '보고서 목록 조회 실패'}</div>
                            </div>`;
                    }
                } else {
                    // 브라우저 단독 테스트 모드 더미
                    setTimeout(() => {
                        const dummyReports = [
                            { filename: '이로운_보고서_260910.md', keyword: '이로운', size_kb: 11.6, updated_at: '2026-09-10 17:30' },
                            { filename: '김광현_보고서_260908.md', keyword: '김광현', size_kb: 8.4, updated_at: '2026-09-08 15:20' }
                        ];
                        if (badge) badge.innerText = `${dummyReports.length}건`;
                        renderSavedReportsList(dummyReports);
                    }, 400);
                }
            } catch (err) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">❌</div>
                        <div class="empty-state-text">목록 로딩 오류: ${err.message || err}</div>
                    </div>`;
            }
        }

        function renderSavedReportsList(reports) {
            const container = document.getElementById('savedReportsListContainer');
            if (!container) return;

            if (!reports || reports.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📂</div>
                        <div class="empty-state-text">
                            storage/report/ 폴더에 저장된 보고서가 없습니다.<br>
                            우측 상단의 <strong>[AI 보고서 작성]</strong> 후 저장해보세요.
                        </div>
                    </div>`;
                return;
            }

            let html = '';
            reports.forEach(rep => {
                const kwBadge = rep.keyword ? `<span class="report-meta-chip">🏷️ ${rep.keyword}</span>` : '';
                html += `
                    <div class="saved-report-item">
                        <div class="report-item-info">
                            <div class="report-item-title" title="${rep.filename}">
                                <span>📄</span>
                                <span>${rep.filename}</span>
                            </div>
                            <div class="report-item-meta">
                                ${kwBadge}
                                <span>📅 ${rep.updated_at}</span>
                                <span>💾 ${rep.size_kb} KB</span>
                            </div>
                        </div>
                        <button class="btn-load-report" onclick="handleSelectSavedReport('${rep.filename}')">
                            <span>📖</span> 열람하기
                        </button>
                    </div>`;
            });

            container.innerHTML = html;
        }

        async function handleSelectSavedReport(filename) {
            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.load_saved_report) {
                    const res = await window.pywebview.api.load_saved_report(filename);
                    if (res && res.status === 'success') {
                        currentReportText = res.report_md;
                        renderReport(currentReportText);

                        const statusBadge = document.getElementById('reportStatusBadge');
                        if (statusBadge) statusBadge.innerText = `📂 ${filename}`;

                        const kwInput = document.getElementById('crawlKeyword');
                        if (kwInput && res.keyword && res.keyword !== '야구') {
                            kwInput.value = res.keyword;
                        }

                        const askBotBtn = document.getElementById('btnAskBotAboutReport');
                        if (askBotBtn) askBotBtn.style.display = 'inline-flex';

                        updateChatContextUI(res.keyword || '야구', currentArticles.length, true);
                        handleCloseSavedReportsModal();
                        showToast(`'${filename}' 보고서를 불러왔습니다!`, '📂');
                    } else {
                        showToast(res.message || '보고서 불러오기 실패', '❌');
                    }
                } else {
                    // 브라우저 테스트 모드
                    currentReportText = `# ⚾ [${filename}] 불러온 보고서\n\n**파일명**: ${filename}\n\n## 1. 핵심 활약상 요약\n- storage/report/${filename} 파일의 내용이 정상적으로 렌더링되었습니다.`;
                    renderReport(currentReportText);
                    const statusBadge = document.getElementById('reportStatusBadge');
                    if (statusBadge) statusBadge.innerText = `📂 ${filename}`;
                    handleCloseSavedReportsModal();
                    showToast(`[테스트] '${filename}' 보고서 열람 완료`, '📂');
                }
            } catch (err) {
                showToast(`보고서 로딩 오류: ${err.message || err}`, '❌');
            }
        }

        window.addEventListener('pywebviewready', async () => {
            console.log('pywebview 브릿지가 준비되었습니다.');
            if (window.pywebview && window.pywebview.api && window.pywebview.api.get_context_status) {
                try {
                    const status = await window.pywebview.api.get_context_status();
                    if (status && status.status === 'success') {
                        updateChatContextUI(status.keyword, status.article_count, status.has_report);
                    }
                } catch (e) {
                    console.error('초기 연동 상태 조회 실패:', e);
                }
            }
        });

        // ============================================================
        // 구장별 실시간 날씨 대시보드 및 DB 이력 관리 로직
        // ============================================================
        let weatherViewMode = 'live'; // 'live' | 'history'

        async function switchWeatherMode(mode) {
            weatherViewMode = mode;
            const btnLive = document.getElementById('modeBtn-live');
            const btnHistory = document.getElementById('modeBtn-history');
            const historyBar = document.getElementById('weatherHistoryBar');
            const titleEl = document.getElementById('weatherHeaderTitle');
            const iconEl = document.getElementById('weatherHeaderIcon');
            const refreshBtn = document.getElementById('btnRefreshWeather');

            if (mode === 'live') {
                if (btnLive) btnLive.classList.add('active');
                if (btnHistory) btnHistory.classList.remove('active');
                if (historyBar) historyBar.style.display = 'none';
                if (titleEl) titleEl.innerText = 'KBO 전국 구장 실시간 기상정보';
                if (iconEl) iconEl.innerText = '☀️';
                if (refreshBtn) refreshBtn.style.display = 'inline-flex';
                loadStadiumWeather();
            } else {
                if (btnHistory) btnHistory.classList.add('active');
                if (btnLive) btnLive.classList.remove('active');
                if (historyBar) historyBar.style.display = 'flex';
                if (titleEl) titleEl.innerText = 'KBO 전국 구장 날씨 기록 이력';
                if (iconEl) iconEl.innerText = '📅';
                if (refreshBtn) refreshBtn.style.display = 'none';
                loadWeatherHistoryDates();
            }
        }

        async function loadStadiumWeather(force = false) {
            const btn = document.getElementById('btnRefreshWeather');
            const container = document.getElementById('stadiumWeatherGrid');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span>⏳</span> 조회 중...';
            }

            if (force || !currentStadiumWeather || currentStadiumWeather.length === 0) {
                if (container) {
                    container.innerHTML = `
                        <div class="empty-state" style="grid-column: 1 / -1;">
                            <div class="empty-state-icon">⏳</div>
                            <div class="empty-state-text">기상청에서 전국 11개 야구장 실시간 날씨 데이터를 수신하고 있습니다...</div>
                        </div>`;
                }
            }

            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.get_stadiums_weather) {
                    const res = await window.pywebview.api.get_stadiums_weather();
                    if (res && res.status === 'success') {
                        currentStadiumWeather = res.stadiums || [];
                        weatherLoaded = true;
                        const timeBadge = document.getElementById('weatherTimeBadge');
                        if (timeBadge && res.base_datetime) {
                            timeBadge.innerText = res.base_datetime;
                        }
                        renderStadiumCards();
                        showToast(`전국 ${currentStadiumWeather.length}개 구장 실시간 기상정보 갱신 완료! (DB 자동 보관)`, '☀️');
                    } else {
                        showToast(res.message || '기상청 데이터 조회 실패', '❌');
                    }
                } else {
                    // 브라우저 단독 테스트 모드 더미
                    setTimeout(() => {
                        currentStadiumWeather = [
                            { id: 'jamsil', name: '서울 잠실야구장', team_short: 'LG / 두산', city: '서울 송파', color: '#C30452', temp: '25.0℃', rain: '0.0 mm', humidity: '45%', wind_speed: '2.1 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'gocheok', name: '서울 고척스카이돔', team_short: '키움', city: '서울 구로', color: '#820024', temp: '24.2℃', rain: '0.0 mm', humidity: '48%', wind_speed: '1.5 m/s', is_dome: true, is_secondary: false, icon: '☀️', status_label: '🔵 돔구장', badge_class: 'badge-dome', status_desc: '실내 돔구장으로 날씨와 상관없이 100% 정상 진행됩니다.' },
                            { id: 'munhak', name: '인천 SSG랜더스필드', team_short: 'SSG', city: '인천 미추홀', color: '#CE0E2D', temp: '24.6℃', rain: '0.0 mm', humidity: '50%', wind_speed: '2.5 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'suwon', name: '수원 KT위즈파크', team_short: 'KT', city: '경기 수원', color: '#000000', temp: '25.2℃', rain: '0.0 mm', humidity: '46%', wind_speed: '1.7 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'daejeon', name: '대전 한화생명이글스파크', team_short: '한화', city: '대전 중구', color: '#FF6600', temp: '26.1℃', rain: '0.0 mm', humidity: '42%', wind_speed: '1.8 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'daegu', name: '대구 삼성라이온즈파크', team_short: '삼성', city: '대구 수성', color: '#074CA1', temp: '27.3℃', rain: '0.0 mm', humidity: '40%', wind_speed: '2.0 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'gwangju', name: '광주-기아 챔피언스필드', team_short: 'KIA', city: '광주 북구', color: '#EA0029', temp: '26.5℃', rain: '0.0 mm', humidity: '44%', wind_speed: '1.9 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'sajik', name: '부산 사직야구장', team_short: '롯데', city: '부산 동래', color: '#002955', temp: '25.8℃', rain: '0.0 mm', humidity: '53%', wind_speed: '2.8 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'changwon', name: '창원 NC파크', team_short: 'NC', city: '경남 창원', color: '#315288', temp: '26.0℃', rain: '0.0 mm', humidity: '49%', wind_speed: '2.2 m/s', is_dome: false, is_secondary: false, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'pohang', name: '포항야구장 (제2구장)', team_short: '삼성 (제2구장)', city: '경북 포항', color: '#074CA1', temp: '24.8℃', rain: '0.0 mm', humidity: '55%', wind_speed: '3.2 m/s', is_dome: false, is_secondary: true, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' },
                            { id: 'ulsan', name: '울산문수야구장 (제2구장)', team_short: '롯데 / 울산', city: '울산 남구', color: 'linear-gradient(90deg, #002955 50%, #c70000 50%)', temp: '25.4℃', rain: '0.0 mm', humidity: '52%', wind_speed: '2.0 m/s', is_dome: false, is_secondary: true, icon: '☀️', status_label: '🟢 정상 진행 가능', badge_class: 'badge-safe', status_desc: '강수가 없어 쾌적하게 경기가 진행될 예정입니다.' }
                        ];
                        weatherLoaded = true;
                        renderStadiumCards();
                        showToast('전국 11개 구장 날씨 조회 완료 (테스트)', '☀️');
                    }, 600);
                }
            } catch (e) {
                showToast(`날씨 조회 오류: ${e.message || e}`, '❌');
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span>🔄</span> 새로고침';
                }
            }
        }

        async function loadWeatherHistoryDates() {
            const select = document.getElementById('selectWeatherHistoryDate');
            const badge = document.getElementById('weatherHistoryCountBadge');
            if (!select) return;

            select.innerHTML = '<option value="">기록 불러오는 중...</option>';

            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.get_weather_history_dates) {
                    const res = await window.pywebview.api.get_weather_history_dates();
                    if (res && res.status === 'success' && res.dates && res.dates.length > 0) {
                        select.innerHTML = res.dates.map(d => 
                            `<option value="${d.base_date}|${d.base_time}">${d.base_date} ${d.base_time} (${d.count}개 구장)</option>`
                        ).join('');
                        if (badge) badge.innerText = `저장된 회차: 총 ${res.dates.length}회`;
                        // 가장 최신 이력 자동 로드
                        loadSelectedWeatherHistory();
                    } else {
                        select.innerHTML = '<option value="">저장된 날씨 기록이 없습니다.</option>';
                        if (badge) badge.innerText = '저장된 기록: 0건';
                        showToast('아직 DB에 저장된 과거 날씨 기록이 없습니다. [현재 날씨 DB 저장]을 눌러보세요.', 'ℹ️');
                    }
                } else {
                    select.innerHTML = '<option value="2026-09-11|15:00">2026-09-11 15:00 (11개 구장)</option>';
                }
            } catch (err) {
                select.innerHTML = '<option value="">기록 조회 실패</option>';
            }
        }

        function onWeatherHistorySelectChange() {
            loadSelectedWeatherHistory();
        }

        async function loadSelectedWeatherHistory() {
            const select = document.getElementById('selectWeatherHistoryDate');
            const container = document.getElementById('stadiumWeatherGrid');
            if (!select || !select.value) return;

            const [baseDate, baseTime] = select.value.split('|');
            if (!baseDate || !baseTime) return;

            if (container) {
                container.innerHTML = `
                    <div class="empty-state" style="grid-column: 1 / -1;">
                        <div class="empty-state-icon">⏳</div>
                        <div class="empty-state-text">${baseDate} ${baseTime} 관측 기록을 불러오고 있습니다...</div>
                    </div>`;
            }

            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.get_weather_history) {
                    const res = await window.pywebview.api.get_weather_history(baseDate, baseTime);
                    if (res && res.status === 'success' && res.stadiums) {
                        // 기존 구장 메타데이터(color, team_short, city 등) 병합
                        const stdMetaMap = {
                            jamsil: { team_short: 'LG / 두산', city: '서울 송파', color: '#C30452', is_dome: false, is_secondary: false },
                            gocheok: { team_short: '키움', city: '서울 구로', color: '#820024', is_dome: true, is_secondary: false },
                            munhak: { team_short: 'SSG', city: '인천 미추홀', color: '#CE0E2D', is_dome: false, is_secondary: false },
                            suwon: { team_short: 'KT', city: '경기 수원', color: '#000000', is_dome: false, is_secondary: false },
                            daejeon: { team_short: '한화', city: '대전 중구', color: '#FF6600', is_dome: false, is_secondary: false },
                            daegu: { team_short: '삼성', city: '대구 수성', color: '#074CA1', is_dome: false, is_secondary: false },
                            gwangju: { team_short: 'KIA', city: '광주 북구', color: '#EA0029', is_dome: false, is_secondary: false },
                            sajik: { team_short: '롯데', city: '부산 동래', color: '#002955', is_dome: false, is_secondary: false },
                            changwon: { team_short: 'NC', city: '경남 창원', color: '#315288', is_dome: false, is_secondary: false },
                            pohang: { team_short: '삼성 (제2구장)', city: '경북 포항', color: '#074CA1', is_dome: false, is_secondary: true },
                            ulsan: { team_short: '롯데 / 울산', city: '울산 남구', color: 'linear-gradient(90deg, #002955 50%, #c70000 50%)', is_dome: false, is_secondary: true },
                        };

                        currentStadiumWeather = res.stadiums.map(item => {
                            const meta = stdMetaMap[item.stadium_id] || {};
                            return {
                                id: item.stadium_id,
                                name: item.stadium_name,
                                temp: item.temp_str || (item.temp ? `${item.temp}℃` : '--'),
                                rain: `${item.rain || 0.0} mm`,
                                humidity: item.humidity ? `${item.humidity}%` : '--',
                                wind_speed: `${item.wind_speed || 0.0} m/s`,
                                icon: item.icon || '☀️',
                                status_label: item.status_label || '🟢 정상 진행 가능',
                                badge_class: item.badge_class || 'badge-safe',
                                status_desc: item.status_desc || '관측 기록 보관 데이터',
                                team_short: meta.team_short || '',
                                city: meta.city || '',
                                color: meta.color || '#333333',
                                is_dome: meta.is_dome || false,
                                is_secondary: meta.is_secondary || false,
                            };
                        });

                        const timeBadge = document.getElementById('weatherTimeBadge');
                        if (timeBadge) {
                            timeBadge.innerText = `${baseDate} ${baseTime} 관측 기록`;
                        }
                        renderStadiumCards();
                        showToast(`${baseDate} ${baseTime} 날씨 이력 (${currentStadiumWeather.length}개 구장) 로드 완료!`, '📋');
                    } else {
                        showToast(res.message || '해당 시간대 날씨 기록이 없습니다.', '⚠️');
                    }
                }
            } catch (err) {
                showToast(`이력 로드 실패: ${err.message || err}`, '❌');
            }
        }

        async function saveCurrentWeatherToDatabase() {
            const btn = document.getElementById('btnSaveWeatherDb');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span>⏳</span> 저장 중...';
            }

            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.save_current_weather_record) {
                    const res = await window.pywebview.api.save_current_weather_record();
                    if (res && res.status === 'success') {
                        showToast(`💾 전국 11개 구장 현재 날씨 DB 저장 완료! (${res.base_date} ${res.base_time})`, '✅');
                        if (weatherViewMode === 'history') {
                            loadWeatherHistoryDates();
                        }
                    } else {
                        showToast(res.message || '날씨 DB 저장 실패', '❌');
                    }
                } else {
                    showToast('현재 환경에서는 DB 저장을 지원하지 않습니다 (테스트 모드)', 'ℹ️');
                }
            } catch (e) {
                showToast(`저장 오류: ${e.message || e}`, '❌');
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span>💾</span> 현재 날씨 DB 저장';
                }
            }
        }

        function filterStadiums(filterType) {
            currentWeatherFilter = filterType;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            const target = document.getElementById(`filterBtn-${filterType}`);
            if (target) target.classList.add('active');
            renderStadiumCards();
        }

        function renderStadiumCards() {
            const container = document.getElementById('stadiumWeatherGrid');
            if (!container) return;

            let list = currentStadiumWeather || [];
            if (currentWeatherFilter === 'main') {
                list = list.filter(s => !s.is_secondary);
            } else if (currentWeatherFilter === 'secondary') {
                list = list.filter(s => s.is_secondary);
            }

            if (list.length === 0) {
                container.innerHTML = `
                    <div class="empty-state" style="grid-column: 1 / -1;">
                        <div class="empty-state-icon">🔍</div>
                        <div class="empty-state-text">해당 조건에 맞는 구장 정보가 없습니다.</div>
                    </div>`;
                return;
            }

            let html = '';
            list.forEach(s => {
                const topBarColor = s.color || '#0f2b5c';
                const teamTagStyle = `background: ${s.color || '#0f2b5c'};`;
                html += `
                    <div class="stadium-card">
                        <div class="stadium-card-top-bar" style="background: ${topBarColor};"></div>
                        <div class="stadium-card-header">
                            <div class="stadium-info">
                                <div class="stadium-name">
                                    <span>${s.name}</span>
                                </div>
                                <div class="stadium-city">📍 ${s.city}</div>
                            </div>
                            <span class="team-tag" style="${teamTagStyle}">${s.team_short}</span>
                        </div>

                        <div class="stadium-card-main">
                            <div class="weather-temp-wrap">
                                <span class="weather-large-icon">${s.icon || '☀️'}</span>
                                <span class="weather-temp">${s.temp || '--'}</span>
                            </div>
                            <span class="game-status-badge ${s.badge_class || 'badge-safe'}">
                                ${s.status_label || '정상 진행'}
                            </span>
                        </div>

                        <div class="stadium-metrics-grid">
                            <div class="metric-chip">
                                <span class="metric-label">🌧️ 강수량</span>
                                <span class="metric-value">${s.rain || '0.0 mm'}</span>
                            </div>
                            <div class="metric-chip">
                                <span class="metric-label">💧 습도</span>
                                <span class="metric-value">${s.humidity || '--'}</span>
                            </div>
                            <div class="metric-chip">
                                <span class="metric-label">💨 풍속</span>
                                <span class="metric-value">${s.wind_speed || '0.0 m/s'}</span>
                            </div>
                        </div>

                        <div class="stadium-card-footer">
                            <span>ℹ️</span>
                            <span>${s.status_desc || '정상 경기 가능 상태입니다.'}</span>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        }
