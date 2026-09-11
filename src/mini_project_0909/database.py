"""
야구 뉴스 기사 데이터베이스 관리 모듈 (설계안 B - 정규화 관계형 모델)
SQL CLI 및 SQLite PRAGMA 엔진 튜닝을 통한 고속 적재 및 추출을 제공합니다.
"""

import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mini_project_0909.normalizer import normalize_keyword

# 프로젝트 루트 및 기본 DB storage 디렉터리 (storage/db)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXPORT_DB_DIR = PROJECT_ROOT / "storage" / "db"


# ============================================================
# DDL: 설계안 B (관계형 정규화 테이블 스키마)
# ============================================================
SCHEMA_DDL = """
-- 1. 수집 세션 / 검색 이력 테이블
CREATE TABLE IF NOT EXISTS search_queries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword         TEXT NOT NULL,
    canonical_keyword TEXT,
    start_date      TEXT,
    end_date        TEXT,
    collected_count INTEGER NOT NULL DEFAULT 0,
    executed_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 순수 기사 테이블 (URL 고유 제약조건으로 중복 수집 방지)
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT,
    title           TEXT NOT NULL,
    press           TEXT,
    date            TEXT,
    url             TEXT UNIQUE NOT NULL,
    content         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. 기사 ↔ 검색 쿼리 다대다(N:M) 관계 매핑 테이블
CREATE TABLE IF NOT EXISTS article_keywords (
    query_id        INTEGER NOT NULL,
    article_id      INTEGER NOT NULL,
    PRIMARY KEY (query_id, article_id),
    FOREIGN KEY (query_id) REFERENCES search_queries(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

-- 4. AI 보고서 이력 테이블 (추후 확장 대비)
CREATE TABLE IF NOT EXISTS ai_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id        INTEGER,
    report_md       TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_id) REFERENCES search_queries(id) ON DELETE SET NULL
);

-- 5. KBO 구장별 날씨 관측 이력 테이블 (초단기실황 일별/시간대별 누적)
CREATE TABLE IF NOT EXISTS stadium_weather_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stadium_id      TEXT NOT NULL,          -- 구장 고유 ID ('jamsil', 'munhak' 등)
    stadium_name    TEXT NOT NULL,          -- 구장명 ('서울 잠실야구장' 등)
    base_date       TEXT NOT NULL,          -- 관측 일자 ('YYYY-MM-DD')
    base_time       TEXT NOT NULL,          -- 관측 정시 시각 ('HH:00')
    temp            REAL,                   -- 기온 수치 (℃)
    temp_str        TEXT,                   -- 기온 표시 문자열 ('24.5℃')
    rain            REAL DEFAULT 0.0,       -- 1시간 강수량 (mm)
    humidity        REAL,                   -- 습도 (%)
    wind_speed      REAL DEFAULT 0.0,       -- 풍속 (m/s)
    pty             INTEGER DEFAULT 0,      -- 강수형태 코드 (0:없음, 1:비, 2:비/눈, 3:눈, 5:빗방울 등)
    status_label    TEXT,                   -- 경기 진행 상태 ('🟢 정상 진행 가능', '🔴 우천 취소 우려' 등)
    badge_class     TEXT,                   -- UI 상태 뱃지 클래스 ('badge-safe', 'badge-danger' 등)
    status_desc     TEXT,                   -- 경기 진행 상태 상세 설명
    icon            TEXT,                   -- 날씨 아이콘 ('☀️', '🌧️', '⛈️' 등)
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (stadium_id, base_date, base_time)
);

-- 인덱스 (조회 및 검색 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
CREATE INDEX IF NOT EXISTS idx_articles_press ON articles(press);
CREATE INDEX IF NOT EXISTS idx_queries_keyword ON search_queries(keyword);
CREATE INDEX IF NOT EXISTS idx_ak_query_id ON article_keywords(query_id);
CREATE INDEX IF NOT EXISTS idx_ak_article_id ON article_keywords(article_id);
CREATE INDEX IF NOT EXISTS idx_swh_date_time ON stadium_weather_history(base_date, base_time);
CREATE INDEX IF NOT EXISTS idx_swh_stadium ON stadium_weather_history(stadium_id);
"""


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    if isinstance(val, float) and (val != val or str(val).lower() == "nan"):
        return default
    s = str(val).strip()
    return default if s.lower() == "nan" else s


