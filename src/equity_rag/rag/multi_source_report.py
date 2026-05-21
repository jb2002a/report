from __future__ import annotations

import re

from langchain_openai import ChatOpenAI

from equity_rag.config import Settings
from equity_rag.observability.langsmith import trace_metadata, traceable
from equity_rag.rag.fixed_queries import build_fixed_queries
from equity_rag.rag.metric_normalization import build_numeric_hints
from equity_rag.rag.prompts import (
    CONCLUSION_PROMPT,
    EXEC_SUMMARY_PROMPT,
    PROMPT_VERSION,
    SECTION_CROSS_SOURCE_PROMPT,
)
from equity_rag.rag.section_summarizer import SectionSummarizer
from equity_rag.rag.section_titles import SECTION_TITLES, SECTION_TITLES_KR
from equity_rag.schemas import (
    BrokerSectionSummary,
    SectionBrokerBundle,
    SourceInfo,
)
from equity_rag.vectorstore.chroma_store import ChromaStore


@traceable(name="compare_section_across_sources")
def _compare_section_across_sources(
    settings: Settings,
    ticker: str,
    company_name: str,
    section_key: str,
    section_title_kr: str,
    broker_summaries: list[BrokerSectionSummary],
    numeric_hints: str = "",
) -> str:
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key or None,
        temperature=0.1,
    )
    formatted = "\n\n".join(
        f"#### {item.source}\n{item.summary}" for item in broker_summaries
    )
    combined_hints = numeric_hints.strip() or build_numeric_hints(broker_summaries)
    messages = SECTION_CROSS_SOURCE_PROMPT.format_messages(
        ticker=ticker,
        company_name=company_name,
        section_name=section_title_kr,
        broker_summaries=formatted,
        numeric_hints=combined_hints or "(해당 섹션에서 십억원 환산 가능한 금액 없음)",
    )
    response = llm.invoke(messages)
    return str(response.content).strip()


def _format_source_registry(sources: list[SourceInfo]) -> str:
    lines = ["| 증권사 | 파일 | report_date |", "|--------|------|-------------|"]
    for item in sources:
        lines.append(
            f"| {item.source} | {item.file_name or '-'} | {item.report_date or '-'} |"
        )
    return "\n".join(lines)


SECTION_REPORT_HEADERS: dict[str, str] = {
    "business_overview": "## 3. Business Overview (사업 개요)",
    "recent_performance": "## 4. Recent Performance (최근 실적)",
    "investment_thesis": "## 5. Investment Thesis (투자 논리)",
    "industry_supply": "## 6. Industry & Supply (산업·수급)",
    "valuation": "## 7. Valuation (밸류에이션)",
    "outlook": "## 8. Outlook (전망)",
}


def _strip_broker_summary_header(summary: str, source: str) -> str:
    """Remove duplicate ### {source} 자료 요약 heading when parent already has ### {source}."""
    pattern = rf"^###\s*{re.escape(source)}\s*자료\s*요약\s*\n+"
    return re.sub(pattern, "", summary.strip(), count=1, flags=re.MULTILINE).strip()


def _format_section_bundles(bundles: list[SectionBrokerBundle]) -> str:
    blocks: list[str] = []
    for bundle in bundles:
        broker_blocks = "\n\n".join(
            f"{summary.summary}" for summary in bundle.broker_summaries
        )
        blocks.append(
            f"## {bundle.section_title_kr} ({bundle.section})\n\n"
            f"{broker_blocks}\n\n"
            f"{bundle.comparison}"
        )
    return "\n\n".join(blocks)


def _build_body_sections(
    sources: list[SourceInfo],
    section_bundles: list[SectionBrokerBundle],
) -> str:
    """Assemble sections 2-8 programmatically to preserve broker bullets and comparison tables."""
    parts: list[str] = [
        "## 2. 분석 자료",
        "",
        _format_source_registry(sources),
        "",
    ]
    for bundle in section_bundles:
        header = SECTION_REPORT_HEADERS.get(
            bundle.section,
            f"## {bundle.section_title_kr}",
        )
        parts.append(header)
        parts.append("")
        for summary in bundle.broker_summaries:
            parts.append(f"### {summary.source}")
            parts.append(
                _strip_broker_summary_header(summary.summary, summary.source)
            )
            parts.append("")
        parts.append(bundle.comparison)
        parts.append("")
    return "\n".join(parts).strip()


