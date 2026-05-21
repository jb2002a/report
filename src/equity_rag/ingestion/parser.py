from __future__ import annotations

from pathlib import Path

from equity_rag.config import Settings
from equity_rag.schemas import ParsedPage

# Domain-specific instruction for Korean equity research reports.
# Tells LlamaParse to preserve financial tables, collapse charts to one line,
# and skip recurring page-header patterns.
_KO_EQUITY_INSTRUCTION = """\
이 문서는 한국 증권사의 주식 리서치 리포트입니다. 다음 규칙을 따라 변환하세요.

1. 재무 테이블(실적, 밸류에이션, 피어 비교 등)은 마크다운 테이블 형식으로 정확히 변환하세요.
   - 헤더 행과 단위 행을 보존하고, 숫자 데이터는 그대로 유지하세요.
2. 바 차트, 선 그래프, 파이 차트 등 시각적 차트는 좌표나 픽셀 데이터를 테이블로 변환하지 마세요.
   - 대신 [CHART: <차트 제목>] 한 줄로 표시하세요.
3. 각 페이지 상단에 반복되는 '종목명 (6자리 숫자코드)' 형식의 헤더(예: '삼성전기 (009150)')는 제외하세요.
4. 하드웨어 다이어그램, 블록도, 플로우차트 등 이미지 내부 라벨은 별도 텍스트로 추출하지 마세요.
   - [DIAGRAM: <제목>] 한 줄로 표시하세요.
5. 한국어 텍스트가 여러 줄로 나뉘어 있어도 하나의 문단으로 합쳐주세요.
"""


def parse_pdf_to_markdown(pdf_path: Path, settings: Settings) -> list[ParsedPage]:
    if not settings.llama_cloud_api_key:
        raise ValueError(
            "LLAMA_CLOUD_API_KEY is required for LlamaParse PDF parsing."
        )

    from llama_parse import LlamaParse

    parser = LlamaParse(
        api_key=settings.llama_cloud_api_key,
        result_type="markdown",
        verbose=False,
        language="ko",
        parsing_instruction=_KO_EQUITY_INSTRUCTION,
    )
    documents = parser.load_data(str(pdf_path))

    pages: list[ParsedPage] = []
    for index, document in enumerate(documents, start=1):
        page_number = _extract_page_number(document.metadata, index)
        markdown = (document.text or "").strip()
        if markdown:
            pages.append(ParsedPage(page=page_number, markdown=markdown))

    if not pages:
        raise ValueError(f"No markdown content parsed from PDF: {pdf_path}")

    return pages


def _extract_page_number(metadata: dict | None, fallback: int) -> int:
    if not metadata:
        return fallback

    for key in ("page", "page_number", "page_label"):
        value = metadata.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return fallback
