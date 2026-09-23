"""Approved law.go.kr DRF XML -> resumable raw archive -> normalized JSONL.
Never supplies a public/sample OC automatically. See docs/LEGAL_DATA_RUNBOOK.md.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from defusedxml import ElementTree as ET

BASE = 'https://www.law.go.kr'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean(text):
    text = re.sub(r'<br\s*/?>', '\n', text or '', flags=re.I)
    return html.unescape(re.sub(r'<[^>]*>', '', text)).strip()


def value(node, key):
    found = node.find('.//' + key)
    return clean(''.join(found.itertext())) if found is not None else ''


def iso(text):
    digits = re.sub(r'\D', '', text)
    if len(digits) != 8:
        raise ValueError('Missing or unsupported date')
    return date.fromisoformat(f'{digits[:4]}-{digits[4:6]}-{digits[6:]}').isoformat()


def parse_list(raw, target):
    root = ET.fromstring(raw)
    total = value(root, 'totalCnt')
    if not total.isdigit():
        raise ValueError('Expected XML totalCnt; authentication/error/HTML response rejected')
    tag, key = ('law', '법령일련번호') if target == 'eflaw' else ('prec', '판례일련번호')
    records = []
    for node in root.findall('.//' + tag):
        item = {c.tag: clean(''.join(c.itertext())) for c in node}
        ident = item.get(key, '')
        if not ident.isdigit():
            raise ValueError('Invalid item identifier')
        if target == 'eflaw':
            iso(item.get('시행일자', ''))
        records.append(item)
    if int(total) > 0 and not records:
        raise ValueError('Nonzero total without items; do not silently mark complete')
    return int(total), records


def identity(item, target):
    if target == 'eflaw':
        return item['법령일련번호'] + '-' + re.sub(r'\D', '', item['시행일자'])
    return item['판례일련번호']


def detail_params(item, target):
    if target == 'eflaw':
        return {'MST': item['법령일련번호'], 'efYd': re.sub(r'\D', '', item['시행일자'])}
    return {'ID': item['판례일련번호']}


def sections(raw, item, target):
    root = ET.fromstring(raw)
    if target == 'eflaw':
        title = value(root, '법령명_한글')
        if not title:
            raise ValueError('Law body missing title (API error or changed schema)')
        title_date = iso(item['시행일자'])
        common = {'title': title, 'kind': 'law', 'effective_date': title_date,
                  'law_id': value(root, '법령ID'), 'version_id': identity(item, target),
                  'temporal_status': item.get('현행연혁코드', 'unknown'),
                  'url': BASE + '/LSW/lsInfoP.do?lsiSeq=' + item['법령일련번호'] + '&efYd=' + re.sub(r'\D', '', item['시행일자'])}
        for index, unit in enumerate(root.findall('.//조문단위')):
            if value(unit, '조문여부') not in {'', '조문'}:
                continue
            locator = '제' + value(unit, '조문번호') + '조'
            branch = value(unit, '조문가지번호')
            if branch and branch != '0':
                locator += '의' + branch
            locator += ' ' + value(unit, '조문제목')
            # Include nested paragraph/item provisos, not only the article heading.
            parts = [clean(''.join(n.itertext())) for n in unit.iter() if n.tag in {'조문내용', '항내용', '호내용', '목내용'}]
            text = '\n'.join(p for p in parts if p)
            if text:
                article_date = value(unit, '조문시행일자')
                yield dict(common, section_id=f'article-{index}', locator=locator.strip(), text=text,
                           effective_date=iso(article_date) if article_date else title_date)
        for index, unit in enumerate(root.findall('.//부칙단위')):
            text = value(unit, '부칙내용')
            if text:
                yield dict(common, section_id=f'addendum-{index}', locator=f'부칙 {index+1}', text=text)
    else:
        title, body = value(root, '사건명'), value(root, '판례내용')
        if not title or not body:
            raise ValueError('Case body missing (HTML-only source or API error); requires review')
        common = {'title': title, 'kind': 'case', 'effective_date': iso(value(root, '선고일자')),
                  'decision_date': iso(value(root, '선고일자')), 'version_id': identity(item, target),
                  'case_number': value(root, '사건번호'), 'court': value(root, '법원명'),
                  'reference_text': value(root, '참조조문'),
                  'url': BASE + '/LSW/precInfoP.do?precSeq=' + item['판례일련번호']}
        for key in ('판시사항', '판결요지', '판례내용', '참조조문', '참조판례'):
            text = value(root, key)
            if text:
                yield dict(common, section_id=key, locator=f"{common['court']} {common['case_number']} / {key}", text=text)


def chunks(raw, item, target, retrieved_at, size=1400, overlap=200):
    if not 0 <= overlap < size:
        raise ValueError('Invalid chunk window')
    raw_hash = digest(raw)
    count = 0
    for section in sections(raw, item, target):
        text = section.pop('text')
        parent = f"{target}:{identity(item,target)}:{section.pop('section_id')}"
        for start in range(0, len(text), size-overlap):
            end = min(len(text), start+size)
            count += 1
            yield dict(section, id=f'{parent}:{start}', parent_id=parent, text=text[start:end],
                       start_char=start, end_char=end, raw_sha256=raw_hash,
                       retrieved_at=retrieved_at, section_sha256=digest(text.encode()), source='법제처 국가법령정보센터')
            if end == len(text):
                break
    if not count:
        raise ValueError('No indexable sections')


def attachment_urls(raw):
    root = ET.fromstring(raw)
    links = set()
    for node in root.iter():
        if node.tag in {'별표서식파일링크', '별표서식PDF파일링크'} and node.text:
            url = urljoin(BASE, html.unescape(node.text.strip()))
            parsed = urlparse(url)
            if parsed.hostname in {'www.law.go.kr', 'law.go.kr'} and parsed.path == '/LSW/flDownload.do':
                links.add(url.replace('http://', 'https://', 1))
    return sorted(links)


class Api:
    def __init__(self, oc, interval=1.0, max_requests=1000, transport=None):
        if not oc:
            raise ValueError('Set approved LAW_OC; never use OC=test for a mirror')
        self.oc, self.interval, self.limit, self.used = oc, interval, max_requests, 0
        self.client = httpx.Client(timeout=60, follow_redirects=False, transport=transport)

    def get(self, path, params):
        for attempt in range(4):
            if self.used >= self.limit:
                raise RuntimeError('Request budget reached; rerun to resume')
            self.used += 1
            time.sleep(self.interval)
            try:
                response = self.client.get(BASE + '/DRF/' + path, params=dict(params, OC=self.oc, type='XML'))
            except httpx.TransportError:
                if attempt == 3:
                    raise RuntimeError('Transport failed (URL/OC omitted)') from None
                time.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    raise RuntimeError('Transient API failure; resume later')
                delay = response.headers.get('Retry-After', '')
                time.sleep(min(120, float(delay)) if delay.isdigit() else 2**attempt)
                continue
            if response.status_code != 200:
                raise RuntimeError(f'API HTTP {response.status_code}; check approval/IP without logging OC')
            return response.content
        raise RuntimeError('Retry exhausted')


def connect(folder, scope):
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder/'manifest.sqlite')
    db.executescript('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, metadata TEXT, raw_path TEXT, sha TEXT, collected TEXT, error TEXT);')
    fingerprint = json.dumps(scope, sort_keys=True, ensure_ascii=False)
    previous = db.execute("SELECT value FROM state WHERE key='scope'").fetchone()
    if previous and previous[0] != fingerprint:
        raise ValueError('Different scope: choose a new --out folder')
    db.execute("INSERT OR IGNORE INTO state VALUES('scope',?)", (fingerprint,))
    db.commit()
    return db


def sync(args, api):
    scope = {'target': args.target, 'query': args.query, 'nw': args.nw, 'date_range': args.date_range}
    folder = args.out
    db = connect(folder, scope)
    try:
        if args.refresh:
            # Retain archived blobs but re-enumerate/re-fetch this scope; never overwrite a hash blob.
            archive = sqlite3.connect(folder/f'manifest-{time.time_ns()}.sqlite')
            db.backup(archive)
            archive.close()
            db.execute("DELETE FROM state WHERE key IN ('page','complete','total','last_ids')")
            db.execute('DELETE FROM items')
            db.commit()
        page_row = db.execute("SELECT value FROM state WHERE key='page'").fetchone()
        page = int(page_row[0]) if page_row else 1
        complete = db.execute("SELECT 1 FROM state WHERE key='complete'").fetchone()
        for _ in range(args.max_pages):
            if complete:
                break
            params = {'target': args.target, 'display': 100, 'page': page, 'sort': 'dasc'}
            if args.query:
                params['query'] = args.query
            if args.target == 'eflaw':
                params['nw'] = args.nw
            if args.date_range:
                params['ancYd' if args.target == 'eflaw' else 'prncYd'] = args.date_range
            raw = api.get('lawSearch.do', params)
            total, rows = parse_list(raw, args.target)
            prior = db.execute("SELECT value FROM state WHERE key='total'").fetchone()
            if prior and int(prior[0]) != total:
                raise RuntimeError('Remote total changed during enumeration; use a new dated snapshot or --refresh')
            ids = [identity(item, args.target) for item in rows]
            previous_ids = db.execute("SELECT value FROM state WHERE key='last_ids'").fetchone()
            if page > 1 and previous_ids and json.loads(previous_ids[0]) == ids:
                raise RuntimeError('Repeated page detected')
            (folder/'lists').mkdir(exist_ok=True)
            stamp = digest(raw)
            (folder/'lists'/f'{page}-{stamp}.xml').write_bytes(raw)
            for item, ident in zip(rows, ids):
                db.execute('INSERT OR IGNORE INTO items(id,metadata) VALUES(?,?)', (ident, json.dumps(item, ensure_ascii=False)))
            done = page*100 >= total
            unique_count = db.execute('SELECT count(*) FROM items').fetchone()[0]
            if done and unique_count != total:
                db.rollback()
                raise RuntimeError('Unique count differs from total; remote ordering changed or duplicate rows')
            db.execute("INSERT OR REPLACE INTO state VALUES('total',?)", (str(total),))
            db.execute("INSERT OR REPLACE INTO state VALUES('last_ids',?)", (json.dumps(ids),))
            db.execute("INSERT OR REPLACE INTO state VALUES('page',?)", (str(page+1),))
            if done:
                db.execute("INSERT OR REPLACE INTO state VALUES('complete','1')")
            db.commit()
            page += 1
            complete = done
        (folder/'raw').mkdir(exist_ok=True)
        pending = db.execute('SELECT id,metadata FROM items WHERE raw_path IS NULL ORDER BY id').fetchall()
        failures = 0
        for ident, encoded in pending[:args.max_details]:
            item = json.loads(encoded)
            try:
                raw = api.get('lawService.do', dict(target=args.target, **detail_params(item, args.target)))
                # Validate body before considering this item complete.
                for _ in chunks(raw, item, args.target, date.today().isoformat()):
                    pass
                sha = digest(raw)
                relative = 'raw/' + sha + '.xml'
                (folder/relative).write_bytes(raw)
                db.execute('UPDATE items SET raw_path=?,sha=?,collected=?,error=NULL WHERE id=?', (relative, sha, date.today().isoformat(), ident))
            except (ValueError, ET.ParseError, StopIteration) as exc:
                failures += 1
                db.execute('UPDATE items SET error=? WHERE id=?', (type(exc).__name__ + ': schema/HTML-only body; review required', ident))
            db.commit()
        remaining = db.execute('SELECT count(*) FROM items WHERE raw_path IS NULL').fetchone()[0]
        report = {'enumeration_complete': bool(complete), 'listed': db.execute('SELECT count(*) FROM items').fetchone()[0],
                  'pending_or_failed': remaining, 'failed_this_run': failures, 'requests_this_run': api.used}
        (folder/'status.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        return 0 if complete and remaining == 0 else 2
    finally:
        db.close()


def export(folder, output, allow_partial=False):
    db = sqlite3.connect(folder/'manifest.sqlite')
    state = dict(db.execute('SELECT key,value FROM state'))
    scope = json.loads(state['scope'])
    remaining = db.execute('SELECT count(*) FROM items WHERE raw_path IS NULL').fetchone()[0]
    if (state.get('complete') != '1' or remaining) and not allow_partial:
        raise ValueError('Incomplete mirror; resume sync or explicitly --allow-partial for development')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    assets = output.with_suffix('.attachments.jsonl')
    count = 0
    with temporary.open('w', encoding='utf-8') as stream, assets.open('w', encoding='utf-8') as attachments:
        for ident, metadata, path, sha, collected in db.execute('SELECT id,metadata,raw_path,sha,collected FROM items WHERE raw_path IS NOT NULL ORDER BY id'):
            raw = (folder/path).read_bytes()
            if digest(raw) != sha:
                raise ValueError('Raw archive checksum mismatch')
            for chunk in chunks(raw, json.loads(metadata), scope['target'], collected):
                stream.write(json.dumps(chunk, ensure_ascii=False)+'\n')
                count += 1
            for url in attachment_urls(raw):
                attachments.write(json.dumps({'parent':ident,'url':url,'status':'not_downloaded'},ensure_ascii=False)+'\n')
    temporary.replace(output)
    db.close()
    print(json.dumps({'chunks':count,'output':str(output),'attachments_manifest':str(assets)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    collect = sub.add_parser('sync')
    collect.add_argument('--target', choices=['eflaw','prec'], required=True)
    collect.add_argument('--out', type=Path, required=True)
    collect.add_argument('--query', default='')
    collect.add_argument('--nw', choices=['1','2','3','1,2,3'], default='3')
    collect.add_argument('--date-range', default='')
    collect.add_argument('--max-pages', type=int, default=10)
    collect.add_argument('--max-details', type=int, default=100)
    collect.add_argument('--max-requests', type=int, default=200)
    collect.add_argument('--interval', type=float, default=1.0)
    collect.add_argument('--refresh', action='store_true')
    ex = sub.add_parser('export')
    ex.add_argument('--out', type=Path, required=True)
    ex.add_argument('--output', type=Path, required=True)
    ex.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    if args.command == 'export':
        export(args.out, args.output, args.allow_partial)
        return 0
    if min(args.max_pages,args.max_details,args.max_requests) < 1 or args.interval < 0.1:
        parser.error('Positive limits and interval >= 0.1 required')
    api = Api(os.environ.get('LAW_OC',''), args.interval, args.max_requests)
    try:
        return sync(args, api)
    finally:
        api.client.close()


if __name__ == '__main__':
    raise SystemExit(main())
