# 검증 기록

2026-09-23 로컬 Python 3.14.5 / Node 24.19.0에서 초기 구현을 검사했습니다.

- pytest: 22 passed (의존성 갱신 및 저장소에서 재다운로드 후 재검증)
- 데모 검색 3건: Recall@3=1.0, MRR=1.0. 실제 법률 정확도 수치 아님.
- React Vite production build 성공 (Vite 6.4.3)
- npm audit: Vite 6.4.1 취약점 발견 후 6.4.3으로 수정, 재검사 0건
- Python 감사: 구버전 pytest/python-dotenv/Starlette 취약점 발견 후 의존성 갱신, pip-audit -r requirements.txt 재검사에서 알려진 취약점 없음.
- 실제 테스트 환경: FastAPI 0.141.1, Starlette 1.6.0, Pydantic 2.13.5, Uvicorn 0.53.0, pytest 9.1.1.
- 검증 범위: 출처 일치, 잘못된 GPT 인용 폴백, 근거 부족, 세션 격리/삭제/만료/재시작, 입력 한도, PII 마스킹, URL 제한, 임베딩 캐시, 외부 API 실패, JSON 가져오기·데모 거부, 빌드된 프론트 정적 제공.
- 경고 2건: Starlette TestClient의 httpx 및 anyio 별칭 사용 중단 예정 경고. 현재 테스트 실패는 아니며 후속 업그레이드 필요.

OpenAI 호출은 mock 테스트만 수행했습니다. 실제 유료 API·법률 Open API·브라우저 실기기 PWA·법률 전문가 검수는 미실행입니다. CI를 추가했지만 원격 실행 성공은 별도 확인이 필요합니다. 재현 시 requirements 설치 → 프론트 npm install/build → pytest 순서로 실행하세요. 테스트의 프론트 제공 검사는 dist 빌드가 필요합니다. 직접 의존성 버전은 고정했지만 전이 의존성 lockfile은 아직 없으므로 설치 시점별 차이가 있을 수 있습니다. 보안 감사 0건은 무취약점 보장이 아닙니다.
