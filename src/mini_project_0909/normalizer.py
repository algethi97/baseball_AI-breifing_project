"""
KBO 야구 뉴스 키워드 정규화(Keyword Normalization) 및 동의어 관리 모듈
구단 약칭, 띄어쓰기, 조사 결합, 유사 키워드를 표준 대표 명칭 및 식별자로 일원화합니다.
"""

import os
import re
import json
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)


@dataclass
class NormalizedEntity:
    raw: str                  # 사용자가 입력한 원본 문자열
    canonical: str            # 화면 및 보고서 제목용 대표 공식 명칭 (예: '한화 이글스')
    safe_id: str              # DB 파일명 및 시스템 식별자용 명칭 (예: '한화이글스')
    synonyms: List[str]       # 동의어 및 축약어 풀 (연관도 검색 및 RAG 매칭용)
    entity_type: str          # 'team'(구단), 'player'(선수), 'topic'(야구주제), 'general'(일반)

    @property
    def raw_keyword(self) -> str:
        return self.raw


class KeywordNormalizer:
    """
    KBO 야구 뉴스 수집, AI 보고서, DB 적재를 위한 하이브리드 키워드 정규화기
    - 1차: KBO 10개 구단 및 야구 용어 사전 기반 고속 매핑 (Zero Latency)
    - 2차: 텍스트 전처리 (선수명 띄어쓰기 결합, 불필요한 조사 제거)
    - 3차: OpenAI gpt-5.6-luna 지능형 Fallback & 캐싱
    """

    # KBO 10개 구단 공식 명칭 및 동의어 매핑 테이블
    KBO_TEAMS = {
        "한화이글스": {
            "canonical": "한화 이글스",
            "safe_id": "한화이글스",
            "synonyms": ["한화", "한화이글스", "한화 이글스", "이글스"],
            "entity_type": "team",
        },
        "KIA타이거즈": {
            "canonical": "KIA 타이거즈",
            "safe_id": "KIA타이거즈",
            "synonyms": ["KIA", "기아", "기아타이거즈", "KIA타이거즈", "기아 타이거즈", "KIA 타이거즈", "타이거즈"],
            "entity_type": "team",
        },
        "LG트윈스": {
            "canonical": "LG 트윈스",
            "safe_id": "LG트윈스",
            "synonyms": ["LG", "엘지", "LG트윈스", "엘지트윈스", "LG 트윈스", "엘지 트윈스", "트윈스"],
            "entity_type": "team",
        },
        "SSG랜더스": {
            "canonical": "SSG 랜더스",
            "safe_id": "SSG랜더스",
            "synonyms": ["SSG", "쓱", "SSG랜더스", "SSG 랜더스", "랜더스", "SK와이번스", "SK 와이번스"],
            "entity_type": "team",
        },
        "두산베어스": {
            "canonical": "두산 베어스",
            "safe_id": "두산베어스",
            "synonyms": ["두산", "두산베어스", "두산 베어스", "베어스"],
            "entity_type": "team",
        },
        "삼성라이온즈": {
            "canonical": "삼성 라이온즈",
            "safe_id": "삼성라이온즈",
            "synonyms": ["삼성", "삼성라이온즈", "삼성 라이온즈", "라이온즈"],
            "entity_type": "team",
        },
        "롯데자이언츠": {
            "canonical": "롯데 자이언츠",
            "safe_id": "롯데자이언츠",
            "synonyms": ["롯데", "롯데자이언츠", "롯데 자이언츠", "자이언츠"],
            "entity_type": "team",
        },
        "KT위즈": {
            "canonical": "KT 위즈",
            "safe_id": "KT위즈",
            "synonyms": ["KT", "케이티", "KT위즈", "케이티위즈", "KT 위즈", "위즈"],
            "entity_type": "team",
        },
        "NC다이노스": {
            "canonical": "NC 다이노스",
            "safe_id": "NC다이노스",
            "synonyms": ["NC", "엔씨", "NC다이노스", "엔씨다이노스", "NC 다이노스", "다이노스"],
            "entity_type": "team",
        },
        "키움히어로즈": {
            "canonical": "키움 히어로즈",
            "safe_id": "키움히어로즈",
            "synonyms": ["키움", "키움히어로즈", "키움 히어로즈", "히어로즈", "넥센", "넥센히어로즈"],
            "entity_type": "team",
        },
    }

    # 주요 야구 일반 토픽 사전
    KBO_TOPICS = {
        "가을야구": ["포스트시즌", "가을야구", "PS", "준플레이오프", "플레이오프", "한국시리즈"],
        "FA": ["FA", "자유계약", "자유계약선수", "프리에이전트"],
        "신인드래프트": ["드래프트", "신인드래프트", "신인선수지명"],
    }

    def __init__(self, client: Optional[OpenAI] = None, model: str = "gpt-5.6-luna"):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = client or (OpenAI(api_key=api_key) if api_key else None)
        self.model = model
        self._cache: Dict[str, NormalizedEntity] = {}

        # 빠른 역방향 매핑 색인 (소문자/공백제거 -> 대상 키)
        self._lookup: Dict[str, str] = {}
        for team_key, info in self.KBO_TEAMS.items():
            for syn in info["synonyms"]:
                clean_syn = self._clean_token(syn)
                self._lookup[clean_syn] = team_key

    @staticmethod
    def _clean_token(text: str) -> str:
        return re.sub(r"\s+", "", text.lower())

    def _strip_josa(self, text: str) -> str:
        """불필요한 한국어 조사(은/는/이/가/의/을/를/과/와/에게/에서/도/에) 제거"""
        josa_pattern = r"(은|는|이|가|의|을|를|과|와|에게|에서|도|에)$"
        if len(text) > 2:
            return re.sub(josa_pattern, "", text).strip()
        return text.strip()

    def normalize(
        self,
        keyword: str,
        use_llm_fallback: bool = True,
        client: Optional[OpenAI] = None,
        model: Optional[str] = None,
    ) -> NormalizedEntity:
        """
        입력 키워드를 표준 엔티티(NormalizedEntity)로 변환합니다.
        """
        active_client = client or self.client
        active_model = model or self.model

        raw = keyword.strip() if keyword else ""
        if not raw:
            return NormalizedEntity(
                raw="",
                canonical="야구",
                safe_id="야구",
                synonyms=["야구"],
                entity_type="general",
            )

        # 캐시 확인
        if raw in self._cache:
            return self._cache[raw]

        # 1. 텍스트 기본 정제 및 조사 제거
        cleaned = self._strip_josa(raw)
        lookup_key = self._clean_token(cleaned)

        # 2. KBO 10개 구단 사전 검사
        if lookup_key in self._lookup:
            team_key = self._lookup[lookup_key]
            info = self.KBO_TEAMS[team_key]
            entity = NormalizedEntity(
                raw=raw,
                canonical=info["canonical"],
                safe_id=info["safe_id"],
                synonyms=list(dict.fromkeys(info["synonyms"] + [raw, cleaned])),
                entity_type=info["entity_type"],
            )
            self._cache[raw] = entity
            return entity

        # 3. KBO 주요 토픽 사전 검사
        for topic_name, syn_list in self.KBO_TOPICS.items():
            for s in syn_list:
                if self._clean_token(s) == lookup_key:
                    entity = NormalizedEntity(
                        raw=raw,
                        canonical=topic_name,
                        safe_id=topic_name,
                        synonyms=list(dict.fromkeys(syn_list + [raw, cleaned])),
                        entity_type="topic",
                    )
                    self._cache[raw] = entity
                    return entity

        # 4. 한국어 인명/선수명 형태 감지 (예: '김 도 영', '김도영의', '이로운' -> '김도영', '이로운')
        combined_candidate = re.sub(r"\s+", "", cleaned)
        is_spaced_name = bool(re.fullmatch(r"^[가-힣]\s+[가-힣](\s+[가-힣])?$", cleaned))
        is_korean_name = bool(re.fullmatch(r"^[가-힣]{2,4}$", combined_candidate))

        if is_spaced_name or is_korean_name:
            safe_name = re.sub(r"[^\w가-힣0-9_-]", "", combined_candidate).strip() or "선수"
            entity = NormalizedEntity(
                raw=raw,
                canonical=combined_candidate,
                safe_id=safe_name,
                synonyms=list(dict.fromkeys([raw, cleaned, combined_candidate])),
                entity_type="player",
            )
            self._cache[raw] = entity
            return entity

        # 5. LLM Fallback (OpenAI gpt-5.6-luna) - 사전에 없는 별명, 오타, 복합 표현 보정
        if use_llm_fallback and active_client:
            try:
                prompt = f"""당신은 한국 프로야구(KBO) 전문 데이터 엔지니어입니다.
사용자가 입력한 검색 키워드를 분석하여 표준 대표 명칭과 동의어를 JSON으로 정규화하세요.

입력 키워드: "{raw}"

지침:
1. canonical: 공식 표준 명칭 (구단이면 정식명칭, 선수면 선수명, 주제면 표준용어)
2. safe_id: 공백 및 특수문자가 없는 파일/DB용 영숫자·한글 식별자
3. synonyms: 기사 검색 및 연관도 산출에 사용할 동의어/약칭/별칭 리스트 (최대 5개)
4. entity_type: "team", "player", "topic", "general" 중 하나

반드시 순수 JSON 형식만 한 줄로 출력하세요:
{{"canonical": "...", "safe_id": "...", "synonyms": [...], "entity_type": "..."}}"""
                resp = active_client.responses.create(
                    model=active_model,
                    instructions="You are a strict KBO baseball entity normalizer. Output pure JSON only without markdown.",
                    input=prompt,
                )
                text = resp.output_text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                data = json.loads(text.strip())

                canonical = data.get("canonical", cleaned)
                safe_id = re.sub(r"[^\w가-힣0-9_-]", "", data.get("safe_id", canonical)).strip() or cleaned
                syns = list(dict.fromkeys([raw, cleaned, canonical] + data.get("synonyms", [])))
                etype = data.get("entity_type", "general")

                entity = NormalizedEntity(
                    raw=raw,
                    canonical=canonical,
                    safe_id=safe_id,
                    synonyms=syns,
                    entity_type=etype,
                )
                self._cache[raw] = entity
                return entity
            except Exception:
                pass

        # Fallback 기본값: 정제된 단어 사용
        safe_clean = re.sub(r"[^\w가-힣0-9_-]", "", cleaned).strip() or "야구"
        entity = NormalizedEntity(
            raw=raw,
            canonical=cleaned,
            safe_id=safe_clean,
            synonyms=list(dict.fromkeys([raw, cleaned])),
            entity_type="general",
        )
        self._cache[raw] = entity
        return entity


# 전역 기본 인스턴스
default_normalizer = KeywordNormalizer()


def normalize_keyword(
    keyword: str,
    use_llm_fallback: bool = True,
    client: Optional[OpenAI] = None,
    model: str = "gpt-5.6-luna",
) -> NormalizedEntity:
    """간편 정규화 함수"""
    return default_normalizer.normalize(
        keyword,
        use_llm_fallback=use_llm_fallback,
        client=client,
        model=model,
    )

