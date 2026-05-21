# Equity Report RAG — 팀 프로젝트 발표 슬라이드 원고

> 슬라이드 도구(PPT, Google Slides, Canva 등)에 **슬라이드 1장 = `## Slide N`** 단위로 복사해 사용하세요.  
> **본편 16장** (Slide 8 = LangSmith 관측성) | 발표 **7~10분** | 데모 **2~3분**

---

## Slide 1 — 표지

**Multi-Source Evidence RAG for Equity Research**

증권사 리서치 PDF 기반 · 출처 유지 · 다중 증권사 종합 분석 리포트 자동 생성

- 팀명 / 팀원 / 학번(필요 시)
- 과목명 · 제출일
- 한 줄: *“PDF → Multi-Source RAG → 종합 리포트 · **LangSmith 전 구간 추적**”*

---

## Slide 2 — 문제 정의 (Why)

### 애널리스트·리서치 사용자의 Pain Point

| 문제 | 설명 |
|------|------|
| **자료 분산** | 동일 종목에 대해 증권사별 PDF가 따로 존재 |
| **출처 혼선** | 한 번에 요약하면 **어느 증권사 주장인지** 불명확 |
| **지표 불일치** | 총매출 vs 순매출, 십억원 vs 억원, 1Q vs FY 혼용 |
| **표·수치 누락** | 일반 요약 LLM은 **표 단위 근거**와 **페이지 인용**이 약함 |

### 프로젝트 목표 (1차)

> **End-to-end 파이프라인 구현**  
> Ingest → Vector RAG → 증권사별 요약 → 교차 비교 → 종합 Markdown 리포트

※ 정량 벤치마크는 일정상 **범위 외** → Slide 11 참고 · **LangSmith 추적** → Slide 8

---

## Slide 3 — 핵심 아이디어 (What)

### 기존 방식 vs 우리 방식

| | 단일 합성 (Unified) | **우리 방식 (By-Source, 기본)** |
|--|---------------------|----------------------------------|
| Retrieval | ticker만 필터 | **ticker + 증권사(source)** 필터 |
| 요약 | 전 소스 혼합 | **증권사별 독립 요약** |
| 비교 | 최종 합성에 의존 | **섹션마다 증권사 비교표** |
| 출처 | 약함 | **(p.N, 파일명) bullet 인용** |

### 포지셔닝 한 줄

**“ChatGPT에 PDF 붙여넣기”가 아니라, 리서치 워크플로에 맞는 Multi-Source Evidence RAG**

---

## Slide 4 — 시스템 아키텍처

```mermaid
flowchart LR
  PDF[LlamaParse PDF] --> Chunk[Chunker]
  Chunk --> Chroma[(ChromaDB)]
  Chroma --> RAG[6 Fixed Queries × N Brokers]
  RAG --> Sum[Broker Section Summary]
  Sum --> Cmp[Cross-Source Comparison]
  Cmp --> Asm[Programmatic Assembly]
  Asm --> Book[Exec Summary + Conclusion]
  Book --> MD[Markdown Report]
  subgraph LS[LangSmith Tracing]
    PDF -.-> LS
    RAG -.-> LS
    Sum -.-> LS
    Cmp -.-> LS
    Book -.-> LS
  end
```

### 기술 스택

| 계층 | 기술 |
|------|------|
| Parse | LlamaParse (table-aware PDF → Markdown) |
| Vector DB | ChromaDB (`equity_reports`) |
| Embedding | OpenAI `text-embedding-3-small` |
| LLM | OpenAI `gpt-4.1-mini` (LangChain) |
| **Observability** | **LangSmith** — 파이프라인 전 구간 `@traceable` + 메타데이터 |
| Interface | Typer CLI + FastAPI |

### 관측성 한 줄 (발표 멘트)

> ingest·retrieval·요약·비교·리포트 생성까지 **LangSmith로 end-to-end 추적**했습니다. 정량 벤치마크 대신 **run 단위로 chunk 수·섹션·프롬프트 버전**을 남겨 디버깅·정성 검토에 활용했습니다.

---

## Slide 5 — Ingest & Chunking

### PDF → 검색 가능한 Chunk

1. **LlamaParse**: 페이지별 Markdown, 표 보존  
2. **Chunker**: 제목·표·노이즈 후처리  
3. **Metadata**: `ticker`, `company_name`, `source`, `report_date`, `page`, `is_table`  
4. **ChromaDB upsert**

### 청킹 품질 설계 (차별점)

