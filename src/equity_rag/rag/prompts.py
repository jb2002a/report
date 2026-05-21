from langchain_core.prompts import ChatPromptTemplate

PROMPT_VERSION = "v8"

# --- Legacy unified mode (optional --mode unified) ---
SECTION_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are an equity research analyst.\n"
                "Write an evidence-first Korean summary for the section: {section_name}.\n"
                "Use only the provided context. Do not invent facts, estimates, ratings, "
                "target prices, or financial figures.\n"
                "Prioritize evidence such as revenue, operating income, margin, EPS, guidance, "
                "valuation multiples, target price, analyst rating, dates, and source attribution.\n"
                "If the context is insufficient, clearly state in Korean that the evidence is "
                "insufficient for this section.\n"
                "Every numeric claim must keep its source/date/page when available.\n"
                "Keep important financial terminology in natural English when appropriate."
            ),
        ),
        (
            "human",
            (
                "Ticker: {ticker}\n"
                "Company: {company_name}\n"
                "Section: {section_name}\n\n"
                "Context:\n{context}\n\n"
                "Return:\n"
                "### 핵심 판단\n"
                "- 2-4 Korean bullets. Each bullet must be grounded in the context.\n\n"
                "### 주요 근거\n"
                "- Bullet list with source/date/page/file whenever available.\n"
                "- Include exact figures from the context, but do not calculate new figures.\n\n"
                "### 근거 한계\n"
                "- State what is missing or uncertain for this section."
            ),
        ),
    ]
)

FINAL_REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a senior equity research analyst writing a comprehensive investment "
                "analysis report in Korean.\n"
                "Use only the section summaries provided below. Do not add unsupported claims.\n"
                "If a section has insufficient evidence, preserve that limitation clearly.\n"
                "Preserve source/date/page/file citations from the section summaries.\n"
                "Do not smooth over evidence gaps with generic positive or negative language.\n"
                "Keep financial terminology such as revenue, operating margin, EPS, PER, "
                "EV/EBITDA, guidance, target price, consensus, and catalyst naturally in English "
                "where useful."
            ),
        ),
        (
            "human",
            (
                "Write the report in the exact structure:\n\n"
                "# {company_name} ({ticker}) 종합 분석 리포트\n\n"
                "## 1. Executive Summary\n"
                "## 2. Business Overview\n"
                "## 3. Recent Performance\n"
                "## 4. Investment Thesis\n"
                "## 5. Industry & Supply\n"
                "## 6. Valuation\n"
                "## 7. Outlook\n"
                "## 8. Conclusion\n\n"
                "Rules:\n"
                "- Each section except Executive Summary and Conclusion should include "
                "evidence bullets when evidence exists.\n"
                "- If evidence is weak, say so explicitly instead of filling the section.\n"
                "- Conclusion must separate supported takeaways from remaining evidence gaps.\n\n"
                "Section summaries:\n{section_summaries}"
            ),
        ),
    ]
)

# --- Multi-source (by_source) mode ---
BROKER_SECTION_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are an equity research analyst summarizing ONE broker's research material.\n"
                "Broker/source: {source}\n"
                "Section: {section_name}\n"
                "Write in Korean. Use ONLY the provided context from this broker.\n"
                "Do not invent figures, ratings, or target prices.\n"
                "Do not calculate new figures beyond reading tables.\n"
                "Preserve units exactly as in the context (e.g. 십억원, 억원, 원).\n"
                "For large amounts, always include the unit from the source table (십억원 vs 억원 vs 조).\n"
                "Never convert 조 to 억 or 십억 without the exact figure from context.\n"
                "Do NOT say '근거 부족' or 'insufficient evidence'.\n"
                "If a topic is not in the context, write: '해당 자료에서 명시 없음' for that item only.\n"
                "FORBIDDEN: meta-descriptions such as '~에 대한 정보 제공', "
                "'~관련 내용 포함', '~언급', '~제시' without the actual fact.\n"
                "REQUIRED: each bullet must start with a concrete number, direct quote, "
                "or analyst judgment from the context.\n"
                "REQUIRED: every bullet with a number must end with (p.N, {file_name}) "
                "when page is known.\n"
                "REQUIRED: when context contains tables, quote key rows as bullets with exact figures.\n"
                "{section_focus}"
            ),
        ),
        (
            "human",
            (
                "Ticker: {ticker}\n"
                "Company: {company_name}\n"
                "Broker: {source}\n"
                "File: {file_name}\n"
                "Report date: {report_date}\n"
                "Section: {section_name}\n\n"
                "Context:\n{context}\n\n"
                "Return exactly:\n"
                "### {source} 자료 요약\n"
                "- 4-8 Korean bullets of concrete facts from this broker's context only.\n"
                "- Each bullet: specific figure/claim first, then (p.N, {file_name}) when page known.\n"
                "- Never write bullets that only say information was provided or mentioned.\n"
                "- Use '해당 자료에서 명시 없음' only for sub-topics missing from context."
            ),
        ),
    ]
)

