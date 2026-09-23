# 법률 Open API → 로컬 원문 아카이브 → 검색 인덱스

조사일: 2026-09-23. 아래는 **공식 API 문서를 읽고 구현한 절차**입니다. 이용승인/LAW_OC가 없어 실서비스 인증 호출이나 전량 수집을 완료한 것은 아닙니다. XML 계약 테스트에는 명시적으로 만든 합성 fixture만 사용했습니다.

## 1. 정확한 서비스와 인증

이 구현은 국가법령정보 공동활용 **DRF API**를 사용합니다. data.go.kr의 `apis.data.go.kr/1170000/...` 서비스와 혼합하지 않습니다. DRF의 `OC`에는 신청/승인받은 **API 인증값**을 넣습니다. 과거 자료의 ‘이메일 아이디’ 설명만 보고 값을 추정하거나 `OC=test`로 대량 수집하지 마세요. 최신 공식 본문은 ‘신청한 API인증값’으로 안내합니다.

1. https://open.law.go.kr/ 에서 회원가입.
2. OPEN API 신청에서 법령·판례 등 실제 사용할 데이터 범위를 선택해 승인받기.
3. 마이페이지 API인증키관리와 신청 화면의 IP/도메인 조건 확인. IP 등록 요구 범위는 계정/신청 화면에서 확인해야 하며 이 조사에서 모든 계정에 공통인 규칙으로 확정하지 않았습니다.
4. `.env`의 `LAW_OC` 설정. 코드의 `load_dotenv()`가 읽습니다. API 인증값을 Git, 명령 이력, HTTP access log, 수집 리포트에 넣지 않습니다.
5. **전량 수집/반복 동기화의 허용 범위와 트래픽 제한을 운영기관에 확인**합니다. 공식 이용안내는 트래픽 과다 시 제한 가능성을 명시하지만 이 조사에서 공통 숫자 QPS/일 한도는 확인하지 못했습니다. 도구 기본 1초 간격은 자체 보수적 설정이지 공식 허용량이 아닙니다.

## 2. 목록과 본문은 다른 요청이다

```text
목록: GET https://www.law.go.kr/DRF/lawSearch.do
본문: GET https://www.law.go.kr/DRF/lawService.do
공통: OC=<승인값>, target=<eflaw 또는 prec>, type=XML
```

### 시행일 기준 법령

- 목록: `target=eflaw&display=100&page=1&nw=3` (검색어 생략 시 목록 전체를 요청).
- `display`: 기본 20, 최대 100. `page`: 1부터 시작. `totalCnt`로 페이지 수를 계산합니다.
- `nw=1`: 연혁, `2`: 시행예정, `3`: 현행. `1,2,3`으로 함께 요청할 수 있습니다. 기본값 전체에 의존하지 않고 도구가 명시합니다.
- 목록의 `법령일련번호` → 본문의 **MST**; 목록의 `시행일자` → 본문의 **efYd**.
- 예: `target=eflaw&MST=<법령일련번호>&efYd=<YYYYMMDD>&type=XML`.
- **법령ID와 MST는 다릅니다.** `ID=<법령ID>` 조회는 현행을 반환하고 efYd를 무시하므로 버전 보존 수집에는 사용하지 않습니다.
- `JO`를 생략하면 모든 조문. 특정 조문은 6자리 `조번호 4자리+가지번호 2자리` (공식 예: 000200=제2조, 001002=제10조의2).
- 법령명 검색은 `query`; 공포일 범위 `ancYd=YYYYMMDD~YYYYMMDD`, 시행일 범위 `efYd`. 현재 CLI `--date-range`는 **공포일 ancYd**로 매핑합니다. 혼동하지 마세요.

### 판례

- 목록: `target=prec&display=100&page=1&sort=dasc`, `query` 생략 시 승인 범위 내 목록 전체 요청.
- 목록의 `판례일련번호` → 본문의 **ID**. 사건번호와 같은 값이 아닙니다.
- 본문: `target=prec&ID=<판례일련번호>&type=XML`.
- 목록의 기본 검색은 판례명(`search=1`), 본문 검색은 `search=2`; CLI는 기본 판례명 검색을 사용합니다.
- 선고일 범위는 `prncYd=YYYYMMDD~YYYYMMDD`, CLI `--date-range`로 지원합니다.
- 원문에는 사건명, 사건번호, 선고일자, 법원명, 판시사항, 판결요지, 참조조문, 참조판례, 판례내용이 제공됩니다.
- **국세청 판례 본문은 HTML만 가능**하다는 공식 예외가 있습니다. 현재 XML 수집기는 이를 정상 완료로 숨기지 않고 실패/검토 대상으로 남깁니다. 이 범위를 전부 지원하려면 허가 범위 확인 후 HTML 전용 파서 및 테스트를 추가해야 합니다.

