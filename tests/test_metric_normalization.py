from equity_rag.rag.metric_normalization import (
    _to_shibeok,
    build_numeric_hints,
    detect_outliers,
    extract_metrics_from_summary,
    format_validation_digest,
)
from equity_rag.schemas import BrokerSectionSummary, SectionBrokerBundle


def test_to_shibeok_units():
    assert _to_shibeok(100, "십억원") == 100
    assert _to_shibeok(2806, "억원") == 280.6
    assert _to_shibeok(3.2, "조") == 3200.0


def test_extract_revenue_and_oi():
    summary = """### 메리츠증권 자료 요약
- 1Q26E 매출액은 3,202.7십억원으로 전년 동기 대비 16.9% 증가하였다 (p.2, a.pdf).
- 1Q26E 영업이익은 261.8십억원으로 컨센서스 대비 5.0% 하회하였다 (p.2, a.pdf).
"""
    metrics = extract_metrics_from_summary("메리츠증권", summary)
    kinds = {m.metric_kind for m in metrics}
    assert "revenue" in kinds
    assert "operating_income" in kinds
    oi = next(m for m in metrics if m.metric_kind == "operating_income")
    assert oi.normalized_shibeok == 261.8


def test_detect_outlier_10x_unit_slip():
    """Same 1Q revenue with 억 vs 십억-style 10x gap (한국전력 패턴)."""
    kyobo = """- 1Q26 매출액은 24,398.5억원 (p.3, a.pdf)."""
    hana = """- 1Q26 매출액은 243,985억원 (p.2, b.pdf)."""
    by_broker = {
        "교보": extract_metrics_from_summary("교보", kyobo),
        "하나": extract_metrics_from_summary("하나", hana),
    }
    warnings = detect_outliers(by_broker)
    assert any("매출" in w for w in warnings)
    assert any("10배" in w or "십억" in w for w in warnings)


def test_build_numeric_hints_includes_normalization_table():
    summaries = [
        BrokerSectionSummary(
            source="메리츠",
            section="recent_performance",
            summary="- 1Q26E 매출액은 3,202.7십억원 (p.2, a.pdf).\n- 1Q26E 영업이익은 261.8십억원 (p.2, a.pdf).",
        ),
        BrokerSectionSummary(
            source="유안타",
            section="recent_performance",
            summary="- 1Q26 영업이익은 2,806억원 (p.1, b.pdf).",
        ),
    ]
    hints = build_numeric_hints(summaries)
    assert "1십억원 = 10억원" in hints
    assert "280.6십억원" in hints or "280.6" in hints
    assert "메리츠" in hints and "유안타" in hints


def test_format_validation_digest_returns_empty():
    bundle = SectionBrokerBundle(
        section="recent_performance",
        section_title_kr="최근 실적",
        broker_summaries=[],
        numeric_hints="**자동 검증 경고:**\n- 1Q 영업이익: 테스트",
    )
    assert format_validation_digest([bundle]) == ""


def test_build_numeric_hints_omits_warning_block():
    summaries = [
        BrokerSectionSummary(
            source="교보",
            section="recent_performance",
            summary="- 1Q26 매출액은 24,398.5억원 (p.3, a.pdf).",
        ),
        BrokerSectionSummary(
            source="하나",
            section="recent_performance",
            summary="- 1Q26 매출액은 243,985억원 (p.2, b.pdf).",
        ),
    ]
    hints = build_numeric_hints(summaries)
    assert "자동 검증 경고" not in hints
    assert "⚠" not in hints