RETRIEVAL_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are an equity research analyst interpreting retrieved document chunks.\n"
                "Write a concise Korean analysis for the section using ONLY the retrieved context.\n"
                "Do not invent numbers, ratings, or target prices.\n"
                "Preserve units exactly (십억원, 억원, 원).\n"
                "Every numeric bullet must cite (p.N, file_name) when page is known.\n"
                "Do not say '근거 부족'. Missing topics: '해당 검색 결과에서 명시 없음'.\n"
                "Do not calculate new figures beyond simple reading from tables."
            ),
        ),
        (
            "human",
            (
                "Ticker: {ticker}\n"
                "Company: {company_name}\n"
                "Section: {section_name}\n"
                "Scope: {scope_label}\n\n"
                "Retrieved context:\n{context}\n\n"
                "Return exactly:\n"
                "### 핵심 분석\n"
                "- 3-5 Korean bullets: what the retrieved material implies for this section.\n\n"
                "### 확인된 수치\n"
                "- Bullets with exact figures from context; each ends with (p.N, file) when possible.\n\n"
                "### 주의·한계\n"
                "- 1-2 bullets: unit ambiguity, missing columns, or topics not in retrieved chunks."
            ),
        ),
    ]
)

SECTION_CROSS_SOURCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You compare multiple Korean brokerage research summaries for the same section.\n"
                "Do not invent numbers. Do not average or merge target prices into one figure.\n"
                "Highlight agreement and disagreement across brokers.\n"
                "REQUIRED: output a markdown comparison table FIRST when any numeric field exists.\n"
                "Bullets-only output without a table is forbidden when numbers are present.\n"
                "Use the automated numeric_hints block (십억원-normalized) as the primary basis "
                "for amount comparison rows. Broker bullets are secondary.\n"
                "FORBIDDEN: wrong unit conversions such as 1십억원=100억원 or 1조=100십억원. "
                "Correct: 1십억원=10억원, 1조=1,000십억원.\n"
                "Do not put different metric types in one row (e.g. 총매출 vs 순매출, 연결 OPM vs "
                "부문 ASP scenario margin, 1Q actual vs FY forecast).\n"
                "Do not use ⚠ or similar warning symbols anywhere in the output.\n"
                "When brokers disagree, describe it briefly in plain Korean in the 비고 column "
                "(e.g. 단위·정의·기간 차이 가능) without alarm symbols.\n"
                "When EPS/PER differ sharply across brokers, note in 비고 if definitions may differ "
                "(e.g. forecast year, diluted vs basic, consolidated vs separate).\n"
                "Never say '근거 부족'."
            ),
        ),
        (
            "human",
            (
                "Ticker: {ticker}\n"
                "Company: {company_name}\n"
                "Section: {section_name}\n\n"
                "Broker summaries:\n{broker_summaries}\n\n"
                "Automated numeric normalization (십억원):\n{numeric_hints}\n\n"
                "Return exactly:\n"
                "### 증권사 비교 ({section_name})\n"
                "| 항목 | (each broker column) | 비고 |\n"
                "- Fill table only with figures explicitly stated in summaries.\n"
                "- Below the table, 2-4 Korean bullets on consensus vs divergence."
            ),
        ),
    ]
)

