"""Read-only PyPI advisory lookup for every installed distribution.

No skipped package is counted as clean. Local CUDA version labels are removed
only for the upstream advisory query, never from the actual environment lock.
"""
from pathlib import Path
import importlib.metadata as metadata,urllib.request,urllib.parse,json,time
from concurrent.futures import ThreadPoolExecutor
from packaging.version import Version
ROOT=Path(__file__).resolve().parents[1]
packages=sorted({(d.metadata['Name'],d.version) for d in metadata.distributions()})
def check(package):
    name,installed=package;version=Version(installed).base_version
    url='https://pypi.org/pypi/'+urllib.parse.quote(name,safe='')+'/'+urllib.parse.quote(version,safe='')+'/json'
    try:
        with urllib.request.urlopen(url,timeout=25) as response:data=json.load(response)
        return {'name':name,'installed':installed,'queried':version,'vulnerabilities':data.get('vulnerabilities',[])}
    except Exception as error:return {'name':name,'installed':installed,'error_type':type(error).__name__}
with ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(check,packages))
failures=[r for r in records if 'error_type' in r]
affected=[r for r in records if r.get('vulnerabilities')]
ids={v['id'] for r in affected for v in r['vulnerabilities']}
summary={'scanner':'project read-only installed-version lookup',
         'service':'PyPI Python Packaging Advisory Database',
         'packages':len(records),'affected_packages':len(affected),
         'unique_advisory_ids':len(ids),'skipped_packages':len(failures),
         'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
         'scope':'installed Python packages; no native codec audit or penetration test'}
(ROOT/'.private/dependency-audit-structured.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(ROOT/'.private/structured-security-safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
raise SystemExit(bool(failures))
