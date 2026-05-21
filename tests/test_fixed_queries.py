from equity_rag.rag.fixed_queries import FIXED_QUERIES, build_fixed_queries


def test_build_fixed_queries_renders_placeholders():
    queries = build_fixed_queries("AAPL", "Apple Inc.")
    assert len(queries) == len(FIXED_QUERIES)
    assert queries[0].section == "business_overview"
    assert "AAPL" in queries[0].query
    assert "Apple Inc." in queries[0].query


def test_all_sections_present():
    queries = build_fixed_queries("MSFT", "Microsoft Corporation")
    sections = {query.section for query in queries}
    expected = {item["section"] for item in FIXED_QUERIES}
    assert sections == expected


def test_queries_are_sector_agnostic():
    queries = {query.section: query.query for query in build_fixed_queries("삼성전기", "삼성전기")}
    joined = " ".join(queries.values()).lower()
    for sector_term in ("mlcc", "lpu", "abf", "카메라모듈", "패키지기판"):
        assert sector_term not in joined


def test_queries_include_universal_research_terms():
    queries = {query.section: query.query for query in build_fixed_queries("삼성전기", "삼성전기")}
    assert "매출 비중" in queries["business_overview"]
    assert "서프라이즈" in queries["recent_performance"]
    assert "투자의견" in queries["investment_thesis"]
    assert "적정주가" in queries["valuation"]
    assert "추정치 변경" in queries["outlook"]
    assert "수급" in queries["industry_supply"]
    assert "가동률" in queries["industry_supply"]
    assert "risks" not in queries