@traceable(name="generate_exec_summary")
def _generate_exec_summary(
    settings: Settings,
    ticker: str,
    company_name: str,
    sources: list[SourceInfo],
    section_bundles: list[SectionBrokerBundle],
) -> str:
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key or None,
        temperature=0.2,
    )
    messages = EXEC_SUMMARY_PROMPT.format_messages(
        ticker=ticker,
        company_name=company_name,
        source_registry=_format_source_registry(sources),
        section_bundles=_format_section_bundles(section_bundles),
    )
    response = llm.invoke(messages)
    return str(response.content).strip()


@traceable(name="generate_conclusion")
def _generate_conclusion(
    settings: Settings,
    ticker: str,
    company_name: str,
    sources: list[SourceInfo],
    section_bundles: list[SectionBrokerBundle],
) -> str:
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key or None,
        temperature=0.2,
    )
    messages = CONCLUSION_PROMPT.format_messages(
        ticker=ticker,
        company_name=company_name,
        source_registry=_format_source_registry(sources),
        section_bundles=_format_section_bundles(section_bundles),
    )
    response = llm.invoke(messages)
    return str(response.content).strip()


@traceable(name="build_multi_source_section_bundles")
def build_multi_source_section_bundles(
    ticker: str,
    company_name: str,
    sources: list[SourceInfo],
    settings: Settings,
    summarizer: SectionSummarizer | None = None,
) -> list[SectionBrokerBundle]:
    summarizer = summarizer or SectionSummarizer(settings)
    bundles: list[SectionBrokerBundle] = []

    for section_query in build_fixed_queries(ticker, company_name):
        section_title = SECTION_TITLES.get(
            section_query.section,
            section_query.section,
        )
        section_title_kr = SECTION_TITLES_KR.get(
            section_query.section,
            section_title,
        )
        broker_summaries: list[BrokerSectionSummary] = []
        for source_info in sources:
            broker_summary = summarizer.summarize_for_source(
                ticker=ticker,
                company_name=company_name,
                section_query=section_query,
                section_title=section_title_kr,
                source_info=source_info,
            )
            broker_summaries.append(broker_summary)

        numeric_hints = build_numeric_hints(broker_summaries)
        comparison = _compare_section_across_sources(
            settings=settings,
            ticker=ticker,
            company_name=company_name,
            section_key=section_query.section,
            section_title_kr=section_title_kr,
            broker_summaries=broker_summaries,
            numeric_hints=numeric_hints,
        )
        bundles.append(
            SectionBrokerBundle(
                section=section_query.section,
                section_title_kr=section_title_kr,
                broker_summaries=broker_summaries,
                comparison=comparison,
                numeric_hints=numeric_hints,
            )
        )

    return bundles


@traceable(name="synthesize_multi_source_report")
def synthesize_multi_source_report(
    settings: Settings,
    ticker: str,
    company_name: str,
    sources: list[SourceInfo],
    section_bundles: list[SectionBrokerBundle],
) -> str:
    exec_summary = _generate_exec_summary(
        settings=settings,
        ticker=ticker,
        company_name=company_name,
        sources=sources,
        section_bundles=section_bundles,
    )
    body = _build_body_sections(sources=sources, section_bundles=section_bundles)
    conclusion = _generate_conclusion(
        settings=settings,
        ticker=ticker,
        company_name=company_name,
        sources=sources,
        section_bundles=section_bundles,
    )

    title = f"# {company_name} ({ticker}) 다중 증권사 리서치 종합"
    content = "\n\n".join([title, exec_summary, body, conclusion]).strip()

    _ = trace_metadata(
        workflow="multi_source_final_report",
        ticker=ticker,
        company_name=company_name,
        prompt_version=PROMPT_VERSION,
        source_count=len(sources),
        section_count=len(section_bundles),
        final_report_length=len(content),
        synthesis_mode="assembled_body_llm_bookends",
    )
    return content


def discover_sources_for_ticker(
    ticker: str,
    settings: Settings,
    sources: list[str] | None = None,
) -> list[SourceInfo]:
    store = ChromaStore(settings)
    discovered = store.list_sources_for_ticker(ticker)
    if not discovered:
        raise ValueError(
            f"No ingested sources found for ticker '{ticker}'. "
            "Run ingest for this ticker first."
        )
    if not sources:
        return discovered

    by_name = {item.source: item for item in discovered}
    selected: list[SourceInfo] = []
    for name in sources:
        stripped = name.strip()
        if stripped not in by_name:
            available = ", ".join(by_name.keys())
            raise ValueError(
                f"Source '{stripped}' not found for ticker '{ticker}'. "
                f"Available: {available}"
            )
        selected.append(by_name[stripped])
    return selected
