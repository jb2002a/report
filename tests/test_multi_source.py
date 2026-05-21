from equity_rag.rag.multi_source_report import discover_sources_for_ticker
from equity_rag.rag.prompts import (
    BROKER_SECTION_SUMMARY_PROMPT,
    PROMPT_VERSION,
    RETRIEVAL_ANALYSIS_PROMPT,
)
from equity_rag.rag.retrieval_analyzer import group_chunks_by_source
from equity_rag.schemas import RetrievedChunk
from equity_rag.rag.section_titles import SECTION_TITLES_KR
from equity_rag.schemas import SourceInfo
from equity_rag.vectorstore.retriever import ReportRetriever


def test_prompt_version_is_v8():
    assert PROMPT_VERSION == "v8"


def test_broker_prompt_forbids_insufficient_wording():
    text = BROKER_SECTION_SUMMARY_PROMPT.format_messages(
        ticker="삼성전기",
        company_name="삼성전기",
        section_name="밸류에이션",
        source="메리츠증권",
        file_name="삼성전기_메리츠.pdf",
        report_date="2026-05-20",
        context="sample",
        section_focus="",
    )[0].content
    assert "근거 부족" in text or "Do NOT say" in text


def test_section_titles_kr_covers_all_sections():
    assert len(SECTION_TITLES_KR) == 6


def test_discover_sources_raises_when_empty(monkeypatch):
    class FakeStore:
        def list_sources_for_ticker(self, ticker: str):
            return []

    def fake_chroma(settings):
        return FakeStore()

    monkeypatch.setattr(
        "equity_rag.rag.multi_source_report.ChromaStore",
        lambda settings: FakeStore(),
    )

    try:
        discover_sources_for_ticker("삼성전기", settings=object())  # type: ignore[arg-type]
        raised = False
    except ValueError as exc:
        raised = True
        assert "No ingested sources" in str(exc)
    assert raised


def test_discover_sources_filters_requested(monkeypatch):
    registry = [
        SourceInfo(source="메리츠증권", file_name="a.pdf", report_date="2026-05-20"),
        SourceInfo(source="미래에셋증권", file_name="b.pdf", report_date="2026-05-20"),
    ]

    class FakeStore:
        def list_sources_for_ticker(self, ticker: str):
            return registry

    monkeypatch.setattr(
        "equity_rag.rag.multi_source_report.ChromaStore",
        lambda settings: FakeStore(),
    )

    selected = discover_sources_for_ticker(
        "삼성전기",
        settings=object(),  # type: ignore[arg-type]
        sources=["미래에셋증권"],
    )
    assert len(selected) == 1
    assert selected[0].source == "미래에셋증권"


def test_retriever_builds_source_filter():
    filters = ReportRetriever._build_metadata_filters("삼성전기", "메리츠증권")
    keys = [item.key for item in filters]
    assert keys == ["ticker", "source"]


def test_retrieval_analysis_prompt_structure():
    messages = RETRIEVAL_ANALYSIS_PROMPT.format_messages(
        ticker="삼성전기",
        company_name="삼성전기",
        section_name="밸류에이션",
        scope_label="메리츠증권",
        context="sample",
    )
    human = messages[1].content
    assert "### 핵심 분석" in human
    assert "### 확인된 수치" in human


def test_group_chunks_by_source():
    chunks = [
        RetrievedChunk(text="a", metadata={"source": "메리츠증권"}),
        RetrievedChunk(text="b", metadata={"source": "미래에셋"}),
        RetrievedChunk(text="c", metadata={"source": "메리츠증권"}),
    ]
    grouped = group_chunks_by_source(chunks)
    assert set(grouped.keys()) == {"메리츠증권", "미래에셋"}
    assert len(grouped["메리츠증권"]) == 2
