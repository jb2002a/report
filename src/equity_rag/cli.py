from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from equity_rag.config import Settings, get_settings
from equity_rag.ingestion.chunk_export import default_chunk_export_path
from equity_rag.ingestion.pipeline import ingest_pdf
from equity_rag.normalize import normalize_company_name, normalize_ticker
from equity_rag.rag.fixed_queries import build_fixed_queries
from equity_rag.rag.multi_source_report import discover_sources_for_ticker
from equity_rag.rag.report_generator import generate_report
from equity_rag.rag.retrieval_analyzer import RetrievalAnalyzer
from equity_rag.rag.section_titles import SECTION_TITLES_KR
from equity_rag.vectorstore.retriever import ReportRetriever
from equity_rag.vectorstore.chroma_store import ChromaStore

app = typer.Typer(help="Equity Report RAG MVP CLI")
console = Console()


@app.command("ingest")
def ingest_command(
    pdf: Path = typer.Option(..., "--pdf", help="Path to equity research PDF"),
    ticker: str = typer.Option(..., "--ticker", help="Stock ticker"),
    company_name: str = typer.Option(..., "--company-name", help="Company name"),
    source: str = typer.Option(..., "--source", help="Broker or research source"),
    report_date: str = typer.Option(..., "--report-date", help="Report date (YYYY-MM-DD)"),
    export_chunks: bool = typer.Option(
        False,
        "--export-chunks",
        help="Export generated chunks to a Markdown file for debugging.",
    ),
    export_chunks_path: Path | None = typer.Option(
        None,
        "--export-chunks-path",
        help="Optional Markdown path. Defaults to data/debug_chunks/<pdf_stem>.chunks.md",
    ),
) -> None:
    """Ingest a PDF report into ChromaDB."""
    settings = get_settings()
    chunk_export_path = _resolve_chunk_export_path(
        pdf=pdf,
        export_chunks=export_chunks,
        export_chunks_path=export_chunks_path,
        settings=settings,
    )
    result = ingest_pdf(
        pdf_path=pdf,
        ticker=ticker,
        company_name=company_name,
        source=source,
        report_date=report_date,
        settings=settings,
        export_chunks_path=chunk_export_path,
    )
    console.print("[green]Ingestion completed[/green]")
    console.print(f"Ticker: {result.ticker}")
    console.print(f"Company: {result.company_name}")
    console.print(f"File: {result.file_name}")
    console.print(f"Pages: {result.page_count}")
    console.print(f"Chunks: {result.chunk_count}")
    console.print(f"Table chunks: {result.table_chunk_count}")
    if result.chunk_export_path:
        console.print(f"Chunk export: {result.chunk_export_path}")


@app.command("generate")
def generate_command(
    ticker: str = typer.Option(..., "--ticker", help="Stock ticker"),
    company_name: str = typer.Option(..., "--company-name", help="Company name"),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Optional markdown output path",
    ),
    mode: str = typer.Option(
        "by_source",
        "--mode",
        help="Report mode: by_source (per-broker, default) or unified (legacy single merge)",
    ),
    source: list[str] = typer.Option(
        None,
        "--source",
        help="Limit to specific broker source(s). Repeat flag for multiple. Default: all ingested.",
    ),
) -> None:
    """Generate a Korean investment report (multi-broker by default)."""
    settings = get_settings()
    if mode not in ("by_source", "unified"):
        console.print(f"[red]Invalid mode:[/red] {mode}. Use by_source or unified.")
        raise typer.Exit(code=1)

    if output is None:
        suffix = "_multi_source_report.md" if mode == "by_source" else "_report.md"
        output = settings.outputs_dir / f"{ticker}{suffix}"

    report = generate_report(
        ticker=ticker,
        company_name=company_name,
        output_path=output,
        settings=settings,
        mode=mode,
        sources=source,
    )
    console.print("[green]Report generated[/green]")
    console.print(f"Mode: {report.report_mode}")
    console.print(f"Ticker: {report.ticker}")
    console.print(f"Company: {report.company_name}")
    if report.source_registry:
        console.print(f"Sources: {', '.join(s.source for s in report.source_registry)}")
    if report.output_path:
        console.print(f"Saved to: {report.output_path}")
    console.print("\n" + report.content)


@app.command("sources")
def sources_command(
    ticker: str = typer.Option(..., "--ticker", help="Stock ticker"),
) -> None:
    """List ingested broker sources for a ticker."""
    settings = get_settings()
    normalized_ticker = normalize_ticker(ticker)
    try:
        sources = discover_sources_for_ticker(normalized_ticker, settings)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Sources for {normalized_ticker}")
    table.add_column("Source")
    table.add_column("File")
    table.add_column("Report date")
    for item in sources:
        table.add_row(
            item.source,
            item.file_name or "-",
            item.report_date or "-",
        )
    console.print(table)


@app.command("count")
def count_command() -> None:
    """Show number of stored chunks in ChromaDB."""
    settings = get_settings()
    store = ChromaStore(settings)
    count = store.count()
    console.print(f"Collection: {settings.chroma_collection_name}")
    console.print(f"Stored chunks: {count}")


