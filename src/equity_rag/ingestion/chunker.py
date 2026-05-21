from __future__ import annotations

import html as _html
import re
from typing import Any

from equity_rag.schemas import ParsedChunk, ParsedPage

HEADING_PATTERN = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)
FIGURE_HEADING_PATTERN = re.compile(r"^#\s*그림\s*\d+", re.IGNORECASE)
DIAGRAM_MARKER_PATTERN = re.compile(r"^\[(?:CHART|DIAGRAM):", re.IGNORECASE)
PAGE_NUMBER_PATTERN = re.compile(r"^\d{1,2}$")
CI21_PATTERN = re.compile(r"^CI21:\s*\d+\s*$", re.IGNORECASE)
FOOTNOTE_PATTERN = re.compile(r"^주:\s", re.MULTILINE)
# Matches Korean company name + 6-digit stock code used as page headers
# e.g. "삼성전기 (009150)" or "SK하이닉스 (000660)"
KR_TICKER_HEADER_PATTERN = re.compile(r"^[가-힣a-zA-Z0-9\s·]+\s*\(\d{6}\)\s*$")
# Numeric / year / quarter cell — used for chart noise detection
_CHART_CELL_PATTERN = re.compile(r"^-?[\d,\.]+%?$|^'?\d{2,4}(?:[HQ]\d)?$")

DEFAULT_MIN_TEXT_CHARS = 150
MIN_KEEP_CHARS = 20

COMPLIANCE_MARKERS = (
    "compliance notice",
    "본 조사분석자료는 제3자에게",
    "본 자료는 투자자들의 투자판단",
    "따라서 어떠한 경우에도 본 자료는",
)


def chunk_markdown_pages(
    pages: list[ParsedPage],
    base_metadata: dict[str, Any],
    chunk_size: int = 1000,
    chunk_overlap: int = 120,
    min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    chunk_index = 0

    for page in pages:
        cleaned = _clean_markdown(page.markdown)
        blocks = _split_into_blocks(cleaned)
        blocks = _postprocess_blocks(blocks, min_text_chars=min_text_chars)

        for block in blocks:
            is_table = _block_contains_markdown_table(block)
            block_chunks = (
                _split_table_block(block, chunk_size)
                if is_table
                else _split_text_block(block, chunk_size, chunk_overlap)
            )

            for block_chunk in block_chunks:
                if _is_noise_block(block_chunk):
                    continue

                metadata = {
                    **base_metadata,
                    "page": page.page,
                    "chunk_index": chunk_index,
                    "is_table": is_table,
                }
                chunks.append(
                    ParsedChunk(
                        text=block_chunk,
                        metadata=metadata,
                        chunk_index=chunk_index,
                        is_table=is_table,
                    )
                )
                chunk_index += 1

    return chunks


def _clean_markdown(markdown: str) -> str:
    # Decode HTML entities produced by LlamaParse (e.g. &#x26; → &)
    markdown = _html.unescape(markdown)
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if _looks_like_header_footer(stripped):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _looks_like_header_footer(line: str) -> bool:
    if not line:
        return False

    lowered = line.lower()
    if PAGE_NUMBER_PATTERN.match(line):
        return True
    if CI21_PATTERN.match(line):
        return True
    if len(line) == 1 and line.isalpha():
        return True
    # Korean stock ticker page header: e.g. "삼성전기 (009150)"
    if KR_TICKER_HEADER_PATTERN.match(line):
        return True

    patterns = (
        "page ",
        "confidential",
        "equity research",
        "all rights reserved",
        "meritz securities",
        "meritz research",
        "@meritz.co.kr",
    )
    if any(pattern in lowered for pattern in patterns) and len(line) < 120:
        return True
    if line.startswith("Analyst ") and len(line) < 80:
        return True

    return False


def _split_into_blocks(markdown: str) -> list[str]:
    if not markdown:
        return []

    blocks: list[str] = []
    current: list[str] = []
    pending_heading: str | None = None
    lines = markdown.splitlines()

    def flush_current() -> None:
        nonlocal current, pending_heading
        if not current:
            return
        text = "\n".join(current).strip()
        if pending_heading:
            text = f"{pending_heading}\n\n{text}"
            pending_heading = None
        blocks.append(text)
        current = []

    def attach_heading(content: str) -> str:
        nonlocal pending_heading
        if pending_heading:
            merged = f"{pending_heading}\n\n{content}"
            pending_heading = None
            return merged
        return content

    index = 0
    while index < len(lines):
        line = lines[index]

        if line.strip().startswith("|"):
            flush_current()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            blocks.append(attach_heading("\n".join(table_lines).strip()))
            continue

        if HEADING_PATTERN.match(line):
            flush_current()
            pending_heading = line.strip()
            index += 1
            continue

        if not line.strip():
            flush_current()
            index += 1
            continue

        current.append(line)
        index += 1

    flush_current()
    if pending_heading and not _is_orphan_figure_heading(pending_heading):
        blocks.append(pending_heading)

    return [block for block in blocks if block]


def _postprocess_blocks(blocks: list[str], min_text_chars: int) -> list[str]:
    filtered: list[str] = []
    for block in blocks:
        if _is_noise_block(block):
            continue
        if FOOTNOTE_PATTERN.match(block.strip()) and filtered:
            filtered[-1] = f"{filtered[-1]}\n\n{block.strip()}"
            continue
        filtered.append(block)

    return _merge_short_text_blocks(filtered, min_chars=min_text_chars)


def _merge_short_text_blocks(blocks: list[str], min_chars: int) -> list[str]:
    result: list[str] = []
    carry = ""

    for block in blocks:
        if _is_markdown_table(block):
            if carry:
                result.append(carry)
                carry = ""
            result.append(block)
            continue

        carry = f"{carry}\n\n{block}".strip() if carry else block.strip()
        if len(carry) >= min_chars:
            result.append(carry)
            carry = ""

    if carry:
        if result and len(carry) < min_chars:
            result[-1] = f"{result[-1]}\n\n{carry}"
        elif len(carry) >= MIN_KEEP_CHARS:
            result.append(carry)

    return result


def _is_orphan_figure_heading(text: str) -> bool:
    stripped = text.strip()
    return bool(FIGURE_HEADING_PATTERN.match(stripped)) and "\n" not in stripped


def _is_noise_block(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) <= MIN_KEEP_CHARS and not _is_markdown_table(stripped):
        if PAGE_NUMBER_PATTERN.match(stripped):
            return True
        if CI21_PATTERN.match(stripped):
            return True
        if FIGURE_HEADING_PATTERN.match(stripped):
            return True
        if stripped.startswith("#") and len(stripped) < 40:
            return True

    lowered = stripped.lower()
    if lowered == "compliance notice":
        return True
    if any(marker in stripped for marker in COMPLIANCE_MARKERS):
        return True
    if "meritz securities" in lowered and len(stripped) < 80:
        return True
    # [CHART: ...] / [DIAGRAM: ...] markers generated by parsing_instruction
    if DIAGRAM_MARKER_PATTERN.match(stripped):
        return True
    # Table that looks like chart coordinate/axis data rather than a real table
    if _is_chart_table_noise(stripped):
        return True

    return False


def _is_chart_table_noise(text: str) -> bool:
    """Return True when a markdown table block contains only chart coordinates.

    Heuristic: if the table has ≤4 data columns AND ≥80 % of non-separator
    cells are either empty, pure-numeric, or year/quarter labels, it is almost
    certainly axis/legend data extracted from a bar-chart or line-graph rather
    than a real financial table.
    """
    table_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("|")
    ]
    if len(table_lines) < 2:
        return False

    # Count max columns (excluding separator lines)
    data_lines = [l for l in table_lines if not set(l) <= {"|", "-", ":", " "}]
    if not data_lines:
        return False
    max_cols = max(len(l.split("|")) - 2 for l in data_lines)
    # Real financial tables (peer valuation, earnings) usually have many columns
    if max_cols > 5:
        return False

    cells = [
        cell.strip()
        for line in data_lines
        for cell in line.split("|")[1:-1]
    ]
    if not cells:
        return False

    noise_count = sum(
        1
        for c in cells
        if not c or c in {"-", "---", "·"} or _CHART_CELL_PATTERN.match(c)
    )
    return noise_count / len(cells) >= 0.80


