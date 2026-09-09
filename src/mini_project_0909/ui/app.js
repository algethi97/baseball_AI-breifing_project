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
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            
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

            const keyword = document.getElementById('crawlKeyword').value.trim();

            try {
                if (window.pywebview && window.pywebview.api) {
                    const res = await window.pywebview.api.export_articles_csv(keyword);
                    if (res && res.status === 'success') {
                        showToast(res.message || 'CSV 파일이 성공적으로 저장되었습니다!', '💾');
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
                        currentReportText = `# ⚾ KBO 야구 뉴스 AI 브리핑 보고서\n\n**분석 기간**: ${startDate} ~ ${endDate}\n\n## 1. 핵심 3줄 요약\n- 수집된 기사를 기반으로 경기 및 선수단 주요 이슈 분석 완료\n- 선발 마운드와 클러치 타선의 활약이 주요 화두로 부상\n- 순위 다툼이 치열해짐에 따라 경기별 불펜 운용이 승패 좌우\n\n## 2. 세부 이슈 및 시사점\n- 주요 선수들의 부상 복귀와 엔트리 변동 체크 필요\n- 향후 잔여 경기 일정에 따른 맞춤형 전략 수립 전망`;
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
                .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
                .replace(/^\- (.*$)/gim, '<li>$1</li>')
                .replace(/\n/gim, '<br>');

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
