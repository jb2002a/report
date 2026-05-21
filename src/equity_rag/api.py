from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from equity_rag.config import get_settings
from equity_rag.ingestion.pipeline import ingest_pdf
from equity_rag.rag.report_generator import generate_report
from equity_rag.vectorstore.chroma_store import ChromaStore

app = FastAPI(title="Equity Report RAG MVP", version="0.1.0")


class IngestRequest(BaseModel):
    pdf_path: str = Field(..., description="Path to PDF file")
    ticker: str
    company_name: str
    source: str
    report_date: str


class GenerateRequest(BaseModel):
    ticker: str
    company_name: str
    output_path: str | None = None
    mode: str = "by_source"
    sources: list[str] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/collections/count")
def collection_count() -> dict[str, int | str]:
    settings = get_settings()
    store = ChromaStore(settings)
    return {
        "collection": settings.chroma_collection_name,
        "count": store.count(),
    }


@app.post("/ingest")
def ingest_endpoint(request: IngestRequest) -> dict:
    settings = get_settings()
    pdf = Path(request.pdf_path)
    if not pdf.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf}")

    try:
        result = ingest_pdf(
            pdf_path=pdf,
            ticker=request.ticker,
            company_name=request.company_name,
            source=request.source,
            report_date=request.report_date,
            settings=settings,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result.model_dump()


@app.post("/reports/generate")
def generate_endpoint(request: GenerateRequest) -> dict:
    settings = get_settings()
    output_path = request.output_path
    if output_path is None:
        suffix = (
            "_multi_source_report.md"
            if request.mode == "by_source"
            else "_report.md"
        )
        output_path = str(settings.outputs_dir / f"{request.ticker}{suffix}")

    try:
        report = generate_report(
            ticker=request.ticker,
            company_name=request.company_name,
            output_path=output_path,
            settings=settings,
            mode=request.mode,
            sources=request.sources,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ticker": report.ticker,
        "company_name": report.company_name,
        "report_mode": report.report_mode,
        "output_path": report.output_path,
        "content": report.content,
        "source_registry": [s.model_dump() for s in report.source_registry],
        "section_bundles": [b.model_dump() for b in report.section_bundles],
        "sections": [summary.model_dump() for summary in report.section_summaries],
    }
