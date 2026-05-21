from equity_rag.normalize import (
    normalize_company_name,
    normalize_report_date,
    normalize_ticker,
)


def test_normalize_ticker():
    assert normalize_ticker(" aapl ") == "AAPL"


def test_normalize_company_name():
    assert normalize_company_name("  Apple   Inc.  ") == "Apple Inc."


def test_normalize_report_date():
    assert normalize_report_date(" 2026-05-01 ") == "2026-05-01"
