from typing import Any

from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    ticker: str
    company_name: str
    source: str
    report_date: str
    file_name: str
    document_type: str = "equity_research_report"


class ParsedPage(BaseModel):
    page: int
    markdown: str


class ParsedChunk(BaseModel):
    text: str
    metadata: dict[str, Any]
    chunk_index: int
    is_table: bool = False


class RetrievedChunk(BaseModel):
    text: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionQuery(BaseModel):
    section: str
    query: str
    top_k: int | None = None  # section-specific override; None → use settings default


class SectionSummary(BaseModel):
    section: str
    summary: str
    insufficient_context: bool = False
    retrieved_chunk_count: int = 0


class SourceInfo(BaseModel):
    source: str
    file_name: str | None = None
    report_date: str | None = None


class BrokerSectionSummary(BaseModel):
    source: str
    section: str
    summary: str
    file_name: str | None = None
    report_date: str | None = None
    retrieved_chunk_count: int = 0


class SectionBrokerBundle(BaseModel):
    section: str
    section_title_kr: str
    broker_summaries: list[BrokerSectionSummary]
    comparison: str = ""
    numeric_hints: str = ""


class GeneratedReport(BaseModel):
    ticker: str
    company_name: str
    content: str
    section_summaries: list[SectionSummary] = Field(default_factory=list)
    source_registry: list[SourceInfo] = Field(default_factory=list)
    section_bundles: list[SectionBrokerBundle] = Field(default_factory=list)
    report_mode: str = "by_source"
    output_path: str | None = None


class IngestionResult(BaseModel):
    ticker: str
    company_name: str
    file_name: str
    chunk_count: int
    table_chunk_count: int
    page_count: int
    chunk_export_path: str | None = None
