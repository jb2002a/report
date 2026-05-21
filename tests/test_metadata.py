from equity_rag.ingestion.chunker import _is_markdown_table, chunk_markdown_pages
from equity_rag.schemas import ParsedPage, ReportMetadata
from equity_rag.vectorstore.chroma_store import ChromaStore


def test_report_metadata_required_fields():
    metadata = ReportMetadata(
        ticker="AAPL",
        company_name="Apple Inc.",
        source="Morgan Stanley",
        report_date="2026-05-01",
        file_name="aapl.pdf",
    )
    dumped = metadata.model_dump()
    assert dumped["ticker"] == "AAPL"
    assert dumped["document_type"] == "equity_research_report"


def test_table_chunk_preservation():
    markdown = """# Valuation

| Metric | 2025E | 2026E |
| --- | --- | --- |
| Revenue | 100 | 120 |
| EPS | 1.2 | 1.5 |
"""
    pages = [ParsedPage(page=1, markdown=markdown)]
    base_metadata = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "source": "Test Broker",
        "report_date": "2026-05-01",
        "file_name": "test.pdf",
        "document_type": "equity_research_report",
    }
    chunks = chunk_markdown_pages(pages, base_metadata, chunk_size=500, chunk_overlap=50)
    table_chunks = [chunk for chunk in chunks if chunk.is_table]
    assert table_chunks
    assert "| Revenue |" in table_chunks[0].text
    assert "| EPS |" in table_chunks[0].text


def test_is_markdown_table():
    table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    assert _is_markdown_table(table)
    assert not _is_markdown_table("plain paragraph text")


def test_chroma_metadata_sanitization():
    sanitized = ChromaStore._sanitize_metadata(
        {
            "ticker": "AAPL",
            "page": 3,
            "chunk_index": 1,
            "is_table": True,
            "extra": {"nested": "value"},
        }
    )
    assert sanitized["ticker"] == "AAPL"
    assert sanitized["page"] == 3
    assert sanitized["extra"] == "{'nested': 'value'}"
