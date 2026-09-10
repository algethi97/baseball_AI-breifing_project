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
    snippet         TEXT,
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

-- 인덱스 (조회 및 검색 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
CREATE INDEX IF NOT EXISTS idx_articles_press ON articles(press);
CREATE INDEX IF NOT EXISTS idx_queries_keyword ON search_queries(keyword);
CREATE INDEX IF NOT EXISTS idx_ak_query_id ON article_keywords(query_id);
CREATE INDEX IF NOT EXISTS idx_ak_article_id ON article_keywords(article_id);
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
        데이터베이스 파일에 스키마 및 인덱스를 생성합니다.
        """
        conn = sqlite3.connect(db_path)
        try:
            cls.apply_speed_optimizations(conn)
            conn.executescript(SCHEMA_DDL)
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
    ) -> Tuple[int, int, float]:
        """
        단일 원자적 트랜잭션(Atomic Transaction)으로 기사 데이터를 고속 적재합니다.
        Returns:
            (query_id, 적재된 기사 수, 소요 시간(ms))
        """
        if not articles:
            return 0, 0, 0.0

        cls.init_db(db_path)
        start_time = time.perf_counter()

        conn = sqlite3.connect(db_path)
        try:
            cls.apply_speed_optimizations(conn)
            cursor = conn.cursor()

            # 1. 수집 쿼리 세션 등록
            cursor.execute(
                """
                INSERT INTO search_queries (keyword, start_date, end_date, collected_count)
                VALUES (?, ?, ?, ?)
                """,
                (_safe_str(keyword, "야구"), _safe_str(start_date), _safe_str(end_date), len(articles)),
            )
            query_id = cursor.lastrowid

            # 2. 기사 테이블 UPSERT 및 매핑 테이블 적재
            upsert_sql = """
            INSERT INTO articles (category, title, press, date, url, snippet)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                snippet = CASE WHEN excluded.snippet != '' THEN excluded.snippet ELSE articles.snippet END,
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

                cursor.execute(
                    upsert_sql,
                    (
                        _safe_str(art.get("category"), "국내야구"),
                        _safe_str(art.get("title")),
                        _safe_str(art.get("press")),
                        _safe_str(art.get("date")),
                        url_val,
                        _safe_str(art.get("snippet")),
                    ),
                )
                row = cursor.fetchone()
                if row:
                    article_id = row[0]
                    cursor.execute(mapping_sql, (query_id, article_id))
                    saved_count += 1

            conn.commit()
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return query_id, saved_count, elapsed_ms

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
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        수집된 기사 데이터를 고속 SQL CLI 방식으로 데이터베이스 파일(.db)과
        배치 스크립트(.sql)로 동시 추출합니다.
        """
        if not articles:
            return {
                "status": "error",
                "message": "수집된 기사 데이터가 없습니다. 먼저 기사를 수집해주세요.",
            }

        target_dir = output_dir or DEFAULT_EXPORT_DB_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target_keyword = keyword.strip() or "야구"
        safe_keyword = re.sub(r"[^\w가-힣0-9_-]", "", target_keyword).strip() or "야구기사"

        extract_date = datetime.now().strftime("%y%m%d")
        extract_time = datetime.now().strftime("%H%M%S")

        # 1. 고속 독립 DB 파일 생성
        db_filename = f"{safe_keyword}_데이터베이스_{extract_date}_{extract_time}.db"
        db_path = target_dir / db_filename

        query_id, saved_count, elapsed_ms = cls.save_articles_to_db(
            keyword=target_keyword,
            start_date=start_date,
            end_date=end_date,
            articles=articles,
            db_path=db_path,
        )

        # 2. 통합 영구 DB(baseball_news.db)에도 누적 적재
        main_db_path = target_dir / cls.DEFAULT_DB_NAME
        try:
            cls.save_articles_to_db(
                keyword=target_keyword,
                start_date=start_date,
                end_date=end_date,
                articles=articles,
                db_path=main_db_path,
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

        return {
            "status": "success",
            "message": (
                f"데이터베이스 추출 완료! (처리속도: {elapsed_ms:.2f}ms)\n"
                f"- DB 파일: storage/db/{db_filename} ({saved_count}건 저장)\n"
                f"- 통합 DB(baseball_news.db) 동기화 완료"
            ),
            "db_filename": db_filename,
            "db_path": str(db_path),
            "count": saved_count,
            "elapsed_ms": elapsed_ms,
            "cli_verified": cli_verified,
        }
