from equity_rag.vectorstore.retrieval_rerank import rerank_chunks_for_section
from equity_rag.rag.multi_source_report import _strip_broker_summary_header
from equity_rag.schemas import RetrievedChunk


def test_rerank_deprioritizes_valuation_chunks_for_industry_supply():
    valuation_chunk = RetrievedChunk(
        text="적정주가 700,000원 PER 33.8배 상승여력",
        score=0.9,
        metadata={"is_table": True, "page": 11},
    )
    supply_chunk = RetrievedChunk(
        text="MLCC 수급 타이트 가동률 90% ASP 상승",
        score=0.7,
        metadata={"is_table": False, "page": 8},
    )
    ranked = rerank_chunks_for_section(
        "industry_supply", [valuation_chunk, supply_chunk], top_k=1
    )
    assert ranked[0].text.startswith("MLCC")


def test_strip_broker_summary_header():
    raw = "### 메리츠증권 자료 요약\n- bullet one"
    assert _strip_broker_summary_header(raw, "메리츠증권") == "- bullet one"
