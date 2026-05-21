from __future__ import annotations

from collections import defaultdict

from langchain_openai import ChatOpenAI

from equity_rag.config import Settings
from equity_rag.observability.langsmith import trace_metadata, traceable
from equity_rag.rag.prompts import PROMPT_VERSION, RETRIEVAL_ANALYSIS_PROMPT
from equity_rag.rag.section_titles import SECTION_TITLES_KR
from equity_rag.schemas import RetrievedChunk, SectionQuery
from equity_rag.vectorstore.retriever import ReportRetriever


def group_chunks_by_source(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    grouped: dict[str, list[RetrievedChunk]] = defaultdict(list)
    for chunk in chunks:
        source = str(chunk.metadata.get("source", "unknown")).strip() or "unknown"
        grouped[source].append(chunk)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


class RetrievalAnalyzer:
    def __init__(self, settings: Settings, retriever: ReportRetriever | None = None):
        self.settings = settings
        self.retriever = retriever or ReportRetriever(settings)
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key or None,
            temperature=0.1,
        )

    @traceable(name="analyze_retrieved_section")
    def analyze_section(
        self,
        ticker: str,
        company_name: str,
        section_query: SectionQuery,
        chunks: list[RetrievedChunk],
        source_filter: str | None = None,
    ) -> str:
        section_title_kr = SECTION_TITLES_KR.get(
            section_query.section,
            section_query.section,
        )
        if not chunks:
            scope = source_filter or "전체 증권사"
            return (
                f"### {section_title_kr} 분석 ({scope})\n"
                "- 검색된 chunk 없음. ingest 여부 또는 --source / --section 확인."
            )

        if source_filter:
            return self._analyze_chunk_group(
                ticker=ticker,
                company_name=company_name,
                section_title_kr=section_title_kr,
                scope_label=f"{source_filter} (단일 증권사)",
                chunks=chunks,
                section_key=section_query.section,
            )

        by_source = group_chunks_by_source(chunks)
        if len(by_source) == 1:
            only_source = next(iter(by_source.keys()))
            return self._analyze_chunk_group(
                ticker=ticker,
                company_name=company_name,
                section_title_kr=section_title_kr,
                scope_label=f"{only_source}",
                chunks=chunks,
                section_key=section_query.section,
            )

        blocks: list[str] = []
        for source_name, source_chunks in by_source.items():
            block = self._analyze_chunk_group(
                ticker=ticker,
                company_name=company_name,
                section_title_kr=section_title_kr,
                scope_label=f"{source_name} ({len(source_chunks)} chunks)",
                chunks=source_chunks,
                section_key=section_query.section,
            )
            blocks.append(block)
        return "\n\n".join(blocks)

    def _analyze_chunk_group(
        self,
        ticker: str,
        company_name: str,
        section_title_kr: str,
        scope_label: str,
        chunks: list[RetrievedChunk],
        section_key: str,
    ) -> str:
        context = self.retriever.format_context(chunks)
        if not context.strip():
            return (
                f"### {section_title_kr} — {scope_label}\n"
                "- 해당 검색 결과에서 본문 없음."
            )

        messages = RETRIEVAL_ANALYSIS_PROMPT.format_messages(
            ticker=ticker,
            company_name=company_name,
            section_name=section_title_kr,
            scope_label=scope_label,
            context=context,
        )
        response = self.llm.invoke(messages)
        analysis = str(response.content).strip()
        _ = trace_metadata(
            workflow="retrieval_analysis",
            ticker=ticker,
            company_name=company_name,
            section=section_key,
            scope_label=scope_label,
            prompt_version=PROMPT_VERSION,
            model=self.settings.llm_model,
            retrieved_chunk_count=len(chunks),
            output_length=len(analysis),
        )
        return analysis
