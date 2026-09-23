import argparse
import json
from dotenv import load_dotenv
from backend.hybrid import build_index

if __name__ == '__main__':
    load_dotenv()
    p=argparse.ArgumentParser(description='Build versioned ES+Chroma indexes, switch pointer only after validation')
    p.add_argument('jsonl',nargs='+')
    p.add_argument('--pointer',default='runtime/active-index.json')
    args=p.parse_args()
    print(json.dumps(build_index(args.jsonl,args.pointer),ensure_ascii=False))
