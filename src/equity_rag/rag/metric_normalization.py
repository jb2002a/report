"""Normalize Korean financial amounts and flag cross-broker outliers before comparison."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from equity_rag.schemas import BrokerSectionSummary, SectionBrokerBundle

MetricKind = Literal[
    "revenue",
    "operating_income",
    "net_income",
    "margin",
    "eps",
    "target_price",
    "multiple",
    "capex",
    "other",
]

_PERIOD_PATTERNS: list[tuple[str, str]] = [
    (r"1Q\d{2}|1Q26|1Q25|CY1Q", "1Q"),
    (r"2Q\d{2}|2Q26|2Q25", "2Q"),
    (r"3Q\d{2}|3Q26", "3Q"),
    (r"4Q\d{2}|4Q26", "4Q"),
    (r"1분기", "1Q"),
    (r"2분기", "2Q"),
    (r"FY\d{2}|FY26|FY25", "FY"),
    (r"연간", "FY"),
]

_METRIC_RULES: list[tuple[MetricKind, tuple[str, ...]]] = [
    ("target_price", ("목표주가", "적정주가", "목표 주가")),
    ("eps", ("EPS", "eps", "주당순이익", "주당순손익")),
    ("multiple", ("PER", "PBR", "EV/EBITDA", "P/E")),
    ("margin", ("영업이익률", "순이익률", "매출총이익률", "OPM", "이익률")),
    ("capex", ("CAPEX", "CapEx", "capex", "자본적지출", "유형자산의 증가")),
    ("revenue", ("순매출", "총매출", "매출액", "매출")),
    ("operating_income", ("영업이익",)),
    ("net_income", ("지배순이익", "당기순이익", "순이익", "총당기순이익")),
]

# Amount with optional Korean unit (won amounts for EPS/TP handled separately).
_AMOUNT_RE = re.compile(
    r"(?P<value>[\d]{1,3}(?:,[\d]{3})*(?:\.\d+)?|[\d]+(?:\.\d+)?)"
    r"\s*(?P<unit>십억원|십억|억원|억|조원|조|원|배|%|p|%p)?",
    re.IGNORECASE,
)

_BULLET_LINE_RE = re.compile(r"^\s*-\s+(.+)$", re.MULTILINE)

_OUTLIER_RATIO_THRESHOLD = 5.0
_UNIT_SLIP_RATIO = 9.0


@dataclass(frozen=True)
class ExtractedMetric:
    broker: str
    metric_kind: MetricKind
    period: str
    raw_text: str
    value: float
    unit: str
    normalized_shibeok: float | None  # None for %, 배, 원(주당·주가)
    display_normalized: str


def _parse_number(value: str) -> float:
    return float(value.replace(",", ""))


def _detect_period(text: str) -> str:
    for pattern, label in _PERIOD_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    year = re.search(r"20\d{2}", text)
    if year:
        return year.group(0)
    return "unspecified"


def _detect_metric_kind(text: str) -> MetricKind:
    for kind, keywords in _METRIC_RULES:
        for keyword in keywords:
            if keyword in text:
                return kind
    return "other"


def _to_shibeok(value: float, unit: str) -> float | None:
    u = unit.strip()
    if not u or u in {"%", "p", "배"}:
        return None
    if u == "원":
        return None
    if u in {"십억원", "십억"}:
        return value
    if u in {"억원", "억"}:
        return value / 10.0
    if u in {"조원", "조"}:
        return value * 1000.0
    return None


def _format_shibeok(value: float) -> str:
    text = f"{value:,.1f}".rstrip("0").rstrip(".")
    return f"{text}십억원"


def _extract_amounts_from_line(line: str) -> list[tuple[float, str]]:
    """Return (numeric value, unit) pairs found in a bullet line."""
    results: list[tuple[float, str]] = []
    for match in _AMOUNT_RE.finditer(line):
        unit = (match.group("unit") or "").strip()
        raw_value = match.group("value")
        try:
            value = _parse_number(raw_value)
        except ValueError:
            continue
        if unit in {"%", "p", "배"}:
            continue
        if unit == "원" and value >= 100_000:
            continue
        if not unit and value < 100:
            continue
        if unit or value >= 100:
            results.append((value, unit))
    return results


def extract_metrics_from_summary(
    broker: str, summary: str
) -> list[ExtractedMetric]:
    metrics: list[ExtractedMetric] = []
    for match in _BULLET_LINE_RE.finditer(summary):
        line = match.group(1).strip()
        if "명시 없음" in line:
            continue
        kind = _detect_metric_kind(line)
        period = _detect_period(line)
        amounts = _extract_amounts_from_line(line)
        if not amounts:
            continue
        value, unit = amounts[0]
        if kind in {"eps", "target_price", "multiple", "margin"}:
            normalized = None
            if kind == "margin" and unit in {"%", "p"}:
                display = f"{value}%"
            elif unit == "원" or (kind in {"eps", "target_price"} and not unit):
                display = f"{_format_number_with_commas(value)}원"
            elif unit == "배":
                display = f"{value}배"
            else:
                display = f"{value}{unit}"
        else:
            normalized = _to_shibeok(value, unit)
            if normalized is None and unit == "원":
                continue
            if normalized is None:
                continue
            display = _format_shibeok(normalized)
        metrics.append(
            ExtractedMetric(
                broker=broker,
                metric_kind=kind,
                period=period,
                raw_text=line[:120],
                value=value,
                unit=unit or "(없음)",
                normalized_shibeok=normalized,
                display_normalized=display,
            )
        )
    return metrics


def _format_number_with_commas(value: float) -> str:
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.1f}"


def _metric_label(kind: MetricKind) -> str:
    labels = {
        "revenue": "매출",
        "operating_income": "영업이익",
        "net_income": "순이익",
        "margin": "이익률",
        "eps": "EPS",
        "target_price": "목표주가",
        "multiple": "배수",
        "capex": "CAPEX",
        "other": "기타",
    }
    return labels.get(kind, kind)


def _group_key(metric: ExtractedMetric) -> tuple[MetricKind, str]:
    return (metric.metric_kind, metric.period)


def detect_outliers(
    metrics_by_broker: dict[str, list[ExtractedMetric]],
) -> list[str]:
    """Return Korean warning lines for cross-broker amount inconsistencies."""
    grouped: dict[tuple[MetricKind, str], list[ExtractedMetric]] = {}
    for broker_metrics in metrics_by_broker.values():
        for metric in broker_metrics:
            if metric.normalized_shibeok is None:
                continue
            if metric.metric_kind in {"other", "capex"}:
                continue
            key = _group_key(metric)
            grouped.setdefault(key, []).append(metric)

    warnings: list[str] = []
    for (kind, period), items in grouped.items():
        if len(items) < 2:
            continue
        values = [m.normalized_shibeok for m in items if m.normalized_shibeok]
        if len(values) < 2:
            continue
        low = min(values)
        high = max(values)
        if low <= 0:
            continue
        ratio = high / low
        if ratio < _OUTLIER_RATIO_THRESHOLD:
            continue
        label = _metric_label(kind)
        brokers = ", ".join(
            f"{m.broker}({m.display_normalized})" for m in items
        )
        note = (
            f"- {period} {label}: 증권사 간 차이 약 {ratio:.1f}배 — "
            f"{brokers}. 단위(십억/억/조) 또는 지표 정의(연결/부문·총매출/순매출) 확인 필요."
        )
        if ratio >= _UNIT_SLIP_RATIO:
            note += " (10배 근접 → 십억원 누락·억/십억 혼동 가능성)"
        warnings.append(note)
    return warnings


def build_numeric_hints(
    broker_summaries: list[BrokerSectionSummary],
) -> str:
    """Build a markdown block for the cross-source LLM (십억원-normalized)."""
    metrics_by_broker: dict[str, list[ExtractedMetric]] = {}
    for item in broker_summaries:
        metrics_by_broker[item.source] = extract_metrics_from_summary(
            item.source, item.summary
        )

    brokers = [item.source for item in broker_summaries]
    row_keys: dict[tuple[MetricKind, str], dict[str, str]] = {}

    for broker, metrics in metrics_by_broker.items():
        for metric in metrics:
            if metric.normalized_shibeok is None:
                continue
            if metric.metric_kind in {
                "eps",
                "target_price",
                "multiple",
                "margin",
                "other",
            }:
                continue
            key = _group_key(metric)
            label = f"{metric.period} {_metric_label(metric.metric_kind)}"
            if key not in row_keys:
                row_keys[key] = {"label": label, **dict.fromkeys(brokers, "-")}
            row_keys[key][broker] = metric.display_normalized

    comparable_rows = sorted(row_keys.values(), key=lambda c: c["label"])

    if not comparable_rows and not any(metrics_by_broker.values()):
        return ""

    lines = [
        "### 자동 수치 정규화 (비교용, 금액은 십억원 기준)",
        "",
        "규칙: 1십억원 = 10억원, 1조 = 1,000십억원. "
        "아래 표는 bullet에서 추출·환산한 값이며, 비교표 작성 시 우선 참고하세요.",
        "",
    ]

    if comparable_rows:
        header = "| 지표(기간) | " + " | ".join(brokers) + " |"
        sep = "|" + "|".join(["---"] * (len(brokers) + 1)) + "|"
        lines.extend([header, sep])
        for cells in comparable_rows:
            label = cells["label"]
            row = "| " + label + " | "
            row += " | ".join(cells.get(b, "-") for b in brokers) + " |"
            lines.append(row)
        lines.append("")

    per_broker: list[str] = []
    for item in broker_summaries:
        extracted = metrics_by_broker.get(item.source, [])
        shibeok_lines = [
            f"  - {m.display_normalized} ({_metric_label(m.metric_kind)}, {m.period})"
            for m in extracted
            if m.normalized_shibeok is not None
        ][:8]
        if shibeok_lines:
            per_broker.append(f"- **{item.source}** (십억원 환산):\n" + "\n".join(shibeok_lines))

    if per_broker:
        lines.append("**증권사별 추출 요약:**")
        lines.extend(per_broker)

    return "\n".join(lines).strip()


def format_validation_digest(bundles: list[SectionBrokerBundle]) -> str:
    """Reserved for optional validation digest; currently unused in report output."""
    del bundles
    return ""


def prepare_broker_summaries_for_comparison(
    broker_summaries: list[BrokerSectionSummary],
) -> tuple[str, str]:
    """Return (formatted broker text, numeric hints) for cross-source LLM."""
    formatted = "\n\n".join(
        f"#### {item.source}\n{item.summary}" for item in broker_summaries
    )
    hints = build_numeric_hints(broker_summaries)
    return formatted, hints