- Heading-only chunk → 다음 본문/표와 **병합**
- Compliance / 페이지 마커 / 헤더 푸터 **제외**
- 표 chunk에 **섹션 제목 prefix** 부여
- 디버그: `data/debug_chunks/*.chunks.md` export

**데모 포인트:** `삼성전기_메리츠.chunks.md` — 표·본문이 어떻게 쪼개졌는지 확인

---

## Slide 6 — Retrieval

### 6개 고정 섹션 쿼리 (Fixed Queries)

| Section | 한글 | top_k (예) |
|---------|------|------------|
| business_overview | 사업 개요 | 6 |
| recent_performance | 최근 실적 | 8 |
| investment_thesis | 투자 논리 | 8 |
| industry_supply | 산업·수급 | 6 |
| valuation | 밸류에이션 | 10 |
| outlook | 전망 | 8 |

### Retrieval 강화

- **Metadata filter**: `ticker` (+ `source` for by-source)  
- **Over-fetch → Rerank**: 섹션별 fetch multiplier  
- **Keyword rerank**: 섹션 부적합 chunk 억제 (예: valuation 표가 industry에 섞이는 것 완화)  
- **Dedupe**: 동일 file/page/chunk_index 중복 제거

### 디버그 CLI

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 삼성전기 --company-name "삼성전기" `
  --source 메리츠증권 --section valuation --analyze
```

→ “블랙박스 RAG가 아님”을 보여주는 슬라이드/데모

---

## Slide 7 — Generation (By-Source 파이프라인)

### 단계별 LLM 역할

| 단계 | 입력 | 출력 |
|------|------|------|
| 1. Broker summary | 해당 증권사 chunks | 4~8 bullets + `(p.N, file)` |
| 2. Cross-source compare | N개 증권사 요약 + **numeric hints** | 비교 Markdown 표 + 해석 bullets |
| 3. Assembly | 코드 조립 | §2~8 본문 (broker bullet 보존) |
| 4. Bookends | section bundles | Executive Summary, 종합 결론 |

### Prompt 설계 (v8) 요지

- **Evidence-first**: context 밖 수치·의견 금지  
- **증권사별 분리**: 타 브로커 내용 혼입 금지  
- **비교표 우선**: 수치 있으면 표 필수  
- **단위 보존**: 십억원/억원/조 임의 환산 금지  
- 본문은 LLM이 **다시 쓰지 않음** → broker 요약 훼손 방지

### LLM 호출 규모 (증권사 3개 예시)

- 요약: 6 섹션 × 3 = **18**  
- 비교: 6  
- 서두·결론: 2  
- **합계 약 26회 / 리포트** (품질 ↔ 비용 trade-off)

---

## Slide 8 — LangSmith 관측성 (Observability)

### 왜 LangSmith를 썼는가

- 정량 평가 시간이 없어도, **파이프라인 각 단계가 무엇을 입력받고 몇 chunk를 썼는지** 추적 필요  
- LLM 호출이 많은 by-source 모드(약 26 runs/리포트)에서 **어느 섹션·증권사에서 실패/빈 retrieval**인지 빠르게 확인  

### 구현 방식 (`equity_rag/observability/langsmith.py`)

| 요소 | 설명 |
|------|------|
| `@traceable(name=...)` | LangSmith **run 트리**에 단계별 span 생성 |
| `configure_langsmith(settings)` | `LANGSMITH_TRACING`, API key, project (`equity-report-rag-mvp`) 설정 |
| `trace_metadata(**kwargs)` | run에 **구조화 메타데이터** 부착 (workflow, ticker, section, chunk 수 등) |

`ingest` / `generate` 진입 시 `configure_langsmith` 호출 → 이후 하위 함수 trace 자동 연결

### `@traceable`이 붙은 파이프라인 단계

| Run name | 모듈 | 역할 |
|----------|------|------|
| `ingest_pdf` | `ingestion/pipeline.py` | PDF 파싱·청킹·Chroma upsert |
| `retrieve_section_context` | `vectorstore/retriever.py` | 섹션별 벡터 검색 + rerank |
| `summarize_section` | `section_summarizer.py` | unified 모드 섹션 요약 |
| `summarize_section_for_source` | `section_summarizer.py` | **증권사별** 섹션 요약 |
| `analyze_retrieved_section` | `retrieval_analyzer.py` | `retrieve --analyze` 디버그 분석 |
| `compare_section_across_sources` | `multi_source_report.py` | 증권사 간 섹션 비교 LLM |
| `build_multi_source_section_bundles` | `multi_source_report.py` | 6섹션 × N broker 번들 생성 |
| `generate_exec_summary` | `multi_source_report.py` | Executive Summary |
| `generate_conclusion` | `multi_source_report.py` | 종합 결론 |
| `synthesize_multi_source_report` | `multi_source_report.py` | 최종 리포트 조립 |
| `generate_report` | `report_generator.py` | CLI/API 리포트 생성 진입점 |

