# 진흥 · 법률 근거 찾기

지역 주민을 위한 RAG 기반 법률 정보 챗봇의 **실행 가능한 캡스톤 MVP**입니다. 법률 자문 서비스나 완성된 상용 제품이 아닙니다.

## 현재 구현

- FastAPI REST API, SQLite 세션/대화 저장, 24시간 TTL, 삭제 API
- BM25 + 문자 bigram lexical cosine + RRF 검색: 키 없이 실행 가능
- 선택형 OpenAI 임베딩 검색 및 GPT 근거 선택: 실제 의미 검색은 이 모드에서만 제공
- 출력 구절마다 문서 ID·원문·시행일·수집일·링크 연결, 검증 실패 시 원문 발췌로 폴백
- React 반응형 UI, 출처 팝업, PWA manifest/service worker
- 근거 부족 응답, 질문 길이 제한, 세션당 30회 제한, 일부 개인정보 마스킹

**기본 데이터 3개는 가상 시연 안내문이며 실제 법령/판례가 아닙니다.** 실제 데이터 승인·수집, 법률 전문가 검수, 유료 API 실행, 외부 배포는 완료하지 않았습니다. 판례 문서 스키마는 지원하지만 판례 원문은 포함하지 않았습니다.

## 빠른 실행

Python 3.12 이상, Node.js 22 이상. 저장소 루트에서 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
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

## 먼저 읽을 문서

- [외부 서비스·법률 데이터 사용 방법](docs/EXTERNAL_SETUP.md)
- [설계 결정·제약·운영 보안](docs/ARCHITECTURE.md)
- [학기 일정·평가 계획](docs/ROADMAP.md)
- [실행 검증 기록](docs/VERIFICATION.md)

개인정보가 담긴 신청서와 계정 정보는 저장소에 포함하지 않습니다. `.env`, 실제 수집 데이터, 대화 DB는 Git에서 제외합니다. API 키는 브라우저에 전달하지 않습니다. 외부에 공개하기 전에 인증·전역 사용량 제한·법률 검수를 반드시 추가하세요.
