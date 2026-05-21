from __future__ import annotations

from pathlib import Path

from equity_rag.schemas import ParsedChunk


def default_chunk_export_path(pdf_path: Path, debug_chunks_dir: Path) -> Path:
    stem = pdf_path.stem
    return debug_chunks_dir / f"{stem}.chunks.md"


def export_chunks_markdown(
    chunks: list[ParsedChunk],
    output_path: Path,
    *,
    source_file: str | None = None,
) -> Path:
    """Write all parsed chunks to a human-readable Markdown file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = source_file or output_path.stem.replace(".chunks", "")
    lines: list[str] = [
        f"# Chunk Export: {title}",
        "",
        f"- Total chunks: {len(chunks)}",
        f"- Table chunks: {sum(1 for chunk in chunks if chunk.is_table)}",
        "",
    ]

    for chunk in chunks:
        metadata = chunk.metadata
        lines.extend(
            [
                f"## Chunk {chunk.chunk_index}",
                "",
                f"- page: {metadata.get('page', 'unknown')}",
                f"- is_table: {chunk.is_table}",
                f"- ticker: {metadata.get('ticker', 'unknown')}",
                f"- company_name: {metadata.get('company_name', 'unknown')}",
                f"- source: {metadata.get('source', 'unknown')}",
                f"- report_date: {metadata.get('report_date', 'unknown')}",
                f"- file_name: {metadata.get('file_name', 'unknown')}",
                f"- char_count: {len(chunk.text)}",
                "",
                chunk.text,
                "",
                "---",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
