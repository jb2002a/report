from equity_rag.rag.section_titles import SECTION_TITLES
from equity_rag.schemas import SectionQuery

# top_k: number of chunks to retrieve for this section.
# - recent_performance / outlook: higher because quarterly/annual tables are
#   often split across multiple chunks.
# - valuation: highest because peer comparison tables are large and numerous.
# - investment_thesis: higher to capture narrative thesis paragraphs (not only rating tables).
# - industry_supply: supply/demand, utilization, ASP — narrative over valuation tables.
FIXED_QUERIES: list[dict] = [
    {
        "section": "business_overview",
        "top_k": 6,
        "query": (
            "{ticker} {company_name} 사업 구조 사업부 부문 segment 매출 비중 "
            "주력 사업 제품 서비스 사업 개요 컴포넌트 패키지 광학 솔루션 "
            "연결 매출 사업부문 매출 구성 revenue mix business overview"
        ),
    },
    {
        "section": "recent_performance",
        "top_k": 8,
        "query": (
            "{ticker} {company_name} 실적 매출액 영업이익 영업이익률 순이익 EPS "
            "분기 1Q 2Q 3Q 4Q QoQ YoY 컨센서스 서프라이즈 상회 하회 "
            "Preview 실적 발표 latest earnings quarterly results"
        ),
    },
    {
        "section": "investment_thesis",
        "top_k": 8,
        "query": (
            "{ticker} {company_name} 투자의견 투자 포인트 핵심 논리 성장 동력 "
            "catalyst 구조적 차별화 유일 경쟁 우위 적정주가 상향 목표주가 상향 "
            "상승여력 저평가 Peer Buy 매수 Overweight 비중확대 "
            "사업 구조 글로벌 공급망 편입 수혜 모멘텀 투자 매력 thesis recommendation"
        ),
    },
    {
        "section": "industry_supply",
        "top_k": 6,
        "query": (
            "{ticker} {company_name} 산업 수급 공급 수요 가동률 utilization "
            "ASP 판가 가격 인상 가격 협상 재고 수준 inventory "
            "생산 능력 캐파 capacity CAPEX 증설 원자재 원가 "
            "업황 industry cycle supply demand tight pricing"
        ),
    },
    {
        "section": "valuation",
        "top_k": 10,
        "query": (
            "{ticker} {company_name} 밸류에이션 valuation 목표주가 적정주가 "
            "PER PBR EV EBITDA ROE BPS 멀티플 peer comparable peers "
            "상승여력 괴리율 target price upside"
        ),
    },
    {
        "section": "outlook",
        "top_k": 8,
        "query": (
            "{ticker} {company_name} 전망 추정 컨센서스 매출 전망 영업이익 전망 "
            "2025 2026 2027E 2028E forecast estimates 추정치 변경 "
            "가이던스 성장률 향후 outlook guidance"
        ),
    },
]

def build_fixed_queries(ticker: str, company_name: str) -> list[SectionQuery]:
    queries: list[SectionQuery] = []
    for item in FIXED_QUERIES:
        queries.append(
            SectionQuery(
                section=item["section"],
                query=item["query"].format(
                    ticker=ticker,
                    company_name=company_name,
                ),
                top_k=item.get("top_k"),
            )
        )
    return queries
