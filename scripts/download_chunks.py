"""Bounded concurrent byte ranges for public artifacts with final SHA256 verification."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,httpx,json,time


def fetch(url,path,total,digest,*,workers=4,chunk_bytes=1024*1024,budget_sec=3600,progress=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.stat().st_size==total:
        with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=digest:raise ValueError('Completed artifact SHA256 mismatch')
        return
    if path.exists() and path.stat().st_size>total:raise ValueError('Partial larger than official artifact')
    deadline=time.monotonic()+budget_sec;failures=0
    with httpx.Client(timeout=httpx.Timeout(30,connect=15),follow_redirects=True,trust_env=False,limits=httpx.Limits(max_connections=workers,max_keepalive_connections=workers)) as c:
        def piece(start,end):
            if time.monotonic()>=deadline:raise TimeoutError('Artifact budget exhausted')
            with c.stream('GET',url,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'}) as r:
                r.raise_for_status()
                if r.status_code!=206 or r.headers.get('content-range','')!=f'bytes {start}-{end}/{total}':raise ValueError('Server did not respect exact bounded range')
                data=bytearray()
                for b in r.iter_bytes(32768):
                    data.extend(b)
                    if len(data)>end-start+1:raise ValueError('Response exceeded bounded range')
                    if time.monotonic()>=deadline:raise TimeoutError('Artifact budget exhausted')
                if len(data)!=end-start+1:raise httpx.ReadError('Incomplete artifact range')
                return data
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while not path.exists() or path.stat().st_size<total:
                if time.monotonic()>=deadline:raise TimeoutError('Artifact budget exhausted')
                offset=path.stat().st_size if path.exists() else 0
                starts=range(offset,min(total,offset+workers*chunk_bytes),chunk_bytes)
                futures=[pool.submit(piece,start,min(total-1,start+chunk_bytes-1)) for start in starts]
                try:
                    # Only contiguous verified ranges are appended; <= workers MiB RAM.
                    for future in futures:
                        data=future.result()
                        with path.open('ab') as f:f.write(data)
                        if progress:Path(progress).write_text(json.dumps({'bytes':path.stat().st_size,'total':total,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),encoding='utf-8')
                    failures=0
                except httpx.HTTPError:
                    for future in futures:
                        try:future.result()
                        except (httpx.HTTPError,TimeoutError,ValueError):pass
                    failures=0 if path.exists() and path.stat().st_size>offset else failures+1
                    if failures>3:raise RuntimeError('Repeated public artifact network failure') from None
                    time.sleep(min(2**failures,8))
    with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    if path.stat().st_size!=total or actual!=digest:raise ValueError('Artifact SHA256 verification failed')
