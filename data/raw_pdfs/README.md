# raw_pdfs

회사별 폴더 + 한글 티커명 파일 규칙: `{한글티커명}/{한글티커명}_00x.pdf`

```
data/raw_pdfs/
  SK/
    SK_001.pdf
    SK_002.pdf
    SK_003.pdf
  두산에너빌리티/
    두산에너빌리티_001.pdf
    ...
  삼성전기/
  셀트리온/
  신세계/
  한국전력/
```

| 한글 티커 (폴더명) | 파일 수 |
|-------------------|--------|
| SK | 3 |
| 두산에너빌리티 | 3 |
| 삼성전기 | 3 |
| 셀트리온 | 3 |
| 신세계 | 3 |
| 한국전력 | 2 |

Ingest 예시 (`--ticker`는 한글 티커명 또는 관례 코드 사용):

```powershell
.\.venv\Scripts\python.exe -m equity_rag.cli ingest `
  --pdf data/raw_pdfs/삼성전기/삼성전기_001.pdf `
  --ticker 삼성전기 `
  --company-name "삼성전기" `
  --source "메리츠증권" `
  --report-date 2026-05-20
```

재정리 스크립트: `scripts/organize_pdfs.py`
