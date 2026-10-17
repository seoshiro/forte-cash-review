"""Read-only official candidate source review; no artifact is loaded/executed."""
from pathlib import Path
import urllib.request,json,ast,hashlib,time
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'.private/pt2-release-review';out.mkdir(exist_ok=True)
paths=['torch/_export/serde/serialize.py','torch/export/__init__.py','torch/export/pt2_archive/_package.py']
records=[]
for version in ['v2.8.0','v2.14.1']:
    for relative in paths:
        url='https://raw.githubusercontent.com/pytorch/pytorch/'+version+'/'+relative
        record={'version':version,'path':relative,'url':url}
        try:
            with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(2_000_000)
            target=out/version/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            tree=ast.parse(raw);calls=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and ast.unparse(node.func) in ['torch.load','torch.export.load']:
                    calls.append({'line':node.lineno,'function':ast.unparse(node.func),
                                  'weights_only':next((ast.unparse(x.value) for x in node.keywords if x.arg=='weights_only'),'NOT_EXPLICIT')})
            record.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),load_calls=calls,
                          explicit_weights_only_false_lines=[i for i,line in enumerate(raw.decode().splitlines(),1) if 'weights_only=False' in line or 'weights_only = False' in line])
        except Exception as error:record['error_type']=type(error).__name__
        records.append(record)
summary={'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
         'scope':'official tagged Python source only; no package installed or user artifact loaded',
         'files':records,'candidate_fix_proven':False,
         'limitation':'call-site keyword inventory is not a deserialization-path proof or successful candidate runtime test'}
(out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
