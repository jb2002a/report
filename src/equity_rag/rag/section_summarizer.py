from __future__ import annotations

from langchain_openai import ChatOpenAI

from equity_rag.config import Settings
from equity_rag.observability.langsmith import trace_metadata, traceable
from equity_rag.rag.prompts import (
    BROKER_SECTION_FOCUS,
    BROKER_SECTION_SUMMARY_PROMPT,
    PROMPT_VERSION,
    SECTION_SUMMARY_PROMPT,
)
from equity_rag.schemas import BrokerSectionSummary, SectionQuery, SectionSummary, SourceInfo
from equity_rag.vectorstore.retriever import ReportRetriever

INSUFFICIENT_CONTEXT_MESSAGE = (
    "제공된 리서치 자료만으로는 이 섹션을 뒷받침할 근거가 충분하지 않습니다."
)


class SectionSummarizer:
    def __init__(self, settings: Settings, retriever: ReportRetriever | None = None):
        self.settings = settings
        self.retriever = retriever or ReportRetriever(settings)
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key or None,
            temperature=0.1,
        )

    @traceable(name="summarize_section")
    def summarize(
        self,
        ticker: str,
        company_name: str,
        section_query: SectionQuery,
        section_title: str,
    ) -> SectionSummary:
        chunks = self.retriever.retrieve(ticker=ticker, section_query=section_query)
        insufficient = len(chunks) < self.settings.min_context_chunks
        context = self.retriever.format_context(chunks)

        if insufficient or not context.strip():
            summary = INSUFFICIENT_CONTEXT_MESSAGE
        else:
            messages = SECTION_SUMMARY_PROMPT.format_messages(
                ticker=ticker,
                company_name=company_name,
                section_name=section_title,
                context=context,
            )
            response = self.llm.invoke(messages)
            summary = str(response.content).strip()

        _ = trace_metadata(
            workflow="section_summarization",
            ticker=ticker,
            company_name=company_name,
            section=section_query.section,
            prompt_version=PROMPT_VERSION,
            model=self.settings.llm_model,
            retrieved_chunk_count=len(chunks),
            insufficient_context=insufficient,
            output_length=len(summary),
        )

        return SectionSummary(
            section=section_query.section,
            summary=summary,
            insufficient_context=insufficient,
            retrieved_chunk_count=len(chunks),
        )

    @traceable(name="summarize_section_for_source")
    def summarize_for_source(
        self,
        ticker: str,
        company_name: str,
        section_query: SectionQuery,
        section_title: str,
        source_info: SourceInfo,
    ) -> BrokerSectionSummary:
        chunks = self.retriever.retrieve(
            ticker=ticker,
            section_query=section_query,
            source=source_info.source,
        )
        context = self.retriever.format_context(chunks)
        file_name = source_info.file_name or "unknown"
        report_date = source_info.report_date or "unknown"

        if not context.strip():
            summary = (
                f"### {source_info.source} 자료 요약\n"
                f"- 이 섹션({section_title})에서 검색된 관련 내용 없음. "
                f"(file: {file_name})"
            )
        else:
            section_focus = BROKER_SECTION_FOCUS.get(section_query.section, "")
            messages = BROKER_SECTION_SUMMARY_PROMPT.format_messages(
                ticker=ticker,
                company_name=company_name,
                section_name=section_title,
                source=source_info.source,
                file_name=file_name,
                report_date=report_date,
                context=context,
                section_focus=section_focus,
            )
            response = self.llm.invoke(messages)
            summary = str(response.content).strip()

        _ = trace_metadata(
            workflow="broker_section_summarization",
            ticker=ticker,
            company_name=company_name,
            source=source_info.source,
            section=section_query.section,
            prompt_version=PROMPT_VERSION,
            model=self.settings.llm_model,
            retrieved_chunk_count=len(chunks),
            output_length=len(summary),
        )

        return BrokerSectionSummary(
            source=source_info.source,
            section=section_query.section,
            summary=summary,
            file_name=source_info.file_name,
            report_date=source_info.report_date,
            retrieved_chunk_count=len(chunks),
        )
