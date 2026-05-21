from __future__ import annotations

from pathlib import Path

from langchain_openai import ChatOpenAI

from equity_rag.config import Settings, get_settings
from equity_rag.normalize import normalize_company_name, normalize_ticker
from equity_rag.observability.langsmith import configure_langsmith, trace_metadata, traceable
from equity_rag.rag.fixed_queries import build_fixed_queries
from equity_rag.rag.multi_source_report import (
    build_multi_source_section_bundles,
    discover_sources_for_ticker,
    synthesize_multi_source_report,
)
from equity_rag.rag.prompts import FINAL_REPORT_PROMPT, PROMPT_VERSION
from equity_rag.rag.section_summarizer import SectionSummarizer
from equity_rag.rag.section_titles import SECTION_TITLES
from equity_rag.schemas import GeneratedReport, SectionSummary


@traceable(name="generate_report")
def generate_report(
    ticker: str,
    company_name: str,
    output_path: str | Path | None = None,
    settings: Settings | None = None,
    mode: str = "by_source",
    sources: list[str] | None = None,
) -> GeneratedReport:
    settings = settings or get_settings()
    configure_langsmith(settings)

    normalized_ticker = normalize_ticker(ticker)
    normalized_company = normalize_company_name(company_name)

    if mode == "unified":
        return _generate_unified_report(
            normalized_ticker,
            normalized_company,
            output_path,
            settings,
        )

    return _generate_by_source_report(
        normalized_ticker,
        normalized_company,
        output_path,
        settings,
        sources=sources,
    )


def _generate_by_source_report(
    ticker: str,
    company_name: str,
    output_path: str | Path | None,
    settings: Settings,
    sources: list[str] | None = None,
) -> GeneratedReport:
    source_registry = discover_sources_for_ticker(ticker, settings, sources=sources)
    summarizer = SectionSummarizer(settings)
    section_bundles = build_multi_source_section_bundles(
        ticker=ticker,
        company_name=company_name,
        sources=source_registry,
        settings=settings,
        summarizer=summarizer,
    )
    final_content = synthesize_multi_source_report(
        settings=settings,
        ticker=ticker,
        company_name=company_name,
        sources=source_registry,
        section_bundles=section_bundles,
    )

    saved_path = _save_report(output_path, final_content, settings, ticker, suffix="_multi_source_report")

    _ = trace_metadata(
        workflow="final_report_generation",
        report_mode="by_source",
        ticker=ticker,
        company_name=company_name,
        prompt_version=PROMPT_VERSION,
        source_count=len(source_registry),
        section_count=len(section_bundles),
        final_report_length=len(final_content),
        output_path=saved_path,
    )

    return GeneratedReport(
        ticker=ticker,
        company_name=company_name,
        content=final_content,
        source_registry=source_registry,
        section_bundles=section_bundles,
        report_mode="by_source",
        output_path=saved_path,
    )


def _generate_unified_report(
    ticker: str,
    company_name: str,
    output_path: str | Path | None,
    settings: Settings,
) -> GeneratedReport:
    summarizer = SectionSummarizer(settings)
    section_summaries: list[SectionSummary] = []

    for section_query in build_fixed_queries(ticker, company_name):
        section_title = SECTION_TITLES.get(
            section_query.section,
            section_query.section,
        )
        summary = summarizer.summarize(
            ticker=ticker,
            company_name=company_name,
            section_query=section_query,
            section_title=section_title,
        )
        section_summaries.append(summary)

    final_content = _synthesize_unified_final_report(
        settings=settings,
        ticker=ticker,
        company_name=company_name,
        section_summaries=section_summaries,
    )

    saved_path = _save_report(output_path, final_content, settings, ticker, suffix="_report")

    insufficient_sections = [
        summary.section
        for summary in section_summaries
        if summary.insufficient_context
    ]
    _ = trace_metadata(
        workflow="final_report_generation",
        report_mode="unified",
        ticker=ticker,
        company_name=company_name,
        prompt_version=PROMPT_VERSION,
        included_sections=[summary.section for summary in section_summaries],
        insufficient_sections=insufficient_sections,
        final_report_length=len(final_content),
        output_path=saved_path,
    )

    return GeneratedReport(
        ticker=ticker,
        company_name=company_name,
        content=final_content,
        section_summaries=section_summaries,
        report_mode="unified",
        output_path=saved_path,
    )


def _save_report(
    output_path: str | Path | None,
    content: str,
    settings: Settings,
    ticker: str,
    suffix: str,
) -> str | None:
    if output_path is None:
        path = settings.outputs_dir / f"{ticker}{suffix}.md"
    else:
        path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _synthesize_unified_final_report(
    settings: Settings,
    ticker: str,
    company_name: str,
    section_summaries: list[SectionSummary],
) -> str:
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key or None,
        temperature=0.2,
    )
    formatted_sections = _format_unified_section_summaries(section_summaries)
    messages = FINAL_REPORT_PROMPT.format_messages(
        ticker=ticker,
        company_name=company_name,
        section_summaries=formatted_sections,
    )
    response = llm.invoke(messages)
    return str(response.content).strip()


def _format_unified_section_summaries(section_summaries: list[SectionSummary]) -> str:
    blocks: list[str] = []
    for summary in section_summaries:
        title = SECTION_TITLES.get(summary.section, summary.section)
        status = (
            "근거 부족"
            if summary.insufficient_context
            else f"retrieved_chunks={summary.retrieved_chunk_count}"
        )
        blocks.append(
            f"### {title} ({summary.section})\n"
            f"Status: {status}\n\n"
            f"{summary.summary}"
        )
    return "\n\n".join(blocks)