## 3. 먼저 작은 범위를 실제로 검증

저장소 루트, Python 3.12 이상 환경:

```bash
pip install -r requirements.txt
cp .env.example .env
# 편집기로 .env의 LAW_OC만 입력; 외부로 공유하지 않기
python -m tools.law_sync sync --target eflaw --query 근로기준법 --out runtime/mirror/labor
python -m tools.law_sync export --out runtime/mirror/labor --output runtime/corpus/labor.jsonl
```

수집 종료코드: 0=해당 범위 목록/본문 완료, 2=페이지/본문 예산상 미완료 또는 실패 항목 남음. API 인증·전송·총건수 변화 등은 예외로 중단됩니다. 같은 명령을 다시 실행하면 완료한 목록 페이지와 본문은 건너뛰고 이어갑니다. `manifest.sqlite`/`status.json`을 보며 진행합니다. 파서 실패를 반복하면 자동 반복 대신 실제 응답/공식 스키마를 점검하세요.

## 4. 승인된 범위를 전량 로컬로 옮기기

```bash
# 모든 법령 상태(연혁/예정/현행): 첫 실행과 후속 재개는 동일 명령
python -m tools.law_sync sync --target eflaw --nw 1,2,3 --out runtime/mirror/all-laws
# 모든 접근 가능한 판례 목록: 별도 manifest 사용
python -m tools.law_sync sync --target prec --out runtime/mirror/all-cases
# 날짜로 나눌 수도 있음. 각 구간은 반드시 별도 out 디렉터리
python -m tools.law_sync sync --target prec --date-range '20200101~20201231' --out runtime/mirror/cases-2020
```

기본 1회 실행은 목록 10페이지, 본문 100개, 전체 요청 200회까지만 허용합니다. 초기 검증 후 승인된 한도에 맞춰 `--max-pages`, `--max-details`, `--max-requests`, `--interval`을 조절하세요. 대규모 mirror를 무한 반복하거나 승인 없이 한도를 크게 올리지 마세요. N개 원문에 필요한 최소 호출 수는 대략 `ceil(N/100)+N`이며 재시도·별표 다운로드는 추가입니다. 용량은 실제 표본의 raw XML/첨부 평균 크기와 embedding 차원으로 측정해야 하므로 임의의 전체 GB 수치를 제시하지 않습니다.

‘전부’의 의미는 **선택한 target·필터·승인 범위가 노출하는 레코드 전부**입니다. 법령+판례를 받아도 191종 전체 API, 모든 법원 비공개 판결, 자치법규·행정규칙·첨부 이미지 전체를 복제한 것이 아닙니다. 그 자료는 별도 target과 어댑터가 필요합니다. 원격 API는 고정된 snapshot을 보장하지 않으므로 수집 도중 totalCnt 변동/중복 페이지/최종 고유 건수 불일치 때 중단합니다. 이후 새 날짜 폴더 또는 `--refresh`로 재수집하세요. 총건수가 같아도 내용 변경은 가능하므로 최종 최신성 검수는 별도입니다.

## 5. 로컬 저장 구조와 오류 복구

```text
runtime/mirror/<scope>/
  manifest.sqlite          범위, 다음 페이지, item ID/메타데이터/상태/해시
  lists/<page>-<sha>.xml    원본 목록 응답
  raw/<sha256>.xml         변경하지 않은 본문 응답, 내용 해시 기준
  status.json              완료 여부, 대기/실패 건수, 이번 호출 수
  manifest-<timestamp>.sqlite  refresh 이전 상태 백업
runtime/corpus/
  laws.jsonl               조문/항호목·부칙 단위 -> 겹침 chunk
  laws.attachments.jsonl   별표 파일 URL 및 미다운로드 상태
```

