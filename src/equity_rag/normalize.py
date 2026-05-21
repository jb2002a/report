def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def normalize_company_name(company_name: str) -> str:
    return " ".join(company_name.strip().split())


def normalize_report_date(report_date: str) -> str:
    return report_date.strip()