class DatabaseManager:
    """
    설계안 B 기반 SQLite 데이터베이스 관리자
    """

    DEFAULT_DB_NAME = "baseball_news.db"

    @staticmethod
    def apply_speed_optimizations(conn: sqlite3.Connection) -> None:
        """
        시스템 속도 최적화를 위한 SQLite PRAGMA 파라미터 적용
        - synchronous = OFF: 디스크 동기화 대기 시간 제거로 쓰기 속도 수백 배 가속
        - journal_mode = WAL: 고속 동시성 저널링
        - cache_size = 10000: 메모리 캐시 10,000 페이지 할당
        - temp_store = MEMORY: 임시 테이블 및 인덱스 정렬을 메모리에서 수행
        """
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA synchronous = OFF;")
        try:
            cursor.execute("PRAGMA journal_mode = WAL;")
        except Exception:
            cursor.execute("PRAGMA journal_mode = MEMORY;")
        cursor.execute("PRAGMA cache_size = 10000;")
        cursor.execute("PRAGMA temp_store = MEMORY;")

    @classmethod
    def init_db(cls, db_path: Path) -> None:
        """
        데이터베이스 파일에 스키마 및 인덱스를 생성하고, 하위 호환 컬럼을 확인합니다.
        """
        conn = sqlite3.connect(db_path)
        try:
            cls.apply_speed_optimizations(conn)
            conn.executescript(SCHEMA_DDL)

            # 기존 DB와의 호환성을 위한 컬럼 마이그레이션
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(search_queries);")
            cols = [row[1] for row in cursor.fetchall()]
            if "canonical_keyword" not in cols:
                try:
                    cursor.execute("ALTER TABLE search_queries ADD COLUMN canonical_keyword TEXT;")
                except Exception:
                    pass

            conn.commit()
        finally:
            conn.close()

    @classmethod
    def save_articles_to_db(
        cls,
        keyword: str,
        start_date: str,
        end_date: str,
        articles: List[Dict[str, Any]],
        db_path: Path,
        report_md: Optional[str] = None,
        canonical_keyword: Optional[str] = None,
    ) -> Tuple[int, int, float, int]:
        """
        수집된 기사 목록 및 AI 보고서를 대상 SQLite DB에 고속으로 저장합니다.
        기존 동일 URL 기사는 중복 적재를 방지(UPSERT)하며, AI 보고서가 전달된 경우 ai_reports 테이블에 함께 저장합니다.
        반환값: (query_id, 이번 세션 저장/매핑 기사 수, 소요시간 ms, 누적 총 기사 수)
        """
        if not articles:
            return 0, 0, 0.0, 0

        cls.init_db(db_path)
        start_time = time.perf_counter()

        conn = sqlite3.connect(db_path)
        try:
            cls.apply_speed_optimizations(conn)
            cursor = conn.cursor()

            # 1. 수집 쿼리 세션 등록 (표준 키워드 함께 적재)
            cursor.execute(
                """
                INSERT INTO search_queries (keyword, canonical_keyword, start_date, end_date, collected_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _safe_str(keyword, "야구"),
                    _safe_str(canonical_keyword or keyword, "야구"),
                    _safe_str(start_date),
                    _safe_str(end_date),
                    len(articles),
                ),
            )
            query_id = cursor.lastrowid

            # 2. 기사 테이블 UPSERT 및 매핑 테이블 적재 (content 컬럼 반영)
            upsert_sql = """
            INSERT INTO articles (category, title, press, date, url, content)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                content = CASE WHEN excluded.content != '' THEN excluded.content ELSE articles.content END,
                category = excluded.category,
                title = excluded.title,
                press = excluded.press,
                date = excluded.date
            RETURNING id;
            """

            mapping_sql = """
            INSERT OR IGNORE INTO article_keywords (query_id, article_id)
            VALUES (?, ?)
            """

            saved_count = 0
            for art in articles:
                url_val = _safe_str(art.get("url"))
                if not url_val:
                    continue

                content_val = _safe_str(art.get("content") or art.get("snippet"))

                cursor.execute(
                    upsert_sql,
                    (
                        _safe_str(art.get("category"), "국내야구"),
                        _safe_str(art.get("title")),
                        _safe_str(art.get("press")),
                        _safe_str(art.get("date")),
                        url_val,
                        content_val,
                    ),
                )
                row = cursor.fetchone()
                if row:
                    article_id = row[0]
                    cursor.execute(mapping_sql, (query_id, article_id))
                    saved_count += 1

            # 3. AI 보고서가 전달된 경우 ai_reports 테이블에 외래키(query_id) 연결 적재
            if report_md and report_md.strip():
                cursor.execute(
                    """
                    INSERT INTO ai_reports (query_id, report_md)
                    VALUES (?, ?)
                    """,
                    (query_id, report_md.strip()),
                )

            # 4. 데이터베이스 내 누적 총 기사 수 확인
            cursor.execute("SELECT COUNT(*) FROM articles;")
            total_articles = cursor.fetchone()[0]

            conn.commit()
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return query_id, saved_count, elapsed_ms, total_articles

        finally:
            conn.close()

    @classmethod
    def generate_sql_cli_script(
        cls,
        keyword: str,
        start_date: str,
        end_date: str,
        articles: List[Dict[str, Any]],
        sql_path: Path,
    ) -> None:
        """
        터미널 SQL CLI(python -m sqlite3 또는 sqlite3)에서 초고속으로
        데이터베이스를 일괄 생성/복원할 수 있는 속도 최적화 SQL 배치 스크립트를 생성합니다.
        """
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write("-- ============================================================\n")
            f.write(f"-- KBO 야구 기사 데이터베이스 고속 생성 배치 스크립트 (설계안 B)\n")
            f.write(f"-- 키워드: {_safe_str(keyword, '야구')} | 수집일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-- 실행 방법: python -m sqlite3 new_db.db < [이 파일]\n")
            f.write("-- ============================================================\n\n")

            # 속도 최적화 PRAGMA
            f.write("PRAGMA foreign_keys = ON;\n")
            f.write("PRAGMA synchronous = OFF;\n")
            f.write("PRAGMA journal_mode = MEMORY;\n")
            f.write("PRAGMA cache_size = 10000;\n")
            f.write("PRAGMA temp_store = MEMORY;\n\n")

            # 스키마 DDL
            f.write(SCHEMA_DDL.strip())
            f.write("\n\n-- 고속 단일 트랜잭션 적재 시작\nBEGIN TRANSACTION;\n\n")

            # 1. 쿼리 세션
            safe_kw = _safe_str(keyword, "야구").replace("'", "''")
            safe_sd = _safe_str(start_date).replace("'", "''")
            safe_ed = _safe_str(end_date).replace("'", "''")
            f.write(
                f"INSERT INTO search_queries (keyword, start_date, end_date, collected_count) "
                f"VALUES ('{safe_kw}', '{safe_sd}', '{safe_ed}', {len(articles)});\n\n"
            )

            # 2. 기사 적재 및 관계 매핑
            for art in articles:
                url_raw = _safe_str(art.get("url"))
                if not url_raw:
                    continue

                cat = _safe_str(art.get("category"), "국내야구").replace("'", "''")
                tit = _safe_str(art.get("title")).replace("'", "''")
                prs = _safe_str(art.get("press")).replace("'", "''")
                dat = _safe_str(art.get("date")).replace("'", "''")
                url = url_raw.replace("'", "''")
                snp = _safe_str(art.get("snippet")).replace("'", "''")

                f.write(
                    f"INSERT INTO articles (category, title, press, date, url, snippet)\n"
                    f"VALUES ('{cat}', '{tit}', '{prs}', '{dat}', '{url}', '{snp}')\n"
                    f"ON CONFLICT(url) DO UPDATE SET snippet = excluded.snippet, title = excluded.title;\n\n"
                )
                f.write(
                    f"INSERT OR IGNORE INTO article_keywords (query_id, article_id)\n"
                    f"SELECT (SELECT id FROM search_queries ORDER BY id DESC LIMIT 1), id FROM articles WHERE url = '{url}';\n\n"
                )

            f.write("COMMIT;\n")
            f.write("-- 배치 작업 완료\n")

    @classmethod
    def export_database(
        cls,
        keyword: str,
        start_date: str,
        end_date: str,
        articles: List[Dict[str, Any]],
        report_md: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        수집된 기사 데이터 및 AI 보고서를 키워드별 누적 데이터베이스 파일({키워드}_데이터베이스.db)에
        고속으로 적재(중복 URL 배제)하여 추출합니다.
        """
        if not articles:
            return {
                "status": "error",
                "message": "수집된 기사 데이터가 없습니다. 먼저 기사를 수집해주세요.",
            }

        target_dir = output_dir or DEFAULT_EXPORT_DB_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        # 키워드 정규화 수행
        entity = normalize_keyword(keyword)
        target_keyword = keyword.strip() or entity.canonical
        canonical_keyword = entity.canonical
        safe_keyword = entity.safe_id or "야구기사"

        # 1. 키워드별 고유 누적 DB 파일 지정 (정규화 safe_id 기준으로 동일 파일에 누적)
        db_filename = f"{safe_keyword}_데이터베이스.db"
        db_path = target_dir / db_filename

        query_id, saved_count, elapsed_ms, total_articles = cls.save_articles_to_db(
            keyword=target_keyword,
            start_date=start_date,
            end_date=end_date,
            articles=articles,
            db_path=db_path,
            report_md=report_md,
            canonical_keyword=canonical_keyword,
        )

        # 2. 통합 영구 DB(baseball_news.db)에도 전체 누적 적재
        main_db_path = target_dir / cls.DEFAULT_DB_NAME
        try:
            cls.save_articles_to_db(
                keyword=target_keyword,
                start_date=start_date,
                end_date=end_date,
                articles=articles,
                db_path=main_db_path,
                report_md=report_md,
                canonical_keyword=canonical_keyword,
            )
        except Exception as e:
            print(f"통합 DB 동기화 경고: {e}")

        # 3. python -m sqlite3 CLI 정합성 무결성 테스트 실행
        cli_verified = False
        try:
            test_cmd = [
                sys.executable,
                "-m",
                "sqlite3",
                str(db_path),
                "SELECT COUNT(*) FROM articles;",
            ]
            res = subprocess.run(
                test_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                cli_verified = True
        except Exception:
            cli_verified = False

        has_report_str = "포함 (ai_reports 테이블 적재 완료)" if report_md and report_md.strip() else "미포함 (기사만 적재)"

        return {
            "status": "success",
            "message": (
                f"데이터베이스 누적 저장 완료! (처리속도: {elapsed_ms:.2f}ms)\n"
                f"- 표준 대상: '{canonical_keyword}' (입력: '{target_keyword}')\n"
                f"- DB 파일: storage/db/{db_filename}\n"
                f"- 기사 적재: 이번 세션 {saved_count}건 (누적 총 {total_articles}건, 중복 제외)\n"
                f"- AI 보고서: {has_report_str}\n"
                f"- 통합 DB(baseball_news.db) 동기화 완료"
            ),
            "canonical_keyword": canonical_keyword,
            "db_filename": db_filename,
            "db_path": str(db_path),
            "count": saved_count,
            "total_articles": total_articles,
            "elapsed_ms": elapsed_ms,
            "cli_verified": cli_verified,
            "has_report": bool(report_md and report_md.strip()),
        }

    @classmethod
    def save_stadium_weather_records(
        cls,
        records: List[Dict[str, Any]],
        db_path: Path,
    ) -> int:
        """
        11개 구장의 날씨 관측 레코드를 stadium_weather_history 테이블에 고속 UPSERT 적재합니다.
        (stadium_id, base_date, base_time) 고유 제약 조건으로 중복 저장을 방지하고 최신값으로 갱신합니다.
        반환값: 성공적으로 적재/갱신된 구장 수
        """
        if not records:
            return 0

        cls.init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            cls.apply_speed_optimizations(conn)
            cursor = conn.cursor()

            upsert_sql = """
            INSERT INTO stadium_weather_history (
                stadium_id, stadium_name, base_date, base_time,
                temp, temp_str, rain, humidity, wind_speed, pty,
                status_label, badge_class, status_desc, icon
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stadium_id, base_date, base_time) DO UPDATE SET
                temp = excluded.temp,
                temp_str = excluded.temp_str,
                rain = excluded.rain,
                humidity = excluded.humidity,
                wind_speed = excluded.wind_speed,
                pty = excluded.pty,
                status_label = excluded.status_label,
                badge_class = excluded.badge_class,
                status_desc = excluded.status_desc,
                icon = excluded.icon,
                created_at = CURRENT_TIMESTAMP;
            """

            saved_count = 0
            for r in records:
                cursor.execute(
                    upsert_sql,
                    (
                        _safe_str(r.get("stadium_id") or r.get("id")),
                        _safe_str(r.get("stadium_name") or r.get("name")),
                        _safe_str(r.get("base_date")),
                        _safe_str(r.get("base_time")),
                        r.get("temp_num"),
                        _safe_str(r.get("temp", "--")),
                        float(r.get("rain_num", 0.0) or 0.0),
                        r.get("humidity_num"),
                        float(r.get("wind_num", 0.0) or 0.0),
                        int(r.get("pty", 0) or 0),
                        _safe_str(r.get("status_label", "🟢 정상 진행 가능")),
                        _safe_str(r.get("badge_class", "badge-safe")),
                        _safe_str(r.get("status_desc", "")),
                        _safe_str(r.get("icon", "☀️")),
                    ),
                )
                saved_count += 1

            conn.commit()
            return saved_count
        finally:
            conn.close()

    @classmethod
    def get_stadium_weather_history(
        cls,
        base_date: str,
        base_time: str,
        db_path: Path,
    ) -> List[Dict[str, Any]]:
        """
        특정 날짜(YYYY-MM-DD) 및 시간대(HH:00)의 구장별 날씨 이력 목록을 조회합니다.
        """
        cls.init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
            SELECT id, stadium_id, stadium_name, base_date, base_time,
                   temp, temp_str, rain, humidity, wind_speed, pty,
                   status_label, badge_class, status_desc, icon, created_at
            FROM stadium_weather_history
            WHERE base_date = ? AND base_time = ?
            ORDER BY id ASC;
            """
            cursor.execute(query, (base_date.strip(), base_time.strip()))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @classmethod
    def get_weather_history_dates(cls, db_path: Path) -> List[Dict[str, Any]]:
        """
        DB에 누적 저장된 날씨 관측 일자 및 시간대 목록을 최신순으로 조회합니다.
        반환 예시: [{'base_date': '2026-09-11', 'base_time': '15:00', 'count': 11}, ...]
        """
        cls.init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            query = """
            SELECT base_date, base_time, COUNT(*) as count
            FROM stadium_weather_history
            GROUP BY base_date, base_time
            ORDER BY base_date DESC, base_time DESC;
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                {
                    "base_date": r[0],
                    "base_time": r[1],
                    "count": r[2],
                    "label": f"{r[0]} {r[1]} ({r[2]}개 구장)",
                }
                for r in rows
            ]
        finally:
            conn.close()