EXEC_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You write ONLY the Executive Summary (section 1) for a Korean multi-broker "
                "equity research synthesis.\n"
                "Use ONLY the section bundles provided. Do not invent numbers.\n"
                "Do not merge target prices into one figure; cite broker-specific values.\n"
                "Never use '근거 부족' or 'insufficient evidence'.\n"
                "Clearly separate quarterly (1Q/2Q) results from full-year (FY) forecasts "
                "when citing margins or earnings.\n"
                "Do not use ⚠ or similar warning symbols.\n"
                "Write 4-6 concise Korean paragraphs or bullets covering: consensus themes, "
                "key broker disagreements, ratings/target-price spread, and near-term catalysts."
            ),
        ),
        (
            "human",
            (
                "Ticker: {ticker}\n"
                "Company: {company_name}\n\n"
                "Sources:\n{source_registry}\n\n"
                "Section bundles:\n{section_bundles}\n\n"
                "Return ONLY:\n"
                "## 1. Executive Summary\n"
                "(Korean content; no other sections)"
            ),
        ),
    ]
)

CONCLUSION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You write ONLY the final conclusion (section 9) for a Korean multi-broker "
                "equity research synthesis.\n"
                "Use ONLY the section bundles provided. Do not invent new numeric estimates.\n"
                "Summarize: common themes across brokers, largest disagreements (with broker names), "
                "and what remains uncertain or not stated in the materials.\n"
                "Do not use ⚠ or similar warning symbols.\n"
                "Never use '근거 부족' or 'insufficient evidence'."
            ),
        ),
        (
            "human",
            (
                "Ticker: {ticker}\n"
                "Company: {company_name}\n\n"
                "Sources:\n{source_registry}\n\n"
                "Section bundles:\n{section_bundles}\n\n"
                "Return ONLY:\n"
                "## 9. 종합 결론\n"
                "(Korean content; no other sections)"
            ),
        ),
    ]
)

BROKER_SECTION_FOCUS: dict[str, str] = {
    "industry_supply": (
        "Section focus: industry dynamics, supply/demand balance, utilization rates, "
        "ASP/pricing trends, capacity and CAPEX, raw material costs, and inventory. "
        "Do NOT include target prices, ratings, PER/PBR, or financial ratio tables."
    ),
    "business_overview": (
        "Section focus: describe business segments, revenue mix, and strategic positioning. "
        "Avoid utilization-rate scenario tables unless they explain segment structure."
    ),
    "investment_thesis": (
        "Section focus: prioritize analyst investment arguments and structural advantages "
        "from early report pages; avoid historical target-price tables at the end of reports."
    ),
}

# Legacy: full-report single LLM pass (optional)
MULTI_SOURCE_FINAL_REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You write a comprehensive Korean equity research synthesis using ONLY the "
                "broker-specific summaries and cross-broker comparisons provided.\n"
                "Structure: per-section broker views, then cross-broker comparison, then "
                "overall synthesis.\n"
                "Do not invent numbers. Do not merge target prices into a single value; "
                "show ranges or broker-specific figures with attribution.\n"
                "Never use the phrases '근거 부족' or 'insufficient evidence'.\n"
                "When brokers disagree, state the disagreement clearly with source names.\n"
                "Preserve units (십억원, 억원, 원) as given in the input."
            ),
        ),
        (
            "human",
            (
                "Write the report in this exact structure:\n\n"
                "# {company_name} ({ticker}) 다중 증권사 리서치 종합\n\n"
                "## 1. Executive Summary\n"
                "## 2. 분석 자료\n"
                "## 3. Business Overview (사업 개요)\n"
                "## 4. Recent Performance (최근 실적)\n"
                "## 5. Investment Thesis (투자 논리)\n"
                "## 6. Industry & Supply (산업·수급)\n"
                "## 7. Valuation (밸류에이션)\n"
                "## 8. Outlook (전망)\n"
                "## 9. 종합 결론\n\n"
                "Rules for sections 3-8:\n"
                "- Under each section, include subsections per broker (### 메리츠증권 등).\n"
                "- Then include the cross-broker comparison subsection from the input.\n"
                "- Section 2 must be a table: broker | file | report_date from the registry.\n"
                "- Section 9: common themes, key disagreements, no new numeric estimates.\n\n"
                "Source registry:\n{source_registry}\n\n"
                "Section bundles (broker summaries + comparisons):\n{section_bundles}"
            ),
        ),
    ]
)
