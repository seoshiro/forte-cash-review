"""Offline verify of linked current official sources; no config mutation or media."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.legal_sources import validate_registry


def main():
    directory=ROOT/'.private/sources/current-nb231';pin=json.loads((ROOT/'config/legal-source-pin.json').read_text())
    document=json.loads((directory/'document.json').read_text(encoding='utf-8'));document=document.get('document',document)
    versions=json.loads((directory/'versions.json').read_text(encoding='utf-8'))
    provenance=json.loads((directory/'provenance.json').read_text(encoding='utf-8'))
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ['document','versions']:
        if sha(directory/(name+'.json'))!=provenance['response_sha256'][name]:raise ValueError('Source response provenance mismatch')
    if sha(ROOT/'config/legal-source-pin.json')!=provenance['source_pin_sha256']:raise ValueError('Source pin changed')
    if sha(ROOT/'cashreview/legal_sources.py')!=provenance['parser_code_sha256']:raise ValueError('Parser version changed')
    if sha(ROOT/'scripts/refresh_legal_source.py')!=provenance['refresh_code_sha256']:raise ValueError('Refresh implementation changed')
    registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
    quotes=validate_registry(registry,provenance,document,versions,pin)
    print(json.dumps({'status':'PASS','linked_rules':len(quotes),'network_used':False,'separate_plain_text_used':False,'bank_data_used':False,'semantic_detectors_accepted':0}))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__}));sys.exit(1)
