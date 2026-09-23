# 검증 기록 · 계획 복원 리비전

2026-09-23, 로컬 Python 3.14.5 / Node 24.19.0.

- 오프라인 pytest: **36 passed, 1 skipped**.
- Vite production build 성공.
- 법령/판례 공식 필드 정의를 반영한 합성 XML로 목록/본문 매핑, MST+efYd, 조문 단서/오프셋, 판례 메타데이터, 재개, checksum, 오류 응답, API 재시도, 범위 격리 검증. 실서비스에서 받은 fixture가 아님.
- ES/Chroma 요청 계약, 가중 RRF 차이, 양쪽 검색 합의, 색인 건수 불일치 차단, 문장별 인용 문자열 검사. 이 검사는 실제 외부 DB 실행을 대신하지 않음.
- 첨부 URL 호스트 제한 및 여러 번 실행할 때 완료 파일 이후로 진행되는지 검증.
- 기존 세션/삭제/입력 한도/마스킹/정적 프론트 제공 회귀 테스트 유지.
- CLI help 및 Python compile 검사 통과.

## 아직 실행하지 않은 것

- 실제 ES/Nori + Chroma Docker 통합: 이 환경에 Docker가 없음.
- 실제 법률 Open API 수집: 승인 OC 미사용.
- 실제 OpenAI 임베딩·GPT: 유료 키 미사용.
- 실기기 PWA, 법률 전문가 검수, 새 방법의 성능 개선: 미측정.
- 새 optional RAG 의존성 전체 설치/보안 감사 및 원격 CI 성공: 이번 로컬 검증에 포함하지 않음.

Docker 기동 및 requirements-rag 설치 후 다음 명령으로 실제 두 저장소의 색인·조회 왕복을 검사할 수 있습니다. 이 테스트의 고정 합성 벡터는 API 비용 없는 DB 통합 검사만을 위한 것이며 실제 의미 검색 품질 평가가 아닙니다.

```bash
RUN_SERVICE_TESTS=1 python -m pytest tests/test_services.py -q
```

재현 순서: requirements 설치 → frontend npm install/build → pytest. Starlette TestClient/httpx 및 anyio 별칭 deprecation 경고 2건이 있습니다. 현재 실패는 아니며 후속 호환성 정리가 필요합니다. 직접 의존성은 고정했지만 전체 전이 의존성 lockfile은 아직 없습니다.
