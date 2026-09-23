"""Validate approved JSON documents before installing a corpus. No scraping."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import Document

parser = argparse.ArgumentParser()
parser.add_argument('input', type=Path)
parser.add_argument('--output', type=Path, default=Path('runtime/legal.json'))
args = parser.parse_args()
items = json.loads(args.input.read_text(encoding='utf-8'))
docs = [Document.model_validate(item).model_dump() for item in items]
if not docs or len(docs) > 5000 or len({d['id'] for d in docs}) != len(docs):
    raise SystemExit('문서 수는 1~5000개, ID는 고유해야 합니다.')
if any(d['kind'] == 'demo' for d in docs):
    raise SystemExit('실제 데이터 가져오기에는 demo 자료를 넣지 마세요.')
args.output.parent.mkdir(parents=True, exist_ok=True)
tmp = args.output.with_suffix('.tmp')
tmp.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding='utf-8')
tmp.replace(args.output)
print(f'Validated {len(docs)} documents -> {args.output}')
