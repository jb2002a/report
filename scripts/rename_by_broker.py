"""Rename PDFs to {한글티커}_{증권사명}.pdf using PDF text heuristics."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from pypdf import PdfReader

RAW_PDFS_DIR = Path(__file__).resolve().parents[1] / "data" / "raw_pdfs"

# (pattern in text, normalized broker label) — longer / more specific first
BROKER_RULES: list[tuple[str, str]] = [
    ("DAISHIN SECURITIES", "대신"),
    ("daishin.com", "대신"),
    ("www.daishin.com", "대신"),
    ("imeritz.com", "메리츠"),
    ("meritz.com", "메리츠"),
    ("Kyobo Company Analysis", "교보"),
    ("kyobo.com", "교보"),
    ("sks.co.kr", "SK증권"),
    ("SK SECURITIES", "SK증권"),
    ("미래에셋증권", "미래에셋"),
    ("미래에셋", "미래에셋"),
    ("메리츠증권", "메리츠"),
    ("메리츠", "메리츠"),
    ("유안타증권", "유안타"),
    ("유안타", "유안타"),
    ("대신증권", "대신"),
    ("IBK투자증권", "IBK"),
    ("IBK투자", "IBK"),
    ("IBK", "IBK"),
    ("KB증권", "KB"),
    ("NH투자증권", "NH투자"),
    ("한국투자증권", "한국투자"),
    ("삼성증권", "삼성"),
    ("신한투자증권", "신한투자"),
    ("하나증권", "하나"),
    ("키움증권", "키움"),
    ("현대차증권", "현대차"),
    ("교보증권", "교보"),
    ("BNK투자증권", "BNK"),
    ("iM증권", "iM"),
    ("한화투자증권", "한화투자"),
]

# Known mapping from pre-rename filenames (folder -> ordered brokers)
LEGACY_ORDER_BROKERS: dict[str, list[str]] = {
    "두산에너빌리티": ["IBK", "대신", "미래에셋"],
    "삼성전기": ["메리츠", "미래에셋", "유안타"],
}


def extract_text(pdf_path: Path, max_pages: int = 5) -> str:
    reader = PdfReader(str(pdf_path))
    pages = min(max_pages, len(reader.pages))
    return "\n".join((reader.pages[i].extract_text() or "") for i in range(pages))


def detect_broker(text: str) -> str | None:
    hits: list[tuple[int, str]] = []
    for pattern, label in BROKER_RULES:
        index = text.find(pattern)
        if index >= 0:
            hits.append((index, label))
    if not hits:
        return None
    hits.sort(key=lambda item: item[0])
    return hits[0][1]


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def rename_in_folder(folder: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    ticker = folder.name
    pdfs = sorted(folder.glob("*.pdf"))
    planned: list[tuple[Path, Path]] = []
    used_names: set[str] = set()

    legacy_brokers = LEGACY_ORDER_BROKERS.get(ticker, [])

    for index, pdf_path in enumerate(pdfs):
        text = extract_text(pdf_path)
        broker = detect_broker(text)

        if broker is None and index < len(legacy_brokers):
            broker = legacy_brokers[index]

        if broker is None:
            broker = f"미확인{index + 1:02d}"

        base = safe_filename(f"{ticker}_{broker}")
        dest_name = f"{base}.pdf"
        counter = 2
        while dest_name in used_names:
            dest_name = f"{base}_{counter}.pdf"
            counter += 1
        used_names.add(dest_name)

        dest_path = folder / dest_name
        planned.append((pdf_path, dest_path))

    # two-phase rename to avoid collisions
    temp_moves: list[tuple[Path, Path]] = []
    for src, dest in planned:
        if src.name == dest.name:
            continue
        temp = folder / f"__tmp__{src.stem}.pdf"
        if not dry_run:
            shutil.move(str(src), str(temp))
        temp_moves.append((temp, dest))

    results: list[tuple[str, str]] = []
    for temp, dest in temp_moves:
        results.append((temp.name.replace("__tmp__", "").replace(".pdf", "") + ".pdf", dest.name))
        if not dry_run:
            shutil.move(str(temp), str(dest))

    # include unchanged
    for src, dest in planned:
        if src.name == dest.name:
            results.append((src.name, dest.name))

    return results


def main() -> None:
    all_results: dict[str, list[tuple[str, str]]] = {}
    for folder in sorted(RAW_PDFS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        results = rename_in_folder(folder, dry_run=False)
        all_results[folder.name] = results
        print(f"\n=== {folder.name} ===")
        for old, new in results:
            print(f"  {old} -> {new}")

    total = sum(len(v) for v in all_results.values())
    print(f"\nRenamed {total} files under {RAW_PDFS_DIR}")


if __name__ == "__main__":
    main()