### `trace_metadata` 예시 (슬라이드 표용)

| workflow | 기록 필드 (예) |
|----------|----------------|
| `pdf_ingestion` | ticker, file_name, `parsed_page_count`, `generated_chunk_count`, `table_chunk_count` |
| `retrieval` | ticker, source, section, query, `retrieved_chunk_count`, `insufficient_context` |
| `broker_section_summarization` | source, section, `prompt_version`, `retrieved_chunk_count`, `output_length` |
| `final_report_generation` | `report_mode`, `source_count`, `section_count`, `final_report_length` |

→ LangSmith UI에서 **티커·섹션·증권사별**로 run 필터링 가능

### 설정 (`.env`)

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=equity-report-rag-mvp
```

### 발표 시 보여줄 것 (스크린샷 1~2장)

1. **Projects** → `equity-report-rag-mvp`  
2. `generate_report` run 트리 — 하위에 `summarize_section_for_source`, `compare_section_across_sources` 등 **중첩 span**  
3. 한 run의 **Metadata** — `retrieved_chunk_count`, `prompt_version=v8` 등  

### 발표 멘트 (20초)

> “평가 데이터셋은 만들지 못했지만, **LangSmith에 파이프라인 전 단계를 어노테이션**해 두었습니다. retrieval chunk 수가 0인 섹션, 요약 길이, 프롬프트 버전을 run마다 확인하면서 **정성적으로 품질을 점검**했습니다.”

### 정량 평가 vs LangSmith (구분해서 말하기)

| | 정량 평가 (미수행) | LangSmith 추적 (수행) |
|--|-------------------|----------------------|
| 목적 | accuracy, citation F1 | **재현·디버깅·단계별 관측** |
| 산출 | 점수 표 | run 트리, latency, metadata |
| 발표 표현 | “향후 과제” | “**개발·검증 과정에서 활용**” |

---

## Slide 9 — 수치 비교 보조 (Metric Normalization)

### 문제

증권사마다 **총매출 / 순매출**, **십억 / 억** 표기가 달라 직접 비교 어려움

### 구현 (`metric_normalization.py`)

- Broker bullet에서 금액 **추출**  
- **십억원 기준 환산** 표 → cross-source LLM에 `numeric_hints`로 전달  
- 증권사 간 **5배 이상** 차이 시 outlier 경고 로직 (내부)

### 한계 (솔직히 명시)

- 최종 비교표는 여전히 **LLM이 작성** → 가끔 단위 설명 오류 가능  
- → **정량 평가 + 비교표 코드 생성**이 향후 과제

---

## Slide 10 — 산출물 예시

### 리포트 구조 (`*_report.md`)

```text
# {회사명} ({ticker}) 다중 증권사 리서치 종합

