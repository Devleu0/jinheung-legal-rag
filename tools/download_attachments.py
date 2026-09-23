"""Optional binary archive only; OCR/HWP/PDF indexing is NOT performed."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse
import httpx


def download(manifest, out, limit=100, interval=1.0):
    out.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=60,follow_redirects=False) as client:
        for i,line in enumerate(manifest.read_text().splitlines()):
            if i>=limit:break
            item=json.loads(line);url=item['url'];p=urlparse(url)
            if p.scheme!='https' or p.hostname not in {'www.law.go.kr','law.go.kr'} or p.username or p.password or p.path!='/LSW/flDownload.do':
                raise ValueError('Unsafe attachment URL')
            name=hashlib.sha256(url.encode()).hexdigest()
            if (out/(name+'.json')).exists():continue
            time.sleep(interval)
            temp=out/(name+'.part')
            try:
                with client.stream('GET',url) as response:
                    if response.status_code!=200:raise ValueError('Attachment HTTP failure; redirects are not followed')
                    if 'html' in response.headers.get('content-type','').lower():raise ValueError('HTML is not a binary attachment')
                    size=0;h=hashlib.sha256()
                    with temp.open('wb') as stream:
                        for data in response.iter_bytes():
                            size+=len(data)
                            if size>50*1024*1024:raise ValueError('Attachment exceeds 50 MiB limit')
                            stream.write(data);h.update(data)
                if not size:raise ValueError('Empty attachment')
                temp.replace(out/(name+'.bin'))
                (out/(name+'.json')).write_text(json.dumps(dict(item,bytes=size,sha256=h.hexdigest(),status='downloaded'),ensure_ascii=False))
            finally:
                temp.unlink(missing_ok=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--limit',type=int,default=100)
    args=p.parse_args()
    if args.limit<1:p.error('limit must be positive')
    download(args.manifest,args.out,args.limit)