@app.command("sections")
def sections_command(
    ticker: str = typer.Option(..., "--ticker", help="Stock ticker"),
    company_name: str = typer.Option(..., "--company-name", help="Company name"),
) -> None:
    """List fixed RAG queries for a ticker."""
    queries = build_fixed_queries(
        normalize_ticker(ticker),
        normalize_company_name(company_name),
    )
    table = Table(title="Fixed Queries")
    table.add_column("Section")
    table.add_column("Query")
    for query in queries:
        table.add_row(query.section, query.query)
    console.print(table)


@app.command("retrieve")
def retrieve_command(
    ticker: str = typer.Option(..., "--ticker", help="Stock ticker"),
    company_name: str = typer.Option(..., "--company-name", help="Company name"),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Filter retrieval to one broker (metadata.source, e.g. 메리츠증권).",
    ),
    section: str | None = typer.Option(
        None,
        "--section",
        help="Optional section name. If omitted, retrieve all fixed sections.",
    ),
    top_k: int | None = typer.Option(
        None,
        "--top-k",
        help="Override retrieval top-k for this debug run.",
    ),
    max_chars: int = typer.Option(
        1200,
        "--max-chars",
        help="Maximum characters to print per retrieved chunk.",
    ),
    analyze: bool = typer.Option(
        False,
        "--analyze",
        help="Run LLM analysis on retrieved chunks (Korean summary with citations).",
    ),
    analyze_only: bool = typer.Option(
        False,
        "--analyze-only",
        help="Skip chunk listing; print section analysis only (implies --analyze).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Save retrieve + analysis to a markdown file.",
    ),
) -> None:
    """Debug retrieved chunks; optionally analyze them per section."""
    settings = get_settings()
    normalized_ticker = normalize_ticker(ticker)
    normalized_company = normalize_company_name(company_name)
    queries = build_fixed_queries(normalized_ticker, normalized_company)
    do_analyze = analyze or analyze_only
    show_chunks = not analyze_only

    if section:
        queries = [query for query in queries if query.section == section]
        if not queries:
            valid_sections = ", ".join(query.section for query in build_fixed_queries(normalized_ticker, normalized_company))
            console.print(f"[red]Unknown section:[/red] {section}")
            console.print(f"Valid sections: {valid_sections}")
            raise typer.Exit(code=1)

    retriever = ReportRetriever(settings)
    analyzer = RetrievalAnalyzer(settings, retriever=retriever) if do_analyze else None
    report_parts: list[str] = [
        f"# Retrieve & Analysis: {normalized_company} ({normalized_ticker})",
        "",
    ]
    if source:
        report_parts.append(f"- Filter source: {source}")
    if do_analyze:
        report_parts.append("- Analysis: enabled")
    report_parts.append("")

    for query in queries:
        chunks = retriever.retrieve(
            ticker=normalized_ticker,
            section_query=query,
            top_k=top_k,
            source=source,
        )
        section_kr = SECTION_TITLES_KR.get(query.section, query.section)
        label = query.section if not source else f"{query.section} [{source}]"
        console.rule(f"{label} ({len(chunks)} chunks)")
        console.print(f"[bold]Query:[/bold] {query.query}")

        report_parts.append(f"## {section_kr} (`{query.section}`)")
        report_parts.append("")
        report_parts.append(f"**Query:** {query.query}")
        report_parts.append("")

        if not chunks:
            console.print("[yellow]No chunks retrieved.[/yellow]")
            report_parts.append("*No chunks retrieved.*")
            report_parts.append("")
            continue

        if show_chunks:
            for index, chunk in enumerate(chunks, start=1):
                metadata = chunk.metadata
                score = f"{chunk.score:.4f}" if chunk.score is not None else "unknown"
                header = (
                    f"**Chunk {index}** score={score} | "
                    f"chunk_index={metadata.get('chunk_index', 'unknown')} | "
                    f"is_table={metadata.get('is_table', 'unknown')} | "
                    f"source={metadata.get('source', 'unknown')} | "
                    f"date={metadata.get('report_date', 'unknown')} | "
                    f"page={metadata.get('page', 'unknown')} | "
                    f"file={metadata.get('file_name', 'unknown')}"
                )
                console.print("\n" + header)
                body = _truncate_text(chunk.text, max_chars=max_chars)
                console.print(body)
                report_parts.append(header)
                report_parts.append("")
                report_parts.append(f"```\n{body}\n```")
                report_parts.append("")

        if analyzer is not None:
            console.print("\n[bold cyan]── 섹션 분석 ──[/bold cyan]")
            analysis = analyzer.analyze_section(
                ticker=normalized_ticker,
                company_name=normalized_company,
                section_query=query,
                chunks=chunks,
                source_filter=source,
            )
            console.print(analysis)
            report_parts.append("### 섹션 분석")
            report_parts.append("")
            report_parts.append(analysis)
            report_parts.append("")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(report_parts), encoding="utf-8")
        console.print(f"\n[green]Saved to:[/green] {output}")


def _resolve_chunk_export_path(
    pdf: Path,
    export_chunks: bool,
    export_chunks_path: Path | None,
    settings: Settings,
) -> Path | None:
    if export_chunks_path is not None:
        return export_chunks_path
    if export_chunks or settings.export_debug_chunks:
        return default_chunk_export_path(pdf, settings.debug_chunks_dir)
    return None


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
