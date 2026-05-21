from __future__ import annotations

from pathlib import Path

from equity_rag.config import Settings, get_settings
from equity_rag.ingestion.chunk_export import (
    default_chunk_export_path,
    export_chunks_markdown,
)
from equity_rag.ingestion.chunker import chunk_markdown_pages
from equity_rag.ingestion.parser import parse_pdf_to_markdown
from equity_rag.normalize import (
    normalize_company_name,
    normalize_report_date,
    normalize_ticker,
)
from equity_rag.observability.langsmith import configure_langsmith, trace_metadata, traceable
from equity_rag.schemas import IngestionResult, ReportMetadata
from equity_rag.vectorstore.chroma_store import ChromaStore


@traceable(name="ingest_pdf")
def ingest_pdf(
    pdf_path: str | Path,
    ticker: str,
    company_name: str,
    source: str,
    report_date: str,
    settings: Settings | None = None,
    export_chunks_path: str | Path | None = None,
) -> IngestionResult:
    settings = settings or get_settings()
    configure_langsmith(settings)

    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    normalized_ticker = normalize_ticker(ticker)
    normalized_company = normalize_company_name(company_name)
    normalized_date = normalize_report_date(report_date)

    metadata = ReportMetadata(
        ticker=normalized_ticker,
        company_name=normalized_company,
        source=source.strip(),
        report_date=normalized_date,
        file_name=pdf.name,
    )

    pages = parse_pdf_to_markdown(pdf, settings)
    base_metadata = metadata.model_dump()
    chunks = chunk_markdown_pages(
        pages=pages,
        base_metadata=base_metadata,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        min_text_chars=settings.chunk_min_text_chars,
    )

    if not chunks:
        raise ValueError(f"No chunks generated from PDF: {pdf}")

    chunk_export_path: str | None = None
    if export_chunks_path is not None:
        export_path = Path(export_chunks_path)
    elif settings.export_debug_chunks:
        export_path = default_chunk_export_path(pdf, settings.debug_chunks_dir)
    else:
        export_path = None

    if export_path is not None:
        saved = export_chunks_markdown(
            chunks,
            export_path,
            source_file=pdf.name,
        )
        chunk_export_path = str(saved)

    store = ChromaStore(settings)
    store.upsert_chunks(chunks)

    table_chunk_count = sum(1 for chunk in chunks if chunk.is_table)
    result = IngestionResult(
        ticker=normalized_ticker,
        company_name=normalized_company,
        file_name=pdf.name,
        chunk_count=len(chunks),
        table_chunk_count=table_chunk_count,
        page_count=len(pages),
        chunk_export_path=chunk_export_path,
    )

    _ = trace_metadata(
        workflow="pdf_ingestion",
        ticker=result.ticker,
        company_name=result.company_name,
        file_name=result.file_name,
        parsed_page_count=result.page_count,
        generated_chunk_count=result.chunk_count,
        table_chunk_count=result.table_chunk_count,
    )
    return result
