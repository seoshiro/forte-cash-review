"""Code-only release gate. Never display private data or secret values."""
from pathlib import Path
import subprocess,hashlib,json,re,sys
from release_assets import SAFE_PUBLIC_ASSETS,approved_asset
root=Path(__file__).resolve().parents[1]
files=subprocess.check_output(['git','ls-files','-co','--exclude-standard'],cwd=root,text=True).splitlines()
allowed_ext={'.py','.ps1','.md','.txt','.json','.html','.css','.js','.ini','.csv','.example','.gitignore'}
blocked=[];digests={}
for name in files:
    p=root/name
    if p.is_dir():continue
    data=p.read_bytes()
    if name in SAFE_PUBLIC_ASSETS:
        if not approved_asset(name,data):blocked.append(name)
        digests[name]=hashlib.sha256(data).hexdigest()
        continue
    ok=p.suffix.lower() in allowed_ext or p.name in ['.gitignore','LICENSE','NOTICE','Start-TRAIN-review.cmd']
    if p.suffix.lower()=='.csv' and not re.fullmatch(r'docs/claim-ledger(?:-[0-9]{2})?\.csv',name):ok=False
    if any(part.lower() in {'.private','models','.runtime','.cache','.aws'} or part.lower().startswith('.venv') for part in Path(name).parts):ok=False
    if p.stat().st_size>1024*1024:ok=False
    try:text=p.read_text(encoding='utf-8')
    except (UnicodeError,OSError):ok=False;text=''
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk-proj-|ghp_|hf_)[A-Za-z0-9_-]{16,}',text):ok=False
    if not ok:blocked.append(name)
    digests[name]=hashlib.sha256(data).hexdigest()
out=root/'.private/release';out.mkdir(parents=True,exist_ok=True)
(out/'code-digests.json').write_text(json.dumps(digests,indent=2),encoding='utf-8')
(out/'audit.json').write_text(json.dumps({'code_file_count':len(files),'blocked_count':len(blocked),'blocked_paths':blocked,'scope':'source allowlist + exact-digest reviewed empty UI asset + obvious credential markers; manual code review still required'}),encoding='utf-8')
print(json.dumps({'code_file_count':len(files),'blocked_count':len(blocked),'result':'FAIL' if blocked else 'PASS'}))
sys.exit(bool(blocked))
