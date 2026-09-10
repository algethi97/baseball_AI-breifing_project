# ⚾ KBO 야구 뉴스 AI 브리핑 & 전국 구장 실시간 기상 분석 시스템
> **Baseball AI Briefing & Stadium Weather Analysis Platform**

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/package%20manager-uv-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Release](https://img.shields.io/badge/release-v1.2.1-green.svg)](https://github.com/algethi97/baseball_AI-breifing_project/releases)

---

## 📌 프로젝트 소개 (Overview)

본 프로젝트는 프로야구(KBO) 팬과 코칭스태프, 데이터 분석가를 위한 **올인원(All-in-One) 야구 전문 AI 데스크톱 애플리케이션**입니다.

네이버 스포츠 뉴스를 실시간으로 대량 수집하고, OpenAI 최신 LLM을 결합하여 심층 브리핑 보고서를 자동 생성하며, 기상청 공공데이터를 통해 전국 11개 프로야구 구장의 실시간 기상 관측 데이터 및 **우천 취소 우려 지수**를 직관적인 대시보드로 제공합니다.

---

## 🚀 주요 핵심 기능 (Key Features)

### 1. 💬 KBO 야구 전문 AI 챗봇 (Interactive AI Assistant)
- **KBO 맞춤형 질의응답**: 경기 규칙, 구단 역사, 선수 기록, 최신 리그 이슈에 대한 실시간 지식 브리핑
- **기사 & 보고서 실시간 지식 연동 (Dynamic Knowledge Injection)**:
  - 수집된 기사 목록(최대 200건)과 AI가 생성한 마크다운 보고서 전문이 챗봇의 지식 베이스로 실시간 자동 주입
  - *"방금 수집한 기사 중에서 홈런 친 선수 있어?"*, *"보고서의 2번 경기 리뷰를 더 쉽게 설명해줘"*와 같은 심층 후속 Q&A 지원
- **연동 상태 배너 & 맞춤형 퀵 질문**:
  - 참조 중인 기사/보고서 상태를 실시간 배너(`⚪ 일반 모드`, `🔵 기사 참조 중`, `🟢 보고서 연동 완료`)로 시각화
  - 상황에 맞추어 `[📄 보고서 핵심 요약]`, `[⚾ 경기별 승부처]` 등의 추천 질문 동적 제공

### 2. 📰 네이버 스포츠 실시간 스마트 크롤러 (Sports News Crawler)
- **일자별 스마트 분할 수집**: 포털 검색의 10페이지(100건) 제한을 극복하기 위해 일자별 분할 순회를 적용하여 **최대 200건**의 기사를 균등하게 수집
- **안정적인 수집 파이프라인**: 403 Rate Limit 방지를 위한 세션 관리 및 재시도 로직, 상대 시간("3일 전" 등) 역산 알고리즘 탑재
- **원클릭 데이터 내보내기 (CSV)**: 수집된 원본 기사 속성을 완벽히 보존하며 `storage/csv/{키워드}_기사수집_{YYMMDD}_{HHMMSS}.csv` 파일로 즉시 저장 (UTF-8-SIG 인코딩 적용으로 엑셀 한글 깨짐 방지)

### 3. 📝 AI 심층 뉴스 요약 보고서 엔진 (AI News Report Engine)
- **수집 기사 100% 종합 분석**: 발췌된 일부 기사가 아닌 수집된 전체 기사(최대 200건)의 시간 흐름과 핵심 사건을 빠짐없이 분석
- **경기 일자 명확 기재**: 경기 리뷰 및 선수 활약상 서술 시 구체적인 경기 일자(예: *"9월 8일 경기에서는..."*)를 문장에 필수 명시
- **마크다운(`.md`) 파일 내보내기**:
  - `[⚡ 맞춤 보고서 작성]` 클릭 시 화면에 즉시 렌더링되며, 상단의 `[💾 보고서 MD 저장]` 버튼 클릭 시 `storage/report/{키워드}_보고서_{YYMMDD}.md` 파일로 깔끔하게 1회 저장
  - 동일 날짜 중복 생성 시 시간(`_{HHMMSS}`)을 덧붙여 기존 보고서 덮어쓰기 방지
- **챗봇 연계 버튼**: 보고서 상단의 `[💬 챗봇에 질문하기]` 버튼으로 원클릭 질의 연계

### 4. 🗄️ 설계안 B 기반 고속 SQLite 데이터베이스 추출 엔진 (Database Engine)
- **관계형 정규화 스키마 (설계안 B)**:
  - `search_queries`(수집 세션 이력) ↔ `article_keywords`(다대다 매핑) ↔ `articles`(기사 본문 및 발췌 Snippet) ↔ `ai_reports`(보고서 이력)로 구성된 4개 정규화 테이블 모델
  - 기사 URL 고유 제약조건(`UNIQUE`)으로 중복 적재 방지 및 외래키(`FOREIGN KEY`) 무결성 보장
- **SQLite PRAGMA 고속 엔진 튜닝**:
  - `PRAGMA synchronous = OFF;` (디스크 동기화 대기 시간 제거로 쓰기 속도 극대화)
  - `PRAGMA journal_mode = WAL;`, `cache_size = 10000`, `temp_store = MEMORY` 적용
  - **단일 원자적 트랜잭션** 벌크 적재를 통해 **16건 기준 약 1.99ms(0.002초)**의 초고속 데이터베이스 생성
- **형식별 파일 보관 구조화 (`storage/`)**:
  - `[🗄️ 데이터베이스 추출]` 버튼 클릭 시 `storage/db/{키워드}_데이터베이스_{날짜}_{시간}.db` 파일로 독립 추출
  - SQLite 부속 저널 파일(`-wal`, `-shm`) 및 누적 통합 DB(`baseball_news.db`)가 모두 `storage/db/` 폴더에 함께 안전하게 보관
  - `python -m sqlite3` CLI를 통한 무결성 정합성 자동 검증

### 5. ☀️ KBO 전국 11개 구장 실시간 기상정보 대시보드 (Stadium Weather Dashboard)
- **기상청 초단기실황 API 연동**:
  - 전국 11개 구장(정규 9개 구장 + 제2구장 2개)의 기상청 공식 격자 좌표(`nx`, `ny`) 매핑
  - 매시 40분 데이터 생성 주기에 맞춘 발표시각 자동 보정으로 무결점 데이터 조회
  - 실시간 기온(`℃`), 1시간 강수량(`mm`), 습도(`%`), 풍속(`m/s`) 표출
- **지원 구장 목록 (총 11개 구장)**:
  - 서울 잠실야구장 (LG / 두산)
  - 서울 고척스카이돔 (키움 히어로즈)
  - 인천 SSG랜더스필드 (SSG 랜더스)
  - 수원 KT위즈파크 (kt wiz)
  - 대전 한화생명이글스파크 (한화 이글스)
  - 대구 삼성라이온즈파크 (삼성 라이온즈)
  - 광주-기아 챔피언스필드 (KIA 타이거즈)
  - 부산 사직야구장 (롯데 자이언츠)
  - 창원 NC파크 (NC 다이노스)
  - **포항야구장 (삼성 라이온즈 제2구장)**
  - **울산문수야구장 (롯데 제2구장 & 울산 웨일즈 홈)**
- **야구 특화 '우천 취소 우려 지수' 판정**:
  - `🔵 돔구장`: 실내 돔구장으로 기상과 무관하게 100% 정상 진행
  - `🟢 정상 진행 가능`: 강수 없음 및 안정적 풍속
  - `🟡 우천 주의`: 약한 비 또는 빗방울 관측 (방수포 대기 및 경기 개시 관망)
  - `🔴 우천 취소 우려`: 시간당 5mm 이상의 많은 비
  - `⚠️ 강풍 주의`: 풍속 10m/s 이상의 강풍 관측
- **울산문수야구장 상징색 50:50 반반 분할**:
  - 롯데 자이언츠 네이비(`#002955`)와 울산 웨일즈 레드(`#c70000`)의 반반 그라데이션 적용
- **구장 필터링 및 새로고침**: 전체 구장(11), 정규 구장(9), 제2구장(2) 필터 버튼 및 실시간 `[🔄 날씨 새로고침]` 지원

---

## 🛠️ 기술 스택 (Tech Stack)

| 구분 | 기술 / 라이브러리 | 설명 |
| :--- | :--- | :--- |
| **Language** | Python 3.12+ | 핵심 백엔드 비즈니스 로직 및 크롤러 |
| **GUI Framework** | pywebview (6.2+) | 경량 네이티브 윈도우 데스크톱 웹뷰 컨테이너 |
| **Package Manager**| uv | 초고속 Python 패키지 및 가상환경 관리 |
| **Database** | SQLite 3 | 관계형 정규화 모델(설계안 B), PRAGMA 엔진 튜닝(WAL) 기반 초고속 데이터 적재 |
| **AI / LLM** | OpenAI API (`gpt-5.6-luna`) | 대화형 챗봇 및 종합 분석 리포트 생성 |
| **Web Scraping** | Requests, BeautifulSoup4 | 네이버 스포츠 야구 기사 실시간 크롤링 |
| **Data Processing**| Pandas | 수집 기사 정형화 및 CSV 추출 |
| **Public API** | 공공데이터포털 기상청 단기예보 API | 전국 야구장 초단기실황 기상 데이터 수집 |
| **Frontend** | HTML5, Modern CSS3, Vanilla JS | 반응형 분할 뷰, 카드 그리드 대시보드 |

---

## 📂 프로젝트 구조 (Project Structure)

```
mini-project_0909/
├── src/
│   └── mini_project_0909/
│       ├── __init__.py
│       ├── app.py              # 데스크톱 애플리케이션 진입점 (pywebview 구동)
│       ├── api.py              # JS-Python 브릿지 API (챗봇, 보고서, CSV, DB, 날씨 연동)
│       ├── crawler.py          # 네이버 스포츠 뉴스 스마트 크롤러
│       ├── database.py         # 설계안 B 기반 고속 SQLite DB 적재 및 정규화 스키마 관리 모듈
│       ├── weather.py          # 기상청 단기예보 API 연동 및 11개 구장 날씨 분석 모듈
│       └── ui/
│           ├── index.html      # 3개 탭 반응형 인터페이스 마크업
│           ├── style.css       # 모던 디자인 시스템 및 구장 카드 그리드 스타일
│           └── app.js          # 프론트엔드 상태 관리 및 이벤트 핸들링
├── storage/                    # 형식별 데이터 추출 기본 보관 디렉터리
│   ├── csv/                    # 수집 기사 CSV 내보내기 파일 보관
│   ├── db/                     # 추출된 독립 SQLite DB 및 부속 저널 파일(-wal, -shm) 보관
│   └── report/                 # AI 생성 브리핑 마크다운 보고서 보관
├── pyproject.toml              # 프로젝트 의존성 명세 (uv)
├── uv.lock                     # 패키지 락 파일
├── .gitignore                  # Git 추적 제외 목록 (.db, .csv 등)
├── .env.example                # 환경변수 템플릿
└── README.md                   # 프로젝트 상세 문서
```

---

## ⚡ 빠른 시작 (Getting Started)

### 1. 사전 요구사항 (Prerequisites)
- [Python 3.12](https://www.python.org/) 이상
- [uv](https://docs.astral.sh/uv/) 패키지 관리자 설치

```bash
# Windows (PowerShell) uv 설치
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 저장소 복제 및 의존성 설치
```bash
git clone https://github.com/algethi97/baseball_AI-breifing_project.git
cd baseball_AI-breifing_project

# uv를 통한 가상환경 생성 및 의존성 동기화
uv sync
```

### 3. 환경변수 설정 (`.env`)
프로젝트 루트 경로에 `.env` 파일을 생성하고 필요한 API 키를 입력합니다:

```env
# OpenAI API 키
OPENAI_API_KEY=your_openai_api_key_here

# 공공데이터포털(data.go.kr) 기상청_단기예보 조회서비스 일반 인증키
DATA_GO_KR_API_KEY=your_data_go_kr_service_key_here
```

### 4. 프로그램 실행
```bash
uv run python src/mini_project_0909/app.py
```

---

## 📋 버전 이력 (Release History)

- **`v1.2.1`** (2026-09-10)
  - 추출 데이터 보관 체계화: `storage/` 하위 형식별 디렉터리(`csv/`, `db/`, `report/`) 자동 분류 저장
  - 보고서 저장 UX 개선: 보고서 작성 시 무조건 자동 저장되던 중복 로직을 제거하고, `[💾 보고서 MD 저장]` 버튼 클릭 시 1회 저장되도록 분리
  - 불필요한 `.sql` 자동 생성 로직 제거 및 순수 `.db` 파일 단독 추출 구조 확립
- **`v1.2.0`** (2026-09-10)
  - 설계안 B 기반 관계형 정규화 SQLite 데이터베이스(`database.py`) 추출 엔진 신설 (4개 테이블: `search_queries`, `articles`, `article_keywords`, `ai_reports`)
  - SQLite PRAGMA 엔진 튜닝(`synchronous=OFF`, `journal_mode=WAL`, `cache_size=10000`)으로 초고속(1.99ms) 원자적 벌크 적재 구현
  - UI 상단 `[🗄️ 데이터베이스 추출]` 버튼 및 실시간 토스트 알림 추가
- **`v1.1.1`** (2026-09-09)
  - 고척스카이돔 상태 뱃지 아이콘/텍스트 간소화 (`🔵 돔구장`)
  - 울산문수야구장(롯데 2구장 & 울산 웨일즈) 50:50 반반 상징색 그라데이션 적용
- **`v1.1.0`** (2026-09-09)
  - KBO 전국 11개 프로야구 구장(포항, 울산 문수 제2구장 포함) 실시간 날씨 대시보드 탭 신설
  - 기상청 초단기실황 API 연동 및 야구 특화 '우천 취소 우려 지수' 판정 로직 탑재
- **`v1.0.0`** (2026-09-09)
  - KBO 뉴스 브리핑 & 분석 시스템 초기 공식 릴리스
  - 네이버 스포츠 뉴스 최대 200건 크롤링 및 CSV 추출
  - AI 종합 보고서 마크다운(`.md`) 자동 저장 (`키워드_보고서_추출날짜.md`)
  - 챗봇 지식 베이스 실시간 연동 및 동적 퀵 질문 지원

---

## 📄 라이선스 (License)

This project is licensed under the MIT License.

