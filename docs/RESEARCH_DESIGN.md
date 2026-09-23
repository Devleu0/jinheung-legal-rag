# 계획 복원과 검증 가능한 연구 기여

## 의사결정 원칙 교정

‘대학생 캡스톤’은 개발 품질을 낮추거나 신청서 핵심 기술을 빼도 된다는 뜻이 아닙니다. 기간/예산/팀 역할/재현 가능한 발표를 의사결정 기준으로 삼고, 구현 수준과 연구 검증은 유지합니다. 이전 lexical-only 기본 MVP는 **과거 프로토타입/테스트용 demo**로만 남깁니다.

## 신청서 대비 현재 상태

| 계획 | 이번 변경 | 남은 검증/한계 |
|---|---|---|
| Python/FastAPI | 유지, production retrieval 연결 | 공개 인증·운영 보안 |
| Elasticsearch+Chroma | ES Nori BM25 + Chroma 실제 임베딩 검색 + RRF, Docker 구성 | 이 환경에 Docker가 없어 실제 서비스 통합은 미실행 |
| LangChain/GPT | OpenAIEmbeddings, ChatOpenAI structured output, 후속질문 rewrite | 유료 호출 미실행, mock 계약 테스트 |
| 문장별 출처 | 문장/source_id/exact quote + 별도 grounding review, UI 인용 구절 | LLM 판단은 오류 가능, 법률 전문가 검수 필요 |
| 멀티턴 | 최근 2턴 질문/근거를 바탕으로 독립 질의 생성, 실패 시 규칙 기반 fallback | 대명사·주제전환 실데이터 평가 |
| 법령/판례 로컬화 | 공식 명세 기반 재개 가능한 수집기/원문 archive/JSONL/색인 | 승인된 OC 실호출, HTML-only 판례·OCR 별도 |
| React/PWA | 유지, 근거 팝업 개선 | 실기기 설치/접근성 검증 |

## 독자 실험: 질의 유형 적응 + 양쪽 검색 합의 + 조문 다양성

하이브리드 검색 자체는 새 방법이 아닙니다. 이 프로젝트가 시도할 비교 대상은 **QAC-D: Query-Adaptive Consensus with parent Diversity**라는 실험용 조합입니다. 전 세계 최초라는 뜻이 아니라 프로젝트 내 구현/평가할 가설입니다. 명칭은 본 프로젝트의 실험 식별자입니다.

구현 `backend/hybrid.py:fuse` 및 `HybridRetriever.search`:

1. 법 조항/사건번호 패턴 질의는 BM25:dense=2:1, 일반 생활언어는 1:2로 가중 RRF.
2. 실험 변형에서는 두 검색기 모두 찾은 chunk만 통과시키는 consensus gate.
3. 동일 parent 조문/판례 섹션의 겹침 chunk가 상위 결과를 독점하지 않도록 parent별 최대 1개.
4. 검색 근거가 없으면 빈 결과, 특정 엔진 장애는 503. 임의의 lexical demo로 바꾸지 않음.

가설: 정확한 조문 질의에서 lexical 비중이 유리하고, 생활언어는 dense 비중이 유리하다. 합의 gate는 틀린 근거를 줄일 수 있지만 recall을 떨어뜨릴 수 있다. 다양성은 근거 범위를 넓히지만 같은 조문의 중요한 예외가 다른 chunk에만 있으면 손실될 수 있다. 즉 **개선은 아직 입증하지 않았다**. 기존 RRF를 기본값으로 유지하고 `FUSION_VARIANT=adaptive-diverse`는 실험으로 선택한다.

비교군: `bm25`, `dense`, `rrf`, `adaptive`, `adaptive-diverse` (합의+다양성). 합의와 다양성을 완전히 분리한 ablation은 후속 과제로 남으며 현 단계에서 각 효과를 독립적으로 설명하지 않는다.

## 실험 데이터와 명령

검수한 실제 corpus에 대해 정확한 조항/사건번호 질의 30개, 생활언어 30개, 조건/예외 질의 20개, 무관 질문 20개, 멀티턴 20세트를 만든다. 근거 gold는 사람의 독립 검토 2인과 불일치 조정으로 작성한다. tuning/test 분리, 동일 문서/질문 누출 검사. 개인정보는 넣지 않는다.

```json
{"id":"heldout-001","query":"검수한 실제 질문","relevant_ids":["실제 JSONL의 chunk ID"]}
```

```bash
python -m tools.evaluate_hybrid --gold runtime/evaluation/heldout.jsonl --out runtime/evaluation/results.json
```

현재 평가 도구는 검색 지표 Recall@3/MRR/빈 응답/오근거와 지연 시간을 기록한다. 거절 질문의 recall은 빈 응답을 성공으로 계산하므로 positive/negative 집단을 분리 집계해야 한다. multi-turn 문장 정확도·전문가 법률 판단·bootstrap CI·실제 비용은 아직 자동 측정하지 않는다. 모든 변형에서 같은 후보 획득 코드를 사용하므로 기록된 지연은 BM25-only 시스템의 공정한 비용 비교가 아니다. 개선 주장에는 질문별 paired 비교, 95% bootstrap CI, 최악 사례 분석을 추가한다. 문서/질문은 임베딩·GPT 제공자에 전송되므로 예산과 동의 확인 후 실행한다.

## 선행연구 조사: ‘미시도’ 주장의 한계

- Section-Weighted Hybrid Approach for Legal Case Retrieval: https://arxiv.org/html/2606.03138 — BM25/dense/RRF 및 섹션 가중 접근 선행사례. 섹션 가중 자체를 최초라고 할 수 없다.
- Hybrid GraphRAG for Cross-Lingual Legal Citation Retrieval: https://www.ijecs.in/index.php/ijecs/article/view/5461 — 다중 신호 가중 RRF/그래프 조합 선행사례.
- LegalBench-RAG: https://pith.science/citations/98f89122-db07-49b0-8852-b695a89511fb — 문서 ID뿐 아니라 정밀 근거 구간 평가의 필요성.

이는 초기 선행조사이며 체계적인 신규성 검색을 대체하지 않는다. 캡스톤의 독자 기여는 한국어 생활법률·조문 단서 보존·합의 거절의 실증적 비교와 데이터/실험 재현성으로 제시하고, 학술적 신규성 인정 기준은 지도교수와 확인해야 한다.

## 기술 공식 문서

- Nori 설치: https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori
- Chroma 명시적 embedding 제공: https://docs.trychroma.com/docs/collections/manage-collections
- Chroma cosine 구성: https://docs.trychroma.com/docs/collections/configure
- LangChain ChatOpenAI: https://docs.langchain.com/oss/python/integrations/chat/openai
