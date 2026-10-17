"""Read-only code-history publication check. Never emit blob contents or secrets."""
from pathlib import Path
import subprocess,json,re,sys
from release_assets import SAFE_PUBLIC_ASSETS,approved_asset
ROOT=Path(__file__).resolve().parents[1]

def main():
    revisions=subprocess.check_output(['git','rev-list','--all'],cwd=ROOT,text=True).splitlines()
    commits=len(revisions);objects={};paths=set()
    for revision in revisions:
        for entry in subprocess.check_output(['git','ls-tree','-rz',revision],cwd=ROOT).split(b'\0'):
            if not entry:continue
            metadata,name=entry.split(b'\t',1);_mode,kind,oid=metadata.decode('ascii').split()
            if kind!='blob':continue
            name=name.decode('utf-8');paths.add(name);objects.setdefault(oid,set()).add(name)
    forbidden_ext={'.mov','.mp4','.avi','.mkv','.wav','.mp3','.m4a','.xlsx','.xls','.png','.jpg','.jpeg','.webp','.gif','.safetensors','.gguf','.pt','.pth','.onnx','.zip','.dll','.exe','.url'}
    markers=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk-proj-|ghp_|hf_)[A-Za-z0-9_-]{16,}')
    violations=[];eligible=[];total_bytes=0
    payload=('\n'.join(objects)+'\n').encode('ascii')
    info=subprocess.run(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],cwd=ROOT,input=payload,capture_output=True,check=True).stdout
    for line in info.decode('ascii').splitlines():
        oid,kind,size=line.split();size=int(size);reason=[]
        for name in objects[oid]:
            path=Path(name);parts=[p.lower() for p in path.parts]
            if path.suffix.lower() in forbidden_ext and name not in SAFE_PUBLIC_ASSETS:reason.append('forbidden_artifact_type')
            if path.suffix.lower()=='.csv' and not re.fullmatch(r'docs/claim-ledger(?:-[0-9]{2})?\.csv',name):reason.append('non_code_csv')
            if any(p in {'.private','models','.runtime','.cache','.aws'} or p.startswith('.venv') for p in parts):reason.append('private_artifact_path')
        if size>1024*1024:reason.append('oversized_blob')
        if total_bytes+size>64*1024*1024:reason.append('bounded_audit_limit')
        if reason:violations.append({'paths':sorted(objects[oid]),'reason':sorted(set(reason))});continue
        eligible.append(oid);total_bytes+=size
    if eligible:
        content=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=('\n'.join(eligible)+'\n').encode('ascii'),capture_output=True,check=True).stdout
        position=0
        for expected in eligible:
            end=content.index(b'\n',position);oid,kind,size=content[position:end].decode('ascii').split();size=int(size)
            if oid!=expected or kind!='blob':raise RuntimeError('Unexpected Git batch framing')
            blob=content[end+1:end+1+size];position=end+size+2;reason=[]
            asset_paths=[name for name in objects[oid] if name in SAFE_PUBLIC_ASSETS]
            if asset_paths:
                if all(approved_asset(name,blob) for name in asset_paths) and len(asset_paths)==len(objects[oid]):continue
                violations.append({'paths':sorted(objects[oid]),'reason':['unapproved_public_asset']});continue
            if b'\x00' in blob:reason.append('binary_blob')
            if markers.search(blob):reason.append('credential_marker')
            if reason:violations.append({'paths':sorted(objects[oid]),'reason':reason})
    out=ROOT/'.private/release';out.mkdir(exist_ok=True)
    record={'scope':'All reachable local Git history before any remote publication; known media/private paths, binary blobs and obvious secret markers, with one exact-digest reviewed empty UI asset exception. Not a general proof of absence of arbitrary encoded secrets.',
            'commits_checked':commits,'unique_paths_checked':len(paths),'unique_blobs_checked':len(objects),'text_bytes_checked':total_bytes,'blocked_count':len(violations),'blocked_paths':violations,'status':'PASS' if not violations else 'FAIL'}
    (out/'history-audit.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:record[k] for k in ['commits_checked','unique_blobs_checked','blocked_count','status']}))
    return bool(violations)
if __name__=='__main__':sys.exit(main())
