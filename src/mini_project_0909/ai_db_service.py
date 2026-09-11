"""
SQLAlchemy 2.0 기반 AI 자연어 데이터베이스(DDL/CRUD/통계) 제어 서비스 모듈
OpenAI gpt-5.6-luna를 결합하여 자연어 명령을 최적 SQLite SQL로 변환하고
SQLAlchemy 2.0 Engine(inspect, text, begin/connect) 위에서 안전하게 실행 및 자가 수정을 수행합니다.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv(override=True)


def clean_sql(raw_response: str) -> str:
    """
    AI 응답 텍스트에서 마크다운 코드 블록 및 불필요한 설명어를 제거하고
    단일 실행 가능한 순수 SQLite SQL 문장만 추출합니다.
    """
    text_content = raw_response.strip()

    # 1. ```sql ... ``` 또는 ``` ... ``` 마크다운 코드블록 추출
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text_content, re.IGNORECASE)
    if match:
        sql = match.group(1).strip()
    else:
        # 주요 SQL 키워드 시작 위치 탐색
        kw_match = re.search(
            r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|PRAGMA|WITH)\b",
            text_content,
            re.IGNORECASE,
        )
        if kw_match:
            sql = text_content[kw_match.start():].strip()
        else:
            sql = text_content

    # 양끝 따옴표 및 공백 정리
    sql = sql.strip("`'\"\n\r\t ")
    if sql and not sql.endswith(";"):
        sql += ";"
    return sql


def get_query_type(sql: str) -> str:
    """
    SQL 쿼리의 성격을 판별합니다.
    - 'READ': SELECT, PRAGMA, WITH, EXPLAIN
    - 'DELETE': DELETE
    - 'INSERT': INSERT
    - 'UPDATE': UPDATE
    - 'DDL': CREATE, ALTER, DROP
    """
    cleaned = re.sub(r"--.*?\n", "", sql)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL).strip()
    tokens = cleaned.split()
    first_word = tokens[0].upper() if tokens else ""

    if first_word in ("SELECT", "PRAGMA", "WITH", "EXPLAIN"):
        return "READ"
    elif first_word == "DELETE":
        return "DELETE"
    elif first_word == "INSERT":
        return "INSERT"
    elif first_word == "UPDATE":
        return "UPDATE"
    elif first_word in ("CREATE", "ALTER", "DROP"):
        return "DDL"
    return "UNKNOWN"


def check_query_safety(sql: str) -> Tuple[bool, str]:
    """
    잠재적으로 파괴적인 쿼리를 검증하여 실행을 사전 차단합니다.
    """
    upper = sql.upper()
    if "DROP TABLE" in upper:
        return False, "데이터베이스 무결성 보호를 위해 'DROP TABLE' 구문은 실행할 수 없습니다."
    if re.search(r"\bDELETE\s+FROM\s+\w+\s*(?:;)?$", upper):
        return False, "WHERE 조건절이 없는 전체 데이터 삭제(DELETE) 구문은 실행할 수 없습니다."
    if re.search(r"\bUPDATE\s+\w+\s+SET\b", upper) and "WHERE" not in upper:
        return False, "WHERE 조건절이 없는 전체 데이터 일괄 수정(UPDATE) 구문은 실행할 수 없습니다."
    return True, "안전한 쿼리입니다."


class SQLAlchemyAIDatabaseEngine:
    """
    SQLAlchemy 2.0 기반 자연어 DB 제어 엔진
    """

    def __init__(
        self,
        db_path: Path,
        client: Optional[OpenAI] = None,
        model: str = "gpt-5.6-luna",
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_url = f"sqlite:///{self.db_path.resolve()}"
        self.model = model

        # OpenAI 클라이언트 준비
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = client or (OpenAI(api_key=api_key) if api_key else None)

        # SQLAlchemy 2.0 엔진 생성
        self.engine = create_engine(
            self.db_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in self.db_url else {},
        )

        # 직전 대화 및 쿼리 실행 컨텍스트 (연속 작업용 메모리)
        self.last_result_context: Optional[Dict[str, Any]] = None

    def get_schema_info(self) -> str:
        """
        SQLAlchemy 2.0 inspect를 사용하여 현재 DB의 모든 테이블 및 컬럼, 레코드 수를 추출합니다.
        """
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        if not tables:
            return "[현재 데이터베이스에 생성된 테이블이 없습니다. 새로운 테이블 생성이 필요합니다.]"

        schema_parts = []
        with self.engine.connect() as conn:
            for table_name in tables:
                columns = inspector.get_columns(table_name)
                pk_constraint = inspector.get_pk_constraint(table_name)
                pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []

                col_desc = []
                for col in columns:
                    c_name = col["name"]
                    c_type = str(col["type"])
                    pk_str = " (PRIMARY KEY)" if c_name in pk_cols else ""
                    null_str = " NOT NULL" if not col.get("nullable", True) else ""
                    col_desc.append(f"  - {c_name} ({c_type}){pk_str}{null_str}")

                try:
                    cnt_res = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = cnt_res.scalar() or 0
                except Exception:
                    count = 0

                t_text = (
                    f"테이블명: {table_name} (현재 레코드: {count}건)\n"
                    f"컬럼 목록:\n" + "\n".join(col_desc)
                )
                schema_parts.append(t_text)

        return "\n\n" + ("=" * 45) + "\n" + "\n\n".join(schema_parts) + "\n" + ("=" * 45)

    def ask(self, user_query: str, auto_correct: bool = True) -> Dict[str, Any]:
        """
        자연어 질의를 받아 SQLAlchemy 엔진 위에서 SQL을 생성하고 실행합니다.
        에러 발생 시 SQLAlchemyError를 포착하여 자가 수정(Self-Correction)을 1회 수행합니다.
        """
        if not self.client:
            return {
                "status": "error",
                "message": "❌ OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.",
                "sql": "",
            }

        schema_info = self.get_schema_info()

        # 직전 대화/쿼리 실행 컨텍스트 정보 포맷팅 (연속 작업 지원)
        context_str = ""
        if self.last_result_context:
            ctx = self.last_result_context
            sample_summaries = []
            for r in (ctx.get("records") or [])[:5]:
                r_id = r.get("id", "")
                r_title = r.get("title", r.get("memo", ""))
                sample_summaries.append(f"  - [ID {r_id}] {r_title}")
            sample_text = "\n".join(sample_summaries) if sample_summaries else "(샘플 없음)"

            context_str = (
                f"\n[직전 대화 및 쿼리 실행 컨텍스트 (연속 작업용 참조 정보)]\n"
                f"- 직전 사용자 요청: \"{ctx.get('user_query', '')}\"\n"
                f"- 직전 실행된 SQL: \"{ctx.get('sql', '')}\"\n"
                f"- 직전 쿼리 유형: {ctx.get('query_type', '')}\n"
                f"- 직전 대상 테이블: {ctx.get('table', 'articles')}\n"
                f"- 직전 조회 건수: {ctx.get('row_count', 0)}건\n"
                f"- 직전 조회된 기사 ID 목록: {ctx.get('target_ids', [])[:50]}\n"
                f"- 직전 조회 데이터 샘플 미리보기:\n{sample_text}\n"
            )

        system_instruction = (
            "당신은 대한민국 프로야구(KBO) 데이터베이스 및 SQLAlchemy/SQLite 전문 수석 데이터 엔지니어입니다.\n"
            "사용자의 요청과 제공된 현재 데이터베이스 스키마를 철저히 바탕으로, "
            "오직 실행 가능한 단일 SQLite SQL 쿼리문만 작성하세요.\n\n"
            "[엄격한 작성 규칙]\n"
            "1. 인사말, 마크다운 설명 텍스트를 절대로 작성하지 마세요. 오직 순수한 SQL문 한 줄/블록만 출력하세요.\n"
            "2. 스키마에 존재하는 테이블명과 컬럼명만 정확히 참조하세요.\n"
            "3. 특정 문구가 제목(title)이나 본문(content)에 들어간 기사를 조회(SELECT)하거나 삭제(DELETE)할 때는 LIKE '%문구%' 구문과 명확한 WHERE 조건절을 사용하세요.\n"
            "4. 데이터 삭제(DELETE) 요청 시, 다른 정상 데이터가 실수로 삭제되지 않도록 반드시 사용자가 요청한 조건(예: WHERE title LIKE '%...%')을 엄격하게 명시하세요.\n"
            "5. 테이블 생성(DDL) 시에는 중복 오류를 방지하기 위해 'CREATE TABLE IF NOT EXISTS' 구문을 사용하세요.\n"
            "6. 한글 검색 시 공백과 대소문자에 유의하고, 필요 시 LIKE '%...%' 구문을 적절히 활용하세요.\n"
            "7. [대화 연속 작업]: 사용자가 '방금 조회된 기사들', '직전 결과', '이 기사들', '그 중에서', '방금 나온 것' 등 이전 대화 맥락이나 직전 조회 데이터를 지칭하는 경우:\n"
            "   - 반드시 [직전 대화 및 쿼리 실행 컨텍스트]에 기록된 대상 테이블과 레코드 ID 목록(WHERE id IN (...)) 또는 직전 조건을 활용하여 후속 쿼리(조건부 삭제, 북마크 테이블로 복사/등록, 추가 필터링 등)를 안전하고 정확하게 작성하세요.\n"
            "   - 예시 1 (방금 조회된 기사 삭제): DELETE FROM articles WHERE id IN (101, 102, ...);\n"
            "   - 예시 2 (방금 조회된 기사 북마크 등록): INSERT INTO baseball_bookmarks (article_id, title, press, memo, created_at) SELECT id, title, press, 'AI 북마크', CURRENT_TIMESTAMP FROM articles WHERE id IN (101, 102, ...);\n"
            "   - 예시 3 (방금 나온 기사 재필터링): SELECT * FROM articles WHERE id IN (101, 102, ...) AND date >= '2026-09-10';"
        )

        prompt = (
            f"[현재 데이터베이스 스키마 정보]\n{schema_info}\n"
            f"{context_str}\n"
            f"[사용자 자연어 요청]\n{user_query}\n"
        )

        try:
            resp = self.client.responses.create(
                model=self.model,
                instructions=system_instruction,
                input=prompt,
            )
            raw_sql = resp.output_text.strip()
            sql = clean_sql(raw_sql)
        except Exception as e:
            return {
                "status": "error",
                "message": f"AI SQL 생성 중 오류가 발생했습니다: {str(e)}",
                "sql": "",
            }

        # 안전성 검사
        is_safe, warn_msg = check_query_safety(sql)
        if not is_safe:
            return {
                "status": "blocked",
                "message": f"⚠️ 보안 정책에 의해 실행이 차단되었습니다: {warn_msg}",
                "sql": sql,
            }

        def execute_sql(target_sql: str) -> Dict[str, Any]:
            q_type = get_query_type(target_sql)

            # 대상 테이블 이름 파싱 (FROM/INTO/FROM \w+)
            t_match = re.search(r"\b(?:FROM|INTO|UPDATE)\s+([a-zA-Z0-9_]+)", target_sql, re.IGNORECASE)
            target_table = t_match.group(1) if t_match else "articles"

            if q_type == "READ":
                # 조회 (SELECT) ➔ DataFrame
                with self.engine.connect() as conn:
                    df = pd.read_sql_query(text(target_sql), conn)

                row_count = len(df)
                records = df.to_dict(orient="records")
                target_ids = [r["id"] for r in records if "id" in r]

                # 직전 쿼리 컨텍스트 메모리에 저장
                self.last_result_context = {
                    "user_query": user_query,
                    "sql": target_sql,
                    "query_type": "READ",
                    "table": target_table,
                    "row_count": row_count,
                    "target_ids": target_ids,
                    "records": records[:30],
                }

                if row_count > 0:
                    # 마크다운 표로 변환 (최대 30행 제한으로 가독성 유지)
                    display_df = df.head(30)
                    try:
                        md_table = display_df.to_markdown(index=False)
                    except Exception:
                        md_table = str(display_df)
                    summary_msg = f"데이터베이스에서 총 {row_count}건의 데이터를 조회했습니다."
                else:
                    md_table = "_조회된 데이터가 없습니다 (0건)._"
                    summary_msg = "조건에 부합하는 데이터가 데이터베이스에 존재하지 않습니다."

                return {
                    "status": "success",
                    "query_type": "READ",
                    "sql": target_sql,
                    "row_count": row_count,
                    "data": records,
                    "markdown_table": md_table,
                    "message": summary_msg,
                }
            else:
                # DDL / DML ➔ 트랜잭션 자동 커밋 (begin)
                with self.engine.begin() as conn:
                    result = conn.execute(text(target_sql))
                    affected = result.rowcount

                if q_type == "DDL":
                    summary_msg = "테이블 및 데이터베이스 스키마 정의(DDL) 작업이 성공적으로 완료되었습니다."
                elif q_type == "DELETE":
                    summary_msg = f"데이터베이스에서 조건에 일치하는 데이터 총 {affected}건을 성공적으로 삭제했습니다."
                    # 삭제 완료 시 삭제된 대상을 중복 삭제하지 않도록 컨텍스트 초기화
                    self.last_result_context = None
                elif q_type == "INSERT":
                    summary_msg = f"데이터베이스에 신규 데이터가 성공적으로 등록되었습니다. (추가된 행: {affected}건)"
                elif q_type == "UPDATE":
                    summary_msg = f"데이터베이스 내 레코드 정보가 성공적으로 수정되었습니다. (수정된 행: {affected}건)"
                else:
                    summary_msg = f"데이터 조작(DML) 작업이 완료되었습니다. (영향받은 행: {affected}건)"

                return {
                    "status": "success",
                    "query_type": q_type,
                    "sql": target_sql,
                    "row_count": affected,
                    "markdown_table": "",
                    "message": summary_msg,
                }

        # 1차 실행 시도
        try:
            return execute_sql(sql)
        except SQLAlchemyError as err:
            if not auto_correct:
                return {
                    "status": "error",
                    "message": f"SQL 실행 오류: {str(err)}",
                    "sql": sql,
                }

            # 자가 수정 (Self-Correction) 시도
            fix_prompt = (
                f"[자가 수정 요청]\n"
                f"이전에 작성했던 쿼리를 실행하는 중 SQLAlchemy/SQLite 오류가 발생했습니다.\n"
                f"- 실패한 SQL: {sql}\n"
                f"- 오류 메시지: {str(err)}\n"
                f"- 원본 사용자 요청: {user_query}\n\n"
                f"[현재 스키마]\n{schema_info}\n\n"
                f"위 에러의 원인(컬럼 오타, 문법 오류 등)을 파악하여 올바르게 작동하는 단일 SQLite SQL문만 다시 작성하세요."
            )
            try:
                fix_resp = self.client.responses.create(
                    model=self.model,
                    instructions="You are a strict SQL bug fixer. Output single corrected SQLite SQL only.",
                    input=fix_prompt,
                )
                fixed_sql = clean_sql(fix_resp.output_text.strip())

                is_safe_fixed, warn_fixed = check_query_safety(fixed_sql)
                if not is_safe_fixed:
                    return {
                        "status": "blocked",
                        "message": f"⚠️ 수정된 쿼리가 보안 정책에 의해 차단되었습니다: {warn_fixed}",
                        "sql": fixed_sql,
                    }

                corrected_result = execute_sql(fixed_sql)
                corrected_result["message"] = (
                    f"🔄 [AI 자가 수정 완료] 1차 쿼리 오류를 스스로 감지하고 보정하여 성공적으로 실행했습니다.\n"
                    + corrected_result["message"]
                )
                return corrected_result
            except Exception as fix_err:
                return {
                    "status": "error",
                    "message": f"SQL 실행 및 자가 수정 실패: {str(fix_err)} (원인: {str(err)})",
                    "sql": sql,
                }

