"""Gold is manually reviewed JSONL: {id,query,relevant_ids:[chunk IDs]}.
No ground truth or novelty claims are inferred from model output.
"""
import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from backend.hybrid import HybridRetriever


def metrics(ids,gold):
    hit=set(ids)&set(gold)
    return {'recall_at_3':len(hit)/len(set(gold)) if gold else float(not ids),
            'mrr':next((1/(i+1) for i,x in enumerate(ids) if x in gold),0.),
            'abstained':not ids,'false_evidence':bool(ids) and not bool(hit)}


if __name__=='__main__':
    load_dotenv()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gold',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    cases=[json.loads(line) for line in args.gold.read_text().splitlines() if line.strip()]
    if not cases or len({c['id'] for c in cases})!=len(cases):raise ValueError('Empty/duplicate gold IDs')
    retrieval=HybridRetriever()
    rows=[]
    for case in cases:
        for variant in ('bm25','dense','rrf','adaptive','adaptive-diverse'):
            start=time.perf_counter()
            docs=retrieval.search(case['query'],variant)
            rows.append({'id':case['id'],'variant':variant,'seconds':time.perf_counter()-start,
                         'ids':[d['id'] for d in docs],**metrics([d['id'] for d in docs],case['relevant_ids'])})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps({'corpus':retrieval.config,'rows':rows},ensure_ascii=False,indent=2))
