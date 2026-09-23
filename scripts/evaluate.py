"""Tiny demo retrieval check; not a legal accuracy benchmark."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import Engine
root=Path(__file__).resolve().parents[1]
cases=[('근로계약 임금','demo-work'),('층간소음 분쟁','demo-noise'),('임대차 보증금','demo-rent')]
with tempfile.TemporaryDirectory(dir=root) as tmp:
    engine=Engine(json.loads((root/'data/demo.json').read_text()),Path(tmp)/'eval.db')
    hits=0
    reciprocal=0
    for query,expected in cases:
        ids=[d['id'] for d in engine.search(query)]
        if expected in ids:
            hits+=1
            reciprocal+=1/(ids.index(expected)+1)
    print(json.dumps({'dataset':'synthetic-demo-only','queries':len(cases),'recall_at_3':hits/len(cases),'mrr':reciprocal/len(cases)}))
    assert hits==len(cases)
