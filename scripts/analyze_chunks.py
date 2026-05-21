import re
from pathlib import Path

text = Path("data/debug_chunks/삼성전기_메리츠.chunks.md").read_text(encoding="utf-8")
chunks = re.split(r"^## Chunk ", text, flags=re.M)[1:]
stats = []
for block in chunks:
    m_idx = re.search(r"^(\d+)\s*\n", block, re.M)
    m_page = re.search(r"^- page: (\d+)", block, re.M)
    m_table = re.search(r"^- is_table: (True|False)", block, re.M)
    m_chars = re.search(r"^- char_count: (\d+)", block, re.M)
    body = block.split("---", 1)[0]
    body_lines = [
        line
        for line in body.splitlines()
        if line and not line.startswith("- ") and not line.strip().isdigit()
    ]
    body_text = "\n".join(body_lines).strip()
    stats.append(
        {
            "idx": int(m_idx.group(1)) if m_idx else -1,
            "page": int(m_page.group(1)) if m_page else -1,
            "is_table": m_table.group(1) == "True" if m_table else False,
            "chars": int(m_chars.group(1)) if m_chars else len(body_text),
            "body": body_text,
        }
    )

short = [s for s in stats if s["chars"] < 50 and not s["is_table"]]
heading_only = [
    s for s in stats if s["body"].startswith("#") and len(s["body"]) < 80 and not s["is_table"]
]
page_counts: dict[int, int] = {}
for s in stats:
    page_counts[s["page"]] = page_counts.get(s["page"], 0) + 1

print("total", len(stats))
print("table", sum(1 for s in stats if s["is_table"]))
print("text", sum(1 for s in stats if not s["is_table"]))
print("short_text_under_50", len(short))
print("heading_only_under_80", len(heading_only))
print("page1_chunks", page_counts.get(1, 0))
print("pages", min(page_counts), max(page_counts), "distinct", len(page_counts))
print("char_count buckets:")
for lo, hi, label in [(0, 49, "0-49"), (50, 199, "50-199"), (200, 999, "200-999"), (1000, 2000, "1000+")]:
    n = sum(1 for s in stats if lo <= s["chars"] <= hi)
    print(f"  {label}: {n}")
print("top short non-table:")
for s in sorted(short, key=lambda x: x["chars"])[:15]:
    preview = s["body"].replace("\n", " ")[:60]
    print(f"  chunk {s['idx']} page {s['page']} chars {s['chars']}: {preview}")
print("keyword hits in chunk bodies:")
for kw in ["리스크", "위험", "우려", "투자포인트", "목표주가", "MLCC", "LPU", "전망", "Buy", "상향"]:
    hits = [s for s in stats if kw in s["body"]]
    print(f"  {kw}: {len(hits)} chunks")
print("chunks per page:")
for page in sorted(page_counts):
    print(f"  page {page}: {page_counts[page]}")
good = sorted([s for s in stats if s["chars"] >= 400 and not s["is_table"]], key=lambda x: -x["chars"])[:8]
print("largest narrative text chunks:")
for s in good:
    preview = s["body"].replace("\n", " ")[:80]
    print(f"  chunk {s['idx']} page {s['page']} chars {s['chars']}: {preview}")
