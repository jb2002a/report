from __future__ import annotations

from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters

from equity_rag.config import Settings
from equity_rag.observability.langsmith import trace_metadata, traceable
from equity_rag.vectorstore.retrieval_rerank import (
    fetch_multiplier_for_section,
    rerank_chunks_for_section,
)
from equity_rag.schemas import RetrievedChunk, SectionQuery
from equity_rag.vectorstore.chroma_store import ChromaStore


class ReportRetriever:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = ChromaStore(settings)

    @traceable(name="retrieve_section_context")
    def retrieve(
        self,
        ticker: str,
        section_query: SectionQuery,
        top_k: int | None = None,
        source: str | None = None,
    ) -> list[RetrievedChunk]:
        # Priority: explicit arg → section-level default → global settings default
        top_k = top_k or section_query.top_k or self.settings.retrieval_top_k
        fetch_k = top_k * fetch_multiplier_for_section(section_query.section)
        index = self.store.get_index()
        filters = MetadataFilters(
            filters=self._build_metadata_filters(ticker, source)
        )
        retriever = index.as_retriever(
            similarity_top_k=fetch_k,
            filters=filters,
        )
        nodes = retriever.retrieve(section_query.query)
        chunks = [
            RetrievedChunk(
                text=node.get_content(),
                score=getattr(node, "score", None),
                metadata=dict(node.metadata or {}),
            )
            for node in nodes
        ]
        deduped = self._dedupe_chunks(chunks)
        deduped = rerank_chunks_for_section(
            section_query.section,
            deduped,
            top_k,
        )
        _ = trace_metadata(
            workflow="retrieval",
            ticker=ticker,
            source=source,
            section=section_query.section,
            query=section_query.query,
            retrieved_chunk_count=len(deduped),
            insufficient_context=len(deduped) < self.settings.min_context_chunks,
        )
        return deduped

    @staticmethod
    def _build_metadata_filters(
        ticker: str,
        source: str | None = None,
    ) -> list[MetadataFilter]:
        filter_list = [
            MetadataFilter(
                key="ticker",
                value=ticker,
                operator=FilterOperator.EQ,
            )
        ]
        if source:
            filter_list.append(
                MetadataFilter(
                    key="source",
                    value=source.strip(),
                    operator=FilterOperator.EQ,
                )
            )
        return filter_list

    @staticmethod
    def format_context(chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return ""

        formatted_blocks: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.metadata
            header = (
                f"[Source {index}] "
                f"source={metadata.get('source', 'unknown')} | "
                f"date={metadata.get('report_date', 'unknown')} | "
                f"page={metadata.get('page', 'unknown')} | "
                f"file={metadata.get('file_name', 'unknown')}"
            )
            score_text = (
                f" | score={chunk.score:.4f}"
                if chunk.score is not None
                else ""
            )
            formatted_blocks.append(f"{header}{score_text}\n{chunk.text}")

        return "\n\n".join(formatted_blocks)

    @staticmethod
    def _dedupe_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen: set[str] = set()
        deduped: list[RetrievedChunk] = []

        for chunk in chunks:
            metadata = chunk.metadata
            key = (
                f"{metadata.get('file_name')}:"
                f"{metadata.get('page')}:"
                f"{metadata.get('chunk_index')}:"
                f"{hash(chunk.text)}"
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(chunk)

        return deduped
