from equity_rag.ingestion.chunker import chunk_markdown_pages
from equity_rag.schemas import ParsedPage

BASE_METADATA = {
    "ticker": "삼성전기",
    "company_name": "삼성전기",
    "source": "메리츠증권",
    "report_date": "2026-05-20",
    "file_name": "test.pdf",
    "document_type": "equity_research_report",
}


def test_heading_merges_with_following_paragraph():
    markdown = """# LPU 공급망 First Vendor

당사는 NVSwitch 공급에 이어 LPU ABF 기판 퍼스트 벤더로 진입할 것으로 전망한다.
"""
    pages = [ParsedPage(page=1, markdown=markdown)]
    chunks = chunk_markdown_pages(pages, BASE_METADATA, min_text_chars=40)

    assert len(chunks) == 1
    assert "# LPU 공급망 First Vendor" in chunks[0].text
    assert "NVSwitch" in chunks[0].text


def test_heading_merges_with_following_table():
    markdown = """# Valuation

| Metric | 2026E |
| --- | --- |
| EPS | 15,281 |
"""
    pages = [ParsedPage(page=1, markdown=markdown)]
    chunks = chunk_markdown_pages(pages, BASE_METADATA, chunk_size=500)

    assert len(chunks) == 1
    assert "# Valuation" in chunks[0].text
    assert "| EPS |" in chunks[0].text
    assert chunks[0].is_table


def test_orphan_figure_heading_is_dropped():
    markdown = """# 그림3

| A | B |
| --- | --- |
| 1 | 2 |

실리콘 캐패시터는 낮은 전압 영역을 담당한다.
"""
    pages = [ParsedPage(page=1, markdown=markdown)]
    chunks = chunk_markdown_pages(pages, BASE_METADATA, min_text_chars=40)
    texts = [chunk.text for chunk in chunks]

    assert not any(text.strip() == "# 그림3" for text in texts)
    assert any("# 그림3" in text and "| A |" in text for text in texts)
    assert any("실리콘 캐패시터" in text for text in texts)


def test_footnote_merges_into_previous_block():
    markdown = """| 매출 | 100 |
| --- | --- |
| 2026E | 120 |

주: 삼성전기는 당사 추정치 기준, 국내 기업은 십억원이다.
"""
    pages = [ParsedPage(page=3, markdown=markdown)]
    chunks = chunk_markdown_pages(pages, BASE_METADATA)

    table_chunks = [chunk for chunk in chunks if chunk.is_table]
    assert len(table_chunks) == 1
    assert "주: 삼성전기" in table_chunks[0].text


def test_noise_blocks_are_excluded():
    markdown = """meritz Securities    Company Brief

Compliance Notice

본 조사분석자료는 제3자에게 사전 제공된 사실이 없습니다.

# 투자 포인트

전장용 MLCC 수요 회복과 서버 MLCC 매출 성장이 핵심 투자 포인트다.
"""
    pages = [ParsedPage(page=1, markdown=markdown)]
    chunks = chunk_markdown_pages(pages, BASE_METADATA, min_text_chars=40)
    joined = "\n".join(chunk.text for chunk in chunks)

    assert "Compliance Notice" not in joined
    assert "제3자에게 사전 제공" not in joined
    assert "MLCC" in joined


def test_short_fragments_are_merged():
    markdown = """유일무이

# 삼성전기, 적정주가 70만원으로 상향

삼성전기에 대한 적정주가를 70만원으로 상향한다. MLCC와 패키지 기판 성장이 동력이다.
"""
    pages = [ParsedPage(page=1, markdown=markdown)]
    chunks = chunk_markdown_pages(pages, BASE_METADATA, min_text_chars=80)

    assert len(chunks) == 1
    assert "적정주가 70만원" in chunks[0].text
    assert "MLCC" in chunks[0].text
