# Equity Report RAG MVP

증권사/리서치 PDF 리포트를 기반으로 ticker별 RAG 검색을 수행하고, 한국어 종합 투자 분석 보고서를 생성하는 Python MVP입니다.

## Stack

- **LlamaParse / LlamaIndex**: table-aware PDF parsing 및 embedding
- **ChromaDB**: `equity_reports` collection 벡터 저장
- **LangChain**: fixed query, section summary, final report synthesis
- **LangSmith**: ingestion / retrieval / summarization / report generation tracing

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
```

`.env`에 다음 값을 설정합니다.

- `OPENAI_API_KEY`
- `LLAMA_CLOUD_API_KEY`
- `LANGSMITH_API_KEY` (선택, tracing 사용 시)

## CLI

PDF ingestion:

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli ingest `
  --pdf data/raw_pdfs/aapl_morgan_stanley_2026_05_01.pdf `
  --ticker AAPL `
  --company-name "Apple Inc." `
  --source "Morgan Stanley" `
  --report-date 2026-05-01
```

리포트 생성 (기본: 증권사별 수집 → 비교 → 종합, `by_source` 모드):

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli generate `
  --ticker 삼성전기 `
  --company-name "삼성전기" `
  --output data/outputs/삼성전기_multi_source_report.md
```

티커에 ingest된 증권사 목록 확인:

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli sources --ticker 삼성전기
```

특정 증권사만 포함:

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli generate `
  --ticker 삼성전기 `
  --company-name "삼성전기" `
  --source 메리츠증권 `
  --source 미래에셋증권
```

증권사 단위 retrieval 디버그:

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 삼성전기 --company-name "삼성전기" `
  --source 메리츠증권 --section valuation
```

검색 결과 + LLM 섹션 분석 (chunk 나열 후 해석, 또는 분석만):

```powershell
# chunk + 분석
.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 삼성전기 --company-name "삼성전기" `
  --source 메리츠증권 --section valuation --analyze

# 분석만 (과제용 요약)
.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 삼성전기 --company-name "삼성전기" `
  --analyze-only `
  --output data/outputs/삼성전기_retrieve_analysis.md

# 증권사 필터 없으면 source별로 분석 블록을 나눠 출력
.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 삼성전기 --company-name "삼성전기" --section outlook --analyze-only
```

레거리 단일 합성 모드 (`근거 한계` 문구 포함):

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli generate `
  --ticker 삼성전기 --company-name "삼성전기" --mode unified
```

저장된 chunk 수 확인:

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli count
```

청킹 결과를 Markdown으로 저장 (디버그):

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli ingest `
  --pdf data/raw_pdfs/삼성전기/삼성전기_메리츠.pdf `
  --ticker 삼성전기 `
  --company-name "삼성전기" `
  --source "메리츠증권" `
  --report-date 2026-05-20 `
  --export-chunks
```

기본 저장 경로: `data/debug_chunks/<pdf_stem>.chunks.md`  
또는 `.env`에서 `EXPORT_DEBUG_CHUNKS=true`로 ingest마다 자동 저장할 수 있습니다.

청킹 품질 관련 설정:

- `CHUNK_MIN_TEXT_CHARS=80` — 짧은 텍스트 fragment 병합 기준
- 제목(`# ...`)은 다음 본문/표와 자동 병합
- Compliance/페이지 마커/헤더 푸터 노이즈 제외

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn equity_rag.api:app --reload
```

- `GET /health`
- `GET /collections/count`
- `POST /ingest`
- `POST /reports/generate`

## Workflow

1. PDF를 markdown으로 파싱 (LlamaParse)
2. markdown table을 보존하며 chunk 생성
3. metadata(`ticker`, `company_name`, `source`, `report_date`, `file_name`, `document_type`, `page`)와 함께 ChromaDB 저장
4. 6개 fixed query로 ticker-filtered retrieval
5. 섹션별 한국어 요약 생성
6. 최종 종합 리포트 합성

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Notes

- LangGraph는 사용하지 않습니다. 현재 workflow는 선형적이며 함수형 서비스 레이어로 구성합니다.
- retrieved context가 부족한 섹션은 추측하지 않고 근거 부족을 명시합니다.
- LangSmith UI에서 run별 retrieval 품질과 unsupported claim 여부를 검토할 수 있습니다.


문서개선사항
heading-only chunk를 다음 본문/표와 병합 (# LPU... + Chunk 17 본문)
최소 길이 필터 (예: 텍스트 80자 미만은 버리거나 이웃 chunk와 merge, 표 제외)
# 그림N 캡션은 바로 다음 표/문단과 묶기
Compliance/면책/페이지 번호 chunk 제외 (Compliance Notice, CI21:, 단독 숫자)
표 chunk는 section heading을 prefix로 붙이기 (예: ## 실적 전망 + 표)
동일 ticker 리포트 2~3개 ingest로 coverage 보강