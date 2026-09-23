# 현재 구조

이전 v0.1의 기술 축소 결정은 철회했습니다. 기본 경로는 React/PWA → FastAPI 세션 → LangChain 질의 재작성 → Elasticsearch Nori BM25 + Chroma semantic → RRF → GPT 문장별 인용 생성 → exact quote 검사 + 별도 grounding review입니다.

자세한 계획 대응/실험/한계는 [RESEARCH_DESIGN.md](RESEARCH_DESIGN.md), 원문 수집과 인덱싱은 [LEGAL_DATA_RUNBOOK.md](LEGAL_DATA_RUNBOOK.md)를 따르세요. 이전 설계는 Git 이력에 남아 있습니다.

SQLite 세션 capability 토큰, 일부 PII 마스킹, lazy 24시간 TTL은 유지됩니다. 로그인 인증·전역 비용 제한·실시간 법령 개정 동기화·사건일 유효기간 필터·전문가 검수는 미완료입니다. 공개 배포용 보안 구성이 아니며 ES/Chroma 포트는 loopback에만 바인딩합니다. GPT 검토는 법적 정확성을 보증하지 않습니다.