- raw 원문을 먼저 보존하고 검색용 정규화 텍스트를 별도로 만듭니다. HTML br를 줄바꿈으로 바꾸는 등 정규화는 원본 파일을 수정하지 않습니다.
- 조문은 항/호/목의 조건·단서까지 포함하고, 부칙을 별도 섹션으로 보존합니다. 청크 크기 1,400자, overlap 200자. 원문 해시, section 해시, parent_id, 시작/끝 오프셋을 저장합니다.
- 판례는 섹션별 청크, 사건번호·법원·선고일·참조조문 메타데이터를 보존합니다. 공통 호환 필드 effective_date에도 선고일이 들어가지만 **판례에 법령 시행일이라는 뜻으로 사용하지 않습니다**.
- raw checksum이 달라지면 export 실패. 중간 수집 자료의 export는 기본 거부. 개발 목적으로만 `--allow-partial` 사용하고 완전한 mirror라고 표기하지 마세요.
- `--refresh`는 이전 manifest를 백업하고 목록/본문을 다시 가져옵니다. raw 해시 파일은 유지합니다. 따라서 같은 ID의 정정문도 재수집할 수 있고 제거된 목록 항목을 현재 corpus에서 제외할 수 있습니다. 실시간 증분 CDC나 공식 삭제 API 연동은 아직 없습니다.
- 인증값은 API 요청에만 사용하며 scope/manifest에 저장하지 않습니다. 타임아웃/429/5xx는 최대 4회 시도, backoff/숫자 Retry-After 적용. HTTP 3xx를 임의 추종하거나 HTTPS에서 HTTP로 다운그레이드하지 않습니다. XML 오류 응답은 totalCnt/본문 필수 필드 검증에서 차단합니다.

```bash
python -m tools.law_sync export --out runtime/mirror/all-laws --output runtime/corpus/laws.jsonl
python -m tools.law_sync export --out runtime/mirror/all-cases --output runtime/corpus/cases.jsonl
# 정기 재수집: 승인 한도 내에서 같은 scope를 명시
python -m tools.law_sync sync --target eflaw --nw 1,2,3 --out runtime/mirror/all-laws --refresh
```

## 6. 별표 HWP/PDF와 한계

공식 매뉴얼에 따라 `별표서식파일링크`/`별표서식PDF파일링크` 값에 `https://www.law.go.kr`를 붙입니다. export가 attachment manifest를 생성합니다.

```bash
python -m tools.download_attachments runtime/corpus/laws.attachments.jsonl --out runtime/attachments --limit 100
```

공식 호스트의 `/LSW/flDownload.do`만 허용, 파일당 50MiB 상한, 이어받기는 완료 파일 건너뛰기 방식입니다. 이 도구는 **바이너리 저장만** 합니다. PDF/HWP 본문 추출·OCR·별표 이미지·그림 링크 전체 수집/색인은 미구현입니다. 실패 파일을 재실행해 받되 콘텐츠 형식과 체크섬을 확인하세요. 별표 기준치가 질문의 핵심이라면 본문만으로 완결된 답이라고 평가하지 않아야 합니다.

## 7. 검색 DB로 옮기는 실제 명령

```bash
pip install -r requirements-rag.txt
docker compose up -d --build
# .env: OPENAI_API_KEY 설정 (문서/질문 embedding은 유료)
python -m tools.index_corpus runtime/corpus/laws.jsonl runtime/corpus/cases.jsonl
# 양쪽 저장소 건수 검증 후에만 runtime/active-index.json 원자적 교체
uvicorn backend.app:create_app --factory --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

ES Nori BM25와 Chroma cosine을 **같은 chunk ID·동일 corpus fingerprint**로 색인합니다. 한쪽 실패 시 active pointer는 바뀌지 않습니다. 모델/입력 파일이 달라지면 새 인덱스를 만들며 이전 것을 삭제하지 않습니다. 앱 재시작으로 새 pointer를 읽습니다. 이전 pointer 백업을 복구하면 rollback할 수 있습니다. 오래된 인덱스/볼륨 삭제는 검증 후 수동 수행합니다.

연혁·시행예정까지 모두 아카이브하는 것과 실제 상담 검색에 모두 사용하는 것은 별개입니다. 현재 retrieval은 사건일 기반 유효기간 필터를 구현하지 않았습니다. 운영 시 우선 `nw=3` 현행 corpus로 제한하고, 과거 사건 적용·부분 시행일·폐지/경과조치는 검수해야 합니다. 역사적 법률 판단이 완료됐다고 표시하지 않습니다.

## 공식 근거

- 이용승인/제한/출처 표시: https://open.law.go.kr/LSO/information/guide.do
- API 전체 목록: https://open.law.go.kr/LSO/openApi/guideList.do
- 시행일 법령 목록/nw/display/page: https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdListGuide
- 법령 본문/MST/ID/efYd/JO: https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdInfoGuide
- 판례 목록: https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precListGuide
- 판례 본문/HTML-only 예외: https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precInfoGuide
- 목록→본문→별표 파일 절차: https://open.law.go.kr/LSO/openApi/openApiManual.do
