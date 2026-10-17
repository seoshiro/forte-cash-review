"""Prepare one pinned public portable binary; no tunnel or credentials."""
from pathlib import Path
import sys,json,time,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1]


def main():
    import httpx
    cfg=json.loads((ROOT/'config/cloudflared-artifact.json').read_text());directory=ROOT/'.runtime/cloudflared';directory.mkdir(parents=True,exist_ok=True)
    target=directory/'cloudflared.exe';start=time.monotonic();downloaded=0
    def valid(path):return path.is_file() and path.stat().st_size==cfg['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==cfg['sha256']
    if not target.exists():
        partial=directory/'cloudflared.partial'
        with httpx.Client(timeout=20,follow_redirects=True,max_redirects=5,trust_env=False) as client:
            with client.stream('GET',cfg['url']) as response:
                response.raise_for_status()
                with partial.open('xb') as stream:
                    for chunk in response.iter_bytes(1024*1024):
                        if time.monotonic()-start>180:raise TimeoutError('Download budget')
                        downloaded+=len(chunk)
                        if downloaded>cfg['bytes']:raise ValueError('Artifact too large')
                        stream.write(chunk)
        if not valid(partial):raise ValueError('Official SHA256 mismatch')
        partial.replace(target)
    if not valid(target):raise ValueError('Installed portable artifact mismatch')
    output=subprocess.check_output([str(target),'--version'],timeout=10,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if not output.startswith('cloudflared version '+cfg['version']):raise ValueError('Version mismatch')
    report={'status':'PASS','version':cfg['version'],'verified_bytes':cfg['bytes'],'sha256_verified':True,
        'downloaded_bytes_this_attempt':downloaded,'elapsed_sec':time.monotonic()-start,'tunnel_started':False,
        'credentials_created':False,'account_or_billing_changed':False,'os_security_changed':False}
    out=ROOT/'.private/cloudflared-prepare';out.mkdir(exist_ok=True)
    (out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'private_content_emitted':False}));sys.exit(1)
