"""Organize PDFs under data/raw_pdfs/{한글티커명}/{한글티커명}_00x.pdf."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

# 한글 티커명 (폴더명 = 파일 prefix)
KOREAN_TICKERS: dict[str, str] = {
    "SK": "SK",
    "034020": "두산에너빌리티",
    "009150": "삼성전기",
    "068270": "셀트리온",
    "004170": "신세계",
    "015760": "한국전력",
}

# resources 폴더 기준 (초기 이동 시)
RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"
RAW_PDFS_DIR = Path(__file__).resolve().parents[1] / "data" / "raw_pdfs"

LEGACY_PREFIX_RE = re.compile(r"^(\d{6}|SK)_(\d{3})\.pdf$", re.IGNORECASE)


def _korean_ticker_from_legacy(filename: str) -> str | None:
    match = LEGACY_PREFIX_RE.match(filename)
    if not match:
        return None
    prefix = match.group(1).upper()
    if prefix == "SK":
        return "SK"
    return KOREAN_TICKERS.get(prefix)


def organize_from_resources() -> int:
    """Move PDFs from resources/{회사}/ to raw_pdfs/{한글티커}/{한글티커}_00x.pdf."""
    count = 0
    for folder_name in KOREAN_TICKERS.values():
        source_dir = RESOURCES_DIR / folder_name
        if not source_dir.is_dir():
            continue
        ticker_dir = RAW_PDFS_DIR / folder_name
        ticker_dir.mkdir(parents=True, exist_ok=True)
        for index, pdf_path in enumerate(sorted(source_dir.glob("*.pdf")), start=1):
            dest = ticker_dir / f"{folder_name}_{index:03d}.pdf"
            if dest.exists():
                dest.unlink()
            shutil.move(str(pdf_path), str(dest))
            print(f"{pdf_path} -> {dest.relative_to(RAW_PDFS_DIR.parent)}")
            count += 1
    return count


def reorganize_flat_to_folders() -> int:
    """Reorganize flat numeric-ticker PDFs into per-ticker folders."""
    count = 0
    for pdf_path in sorted(RAW_PDFS_DIR.glob("*.pdf")):
        korean_ticker = _korean_ticker_from_legacy(pdf_path.name)
        if not korean_ticker:
            print(f"Skip (unknown pattern): {pdf_path.name}")
            continue
        match = LEGACY_PREFIX_RE.match(pdf_path.name)
        assert match is not None
        seq = match.group(2)
        ticker_dir = RAW_PDFS_DIR / korean_ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        dest = ticker_dir / f"{korean_ticker}_{seq}.pdf"
        if dest.exists() and dest.resolve() != pdf_path.resolve():
            dest.unlink()
        shutil.move(str(pdf_path), str(dest))
        print(f"{pdf_path.name} -> {dest.relative_to(RAW_PDFS_DIR.parent)}")
        count += 1
    return count


def main() -> None:
    RAW_PDFS_DIR.mkdir(parents=True, exist_ok=True)

    flat_pdfs = list(RAW_PDFS_DIR.glob("*.pdf"))
    resource_pdfs = [
        p for name in KOREAN_TICKERS.values() for p in (RESOURCES_DIR / name).glob("*.pdf")
        if (RESOURCES_DIR / name).is_dir()
    ]

    if flat_pdfs:
        count = reorganize_flat_to_folders()
        print(f"\nReorganized {count} PDFs into Korean ticker folders under {RAW_PDFS_DIR}")
    elif resource_pdfs:
        count = organize_from_resources()
        print(f"\nMoved {count} PDFs from resources/ to {RAW_PDFS_DIR}")
    else:
        print("No PDFs found to organize.")


if __name__ == "__main__":
    main()
