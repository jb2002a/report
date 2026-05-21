"""Section-aware retrieval reranking to reduce cross-section chunk contamination."""

from __future__ import annotations

from equity_rag.schemas import RetrievedChunk

# Fetch more candidates, then rerank down to top_k.
SECTION_FETCH_MULTIPLIER: dict[str, int] = {
    "business_overview": 2,
    "investment_thesis": 2,
    "industry_supply": 3,
}

SECTION_BOOST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "business_overview": (
        "사업부",
        "부문",
        "매출 비중",
        "segment",
        "컴포넌트",
        "패키지",
        "광학",
        "사업 개요",
        "사업 구조",
    ),
    "investment_thesis": (
        "투자 포인트",
        "핵심 논리",
        "적정주가",
        "상향",
        "차별화",
        "구조",
        "저평가",
        "투자 매력",
        "성장",
        "catalyst",
    ),
    "industry_supply": (
        "수급",
        "가동률",
        "ASP",
        "판가",
        "재고",
        "캐파",
        "생산 능력",
        "원자재",
        "원가",
        "가격",
        "증설",
        "CAPEX",
        "utilization",
        "supply",
        "demand",
        "tight",
    ),
}

SECTION_PENALIZE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "business_overview": (
        "가동률",
        "FC-BGA 매출액",
    ),
    "investment_thesis": (
        "추천기준일",
        "직전 1개월",
        "채권분석",
        "기업브리프",
        "괴리율",
    ),
    "industry_supply": (
        "적정주가",
        "목표주가",
        "PER",
        "PBR",
        "상승여력",
        "EV/EBITDA",
        "Implied 주가",
        "멀티플",
        "회전율",
        "부채비율",
        "매출채권",
        "재고자산",
        "매입채무",
        "계속사업",
        "조정영업이익",
        "BPS",
        "순차입금",
        "투자의견",
        "매도",
        "비중축소",
        "Buy",
        "Hold",
    ),
}

SECTION_PREFER_NARRATIVE: frozenset[str] = frozenset(
    {"business_overview", "industry_supply", "investment_thesis"}
)

SECTION_BOOST_EARLY_PAGES: dict[str, int] = {
    "investment_thesis": 3,
}


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw.lower() in lowered)


def rerank_chunks_for_section(
    section: str,
    chunks: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    if not chunks:
        return chunks

    prefer_narrative = section in SECTION_PREFER_NARRATIVE
    boost_keywords = SECTION_BOOST_KEYWORDS.get(section, ())
    penalize_keywords = SECTION_PENALIZE_KEYWORDS.get(section, ())
    early_page_max = SECTION_BOOST_EARLY_PAGES.get(section)

    scored: list[tuple[RetrievedChunk, float]] = []
    for chunk in chunks:
        base = chunk.score if chunk.score is not None else 0.0
        text = chunk.text
        metadata = chunk.metadata

        adjustment = 0.0
        adjustment += 0.04 * _keyword_hits(text, boost_keywords)
        adjustment -= 0.08 * _keyword_hits(text, penalize_keywords)

        if prefer_narrative and metadata.get("is_table") is True:
            adjustment -= 0.06
        elif prefer_narrative and metadata.get("is_table") is False:
            adjustment += 0.03

        if early_page_max is not None:
            page = metadata.get("page")
            try:
                if page is not None and int(page) <= early_page_max:
                    adjustment += 0.05
            except (TypeError, ValueError):
                pass

        scored.append((chunk, base + adjustment))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [chunk for chunk, _ in scored[:top_k]]


def fetch_multiplier_for_section(section: str) -> int:
    return SECTION_FETCH_MULTIPLIER.get(section, 1)
