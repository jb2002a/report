from pathlib import Path

from equity_rag.ingestion.chunk_export import (
    default_chunk_export_path,
    export_chunks_markdown,
)
from equity_rag.schemas import ParsedChunk


def test_default_chunk_export_path():
    path = default_chunk_export_path(
        Path("data/raw_pdfs/삼성전기/삼성전기_메리츠.pdf"),
        Path("./data/debug_chunks"),
    )
    assert path == Path("./data/debug_chunks/삼성전기_메리츠.chunks.md")


def test_export_chunks_markdown(tmp_path: Path):
    chunks = [
        ParsedChunk(
            text="# Valuation\n\n| Metric | Value |\n| --- | --- |\n| PER | 20 |",
            metadata={
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "source": "Test Broker",
                "report_date": "2026-05-01",
                "file_name": "test.pdf",
                "page": 2,
                "chunk_index": 0,
                "is_table": True,
            },
            chunk_index=0,
            is_table=True,
        ),
        ParsedChunk(
            text="Apple revenue grew strongly in 2026.",
            metadata={
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "source": "Test Broker",
                "report_date": "2026-05-01",
                "file_name": "test.pdf",
                "page": 3,
                "chunk_index": 1,
                "is_table": False,
            },
            chunk_index=1,
            is_table=False,
        ),
    ]

    output_path = tmp_path / "test.chunks.md"
    saved = export_chunks_markdown(chunks, output_path, source_file="test.pdf")
    content = saved.read_text(encoding="utf-8")

    assert saved.exists()
    assert "# Chunk Export: test.pdf" in content
    assert "## Chunk 0" in content
    assert "- is_table: True" in content
    assert "| PER | 20 |" in content
    assert "## Chunk 1" in content
    assert "Apple revenue grew strongly in 2026." in content
