# 진흥 · 법률 근거 찾기

지역 주민을 위한 RAG 법률 정보 캡스톤 연구 시스템입니다. **원래 계획의 Elasticsearch + Chroma + LangChain/GPT 구성**을 기본 경로로 복원했습니다. 법률 자문 서비스나 완성된 상용 제품은 아닙니다.

처음 사용하는 분은 **[쉬운 사용자 안내서](docs/USER_GUIDE.md)**에서 기능·동작 방식·화면 사용법·문제 해결을 확인하세요.

## 현재 구현

- FastAPI REST API, SQLite 세션/대화 저장, 24시간 TTL, 삭제 API
- Elasticsearch Nori/BM25 + Chroma 의미 임베딩 + RRF 실제 어댑터 및 버전별 색인
- LangChain GPT 문장 생성·별도 근거 검토·후속 질의 재작성
- 문장별 출처 ID 및 정확한 인용 구절, 검증 실패 시 원문 발췌
- 공식 명세 기반 법령/판례 수집 CLI, 재개·raw checksum·JSONL·첨부 다운로드
- 연구 변형: 질의 적응 가중치 + 양쪽 검색 합의 + 조문 다양성, 5개 비교군 평가 도구
- React 반응형 UI, 출처 팝업, PWA manifest/service worker
- 근거 부족 응답, 질문 길이 제한, 세션당 30회 제한, 일부 개인정보 마스킹

`data/demo.json`은 **명시적으로 demo 모드를 선택했을 때만 사용하는 가상 자료**입니다. 기본 실행에는 승인된 데이터·실제 ES/Chroma·OpenAI 설정이 필요합니다. Docker 통합/승인 API 실호출/유료 GPT 실행/실제 법률 정확도는 아직 검증하지 않았습니다. 오프라인 계약 테스트 통과와 실환경 검증을 혼동하지 마세요.

## 빠른 실행

Python 3.12 이상, Node.js 22 이상. 저장소 루트에서 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-rag.txt
cp .env.example .env
# .env에서 LAW_OC와 OPENAI_API_KEY 설정
# docs/LEGAL_DATA_RUNBOOK.md에 따라 승인된 원문을 수집·export
docker compose up -d --build
python -m tools.index_corpus runtime/corpus/laws.jsonl runtime/corpus/cases.jsonl
cd frontend
npm install
npm run build
cd ..
uvicorn backend.app:create_app --factory --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

http://127.0.0.1:8000 에 접속합니다. API 문서는 `/docs`입니다. 개발 시 백엔드를 실행한 뒤 `cd frontend && npm run dev`로 Vite 개발 서버를 이용할 수 있습니다.

```bash
python -m pytest -q
python scripts/evaluate.py
```

키 없는 UI 시연만 하려면 `requirements.txt` 설치 후 `.env`에서 `RETRIEVAL_BACKEND=demo`, `USE_GPT=0`을 명시하세요. 이 경로는 실제 의미 검색/법적 근거의 대체물이 아닙니다.

## 먼저 읽을 문서

- [공식 API 조사·전량 로컬 수집·실행 절차](docs/LEGAL_DATA_RUNBOOK.md)
- [원계획 대응표·연구 기여·선행연구·실험](docs/RESEARCH_DESIGN.md)
- [외부 서비스·법률 데이터 사용 방법](docs/EXTERNAL_SETUP.md)
- [설계 결정·제약·운영 보안](docs/ARCHITECTURE.md)
- [학기 일정·평가 계획](docs/ROADMAP.md)
- [실행 검증 기록](docs/VERIFICATION.md)

개인정보가 담긴 신청서와 계정 정보는 저장소에 포함하지 않습니다. `.env`, 실제 수집 데이터, 대화 DB는 Git에서 제외합니다. API 키는 브라우저에 전달하지 않습니다. 외부에 공개하기 전에 인증·전역 사용량 제한·법률 검수를 반드시 추가하세요.