## 1. Executive Summary
## 2. 분석 자료          ← 증권사 | 파일 | report_date 표
## 3. Business Overview  ← ### 교보 / ### 미래 / ### 키움 + 비교표
## 4. Recent Performance
## 5. Investment Thesis
## 6. Industry & Supply
## 7. Valuation
## 8. Outlook
## 9. 종합 결론
```

### 데모에 쓸 티커 (이미 산출물 있음)

| Ticker | 출력 파일 | 특징 |
|--------|-----------|------|
| 신세계 | `data/outputs/신세계_report.md` | 유통, 총매출/순매출 대비 |
| 삼성전기 | `data/outputs/삼성전기_report.md` | 반도체, MLCC/밸류에이션 |
| SK / 한국전력 / 두산에너빌리티 / 셀트리온 | `data/outputs/*_report.md` | 섹터 다양성 |

**스크롤 포인트 (30초):** §2 출처 표 → §4 한 증권사 bullet → §4 비교표

---

## Slide 11 — 범위 · 한계 · 향후 (평가 미수행)

### 이번 프로젝트에서 완료한 것 ✅

- [x] PDF ingest + Chroma vector store  
- [x] 6-section fixed retrieval + section rerank  
- [x] **By-source** multi-broker synthesis (기본 모드)  
- [x] 증권사별 bullet + 섹션별 비교표 + 종합 리포트  
- [x] CLI 디버그 (`retrieve`, `sources`, chunk export)  
- [x] **LangSmith end-to-end 추적** (`@traceable` 11개 단계 + `trace_metadata`)  
- [x] 샘플 티커 다수 end-to-end 산출물  

### 일정상 하지 못한 것 ⏸

- [ ] **정량 평가** (Unified vs By-source, citation rate, unit-error rate)  
- [ ] Human eval / golden Q&A set  
- [ ] 비교표 **완전 deterministic** 생성 (LLM 제거)  

### 대신 한 “검증” (정성)

| 방법 | 설명 |
|------|------|
| **LangSmith** | run 트리·metadata로 retrieval/요약 단계 **추적·점검** |
| Chunk export | 청킹 품질 눈으로 확인 |
| `retrieve --analyze` | 검색 결과 + 섹션 해석 |
| 샘플 리포트 | 6개 티커 실제 MD |
| pytest | rerank, prompt, metric 추출 단위 테스트 |

### 발표 시 한 문장 (권장)

> *“1차 목표는 **동작하는 Multi-Source RAG 파이프라인**이었고, accuracy 벤치마크 대신 **LangSmith로 단계별 run을 추적**하며 정성 검증했습니다. 체계적 점수화 평가는 향후 과제입니다.”*

### 향후 로드맵

1. 비교표를 `build_numeric_hints` 기반 **코드 렌더** → LLM은 해석만  
2. 소규모 golden set + 자동 체크 (인용 패턴, 금지 단위 문구)  
3. Retrieval: hybrid search / 섹터별 query profile  
4. Broker summary 캐싱으로 비용·지연 절감  

---

## Slide 12 — Baseline 비교 (설계만, 실험 미수행)

### 비교 대상 (향후 또는 질문 대비)

| 모드 | CLI | 특징 |
|------|-----|------|
| **By-source (Ours)** | `generate` (기본) | 증권사 분리 + 비교표 |
| Unified (Baseline) | `generate --mode unified` | 단일 retrieval·합성 |

### 기대 가설 (평가 시 검증할 항목)

- By-source → **출처 명확성**, **증권사 간 이견** 표현 ↑  
- Unified → LLM 호출 수 ↓, 단 **출처 혼선** ↑  
- 공통 리스크 → PDF 품질·청킹·단위 오류  

※ **실험 수치는 없음** — 질문 시 “파이프라인 완성 우선”이라고 답변

---

## Slide 13 — 데모 시나리오 (2~3분)

### 사전 준비

- Chroma ingest 완료 상태  
- 터미널 폰트 크게 / 복사해 둔 명령어  

### 시나리오 A — 신세계 (유통, 비교표 강조)

```powershell
# 1) 증권사 목록
.\.venv\Scripts\python.exe -m equity_rag.cli sources --ticker 신세계

# 2) 검색 + 분석 (선택, 30초)
.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 신세계 --company-name "신세계" `
  --source 교보 --section recent_performance --analyze-only

# 3) 리포트 열기
# data/outputs/신세계_report.md → §2, §4 비교표
```

### 시나리오 B — 삼성전기 (청킹 + retrieval)

```powershell
# Chunk 품질 (IDE에서 이미 열려 있으면 탭 전환만)
# data/debug_chunks/삼성전기_메리츠.chunks.md

.\.venv\Scripts\python.exe -m equity_rag.cli retrieve `
  --ticker 삼성전기 --company-name "삼성전기" `
  --source 메리츠증권 --section valuation --analyze-only
```

### 데모 중 말할 멘트

1. “같은 종목이라도 **증권사 필터**로 retrieval이 갈립니다.”  
2. “요약 bullet마다 **페이지·파일**이 붙습니다.”  
3. “섹션 끝에 **증권사 비교표**가 자동으로 붙습니다.”  
4. (선택) LangSmith에서 방금 `generate` run 트리 10초 — “**어노테이션으로 전 과정 추적**”

### 데모 실패 시

- 미리 생성된 `data/outputs/*.md`만 열어도 됨  
- “라이브는 ingest/키 이슈 가능, 산출물은 사전 생성” 한 줄

---

## Slide 14 — 팀 역할 분담 (템플릿)

| 역할 | 담당 | 발표 포인트 |
|------|------|-------------|
| **Data / Ingest** | PDF, chunker, debug export | 청킹 품질, `ingest_pdf` trace |
| **Retrieval** | fixed query, rerank, CLI | `retrieve_section_context` trace |
| **Generation** | prompt v8, multi-source | broker/compare span 트리 |
| **Observability** | LangSmith 설정, trace 설계 | `@traceable` / metadata 표 (Slide 8) |
| **Integration / PM** | CLI, API, 데모, 문서 | E2E, 한계·향후 |

*(이름 채워 넣기)*

---

## Slide 15 — Q&A 예상 답변

| 질문 | 답변 방향 |
|------|-----------|
| ChatGPT와 뭐가 다른가요? | 증권사별 retrieval·인용·비교표·6섹션 구조 |
| 정확도는? | 정량 평가 미수행; **LangSmith run 추적** + evidence-first prompt + 샘플 리포트 정성 검토 |
| 평가는 어떻게 했나요? | 벤치마크 점수는 없음; **LangSmith에 11개 단계 `@traceable`**, metadata로 chunk 수·섹션·prompt v8 기록 |
| LangSmith에서 뭘 보나요? | `generate_report` 트리 → broker 요약·비교 span; metadata의 `retrieved_chunk_count`, `insufficient_context` |
| 환각 안 나요? | context only 규칙 + 근거 부족 시 unified는 명시 (by-source는 ‘명시 없음’) |
| 왜 LangGraph 안 썼나요? | 선형 파이프라인 + **LangSmith span**으로 단계 관측; 에이전트 오케스트레이션은 범위 외 |
| 비용은? | broker 수 × 섹션 수에 비례; LangSmith에서 run별 latency 확인 가능 |
| 상용화? | 리서치 보조 도구 수준 MVP; 단위 검증 layer 필요 |

---

## Slide 16 — 마무리

### Summary

- **Problem:** 멀티 브로커 리서치의 출처·단위·비교 어려움  
- **Solution:** Multi-Source Evidence RAG + section-aware retrieval  
- **Observability:** **LangSmith `@traceable` 어노테이션**으로 ingest~리포트 **전 구간 추적**  
- **Deliverable:** CLI/API + 6개 티커 종합 MD 리포트  
- **Limitation:** 정량 eval 미수행 → LangSmith 기반 정성 점검 + deterministic 비교표가 next step  

### Thank you

- GitHub / 데모 영상 링크 (있으면)  
- 질문 환영  

---

## 부록 A — 발표 7분 타임라인

| 시간 | 내용 |
|------|------|
| 0:00 | 표지 + 문제 (Slide 2) |
| 1:00 | 아이디어 + 아키텍처 (3~4) |
| 2:00 | Ingest / Retrieval / Generation (5~7) 요약 |
| 2:45 | **LangSmith 추적** (Slide 8) — 스크린샷 20초 |
| 3:30 | **라이브 데모** (Slide 13) |
| 6:00 | 산출물 + **한계·향후** (10~11) |
| 6:40 | Q&A |

---

## 부록 B — 슬라이드에 넣을 스크린샷 체크리스트

- [ ] `신세계_report.md` — §2 분석 자료 표  
- [ ] `신세계_report.md` — §4 증권사 비교 표  
- [ ] `삼성전기_메리츠.chunks.md` — 표 chunk 예시 1개  
- [ ] `retrieve --analyze-only` 터미널 출력  
- [ ] **LangSmith** — project `equity-report-rag-mvp` 목록  
- [ ] **LangSmith** — `generate_report` run 트리 (nested spans)  
- [ ] **LangSmith** — run Metadata (`retrieved_chunk_count`, `prompt_version`)  
- [ ] 아키텍처 mermaid (Slide 4, LangSmith subgraph)  

---

## 부록 C — 포스터 / 한 줄 소개 (복사용)

**한국어**  
> 증권사 리서치 PDF에서 증권사별 근거를 분리 검색하고, 6개 투자 섹션별 요약·비교·종합 리포트를 생성하는 Multi-Source Evidence RAG 파이프라인 — **LangSmith로 전 단계 추적**

**English**  
> Multi-source evidence RAG pipeline with broker-attributed retrieval and cross-broker comparison tables, **instrumented with LangSmith tracing** across ingest, retrieval, and generation.

---

## 부록 D — 기술 보고서 목차 (제출용 PDF 확장 시)

1. 서론 및 문제 정의  
2. 관련 연구 (RAG, financial document QA)  
3. 시스템 아키텍처  
4. Ingestion & Chunking  
5. Retrieval (fixed queries, rerank)  
6. Generation (by-source, prompts, metric normalization)  
7. **Observability (LangSmith `@traceable`, trace_metadata)**  
8. 구현 및 CLI/API  
9. **정성 검증 및 한계** (벤치마크 미수행 · LangSmith 추적 수행 명시)  
10. 결론 및 향후 연구  

---

*문서 버전: pipeline 기준 2026-05 | prompt v8 | default mode `by_source` | LangSmith `@traceable` 11 runs*