def _is_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    return all(line.startswith("|") and line.endswith("|") for line in lines)


def _block_contains_markdown_table(text: str) -> bool:
    table_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break
    if len(table_lines) < 2:
        return False
    return _is_markdown_table("\n".join(table_lines))


def _split_table_block(table_text: str, chunk_size: int) -> list[str]:
    lines = table_text.splitlines()
    if not lines:
        return []

    # Preserve optional section heading prefix above the table.
    prefix_lines: list[str] = []
    table_start = 0
    for index, line in enumerate(lines):
        if line.strip().startswith("|"):
            table_start = index
            break
        prefix_lines.append(line)

    prefix = "\n".join(prefix_lines).strip()
    table_lines: list[str] = []
    suffix_lines: list[str] = []
    for line in lines[table_start:]:
        if line.strip().startswith("|"):
            table_lines.append(line)
        elif table_lines:
            suffix_lines.append(line)

    suffix = "\n".join(suffix_lines).strip()
    if not table_lines:
        return [table_text] if table_text.strip() else []

    header = table_lines[0]
    separator = (
        table_lines[1]
        if len(table_lines) > 1 and set(table_lines[1]) <= {"|", "-", ":", " "}
        else None
    )
    data_rows = table_lines[2:] if separator else table_lines[1:]

    chunks: list[str] = []
    current_rows: list[str] = []
    current_size = len(header) + (len(prefix) + 2 if prefix else 0)

    def build_chunk(rows: list[str], *, include_suffix: bool = False) -> str:
        body = "\n".join(rows)
        chunk = header
        if separator:
            chunk += "\n" + separator
        chunk += "\n" + body
        if prefix:
            chunk = f"{prefix}\n\n{chunk}"
        if include_suffix and suffix:
            chunk = f"{chunk}\n\n{suffix}"
        return chunk

    for row in data_rows:
        row_size = len(row)
        if current_rows and current_size + row_size > chunk_size:
            chunks.append(build_chunk(current_rows))
            current_rows = []
            current_size = len(header) + (len(separator) if separator else 0)
            if prefix:
                current_size += len(prefix) + 2

        current_rows.append(row)
        current_size += row_size

    if current_rows:
        chunks.append(build_chunk(current_rows, include_suffix=True))

    return chunks or ([table_text] if table_text.strip() else [])


def _split_text_block(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    words = text.split()
    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = start
        current: list[str] = []
        current_len = 0

        while end < len(words):
            word = words[end]
            projected = current_len + len(word) + (1 if current else 0)
            if projected > chunk_size and current:
                break
            current.append(word)
            current_len = projected
            end += 1

        if not current:
            current.append(words[start])
            end = start + 1

        chunks.append(" ".join(current))

        if end >= len(words):
            break

        overlap_words = max(1, chunk_overlap // 5)
        start = max(end - overlap_words, start + 1)

    return chunks
