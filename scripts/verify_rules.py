"""Freeze already inspected public paragraphs from the current official version.

This script only reads public legal sources and code config. It never reads videos.
"""
from pathlib import Path
import json,re,hashlib,time
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'.private/sources';d=json.loads((source/'nb231-document.json').read_text(encoding='utf-8'));d=d.get('document',d)
versions=json.loads((source/'nb231-versions.json').read_text(encoding='utf-8'))
current=[v for v in versions['versions'] if v.get('is_current')]
if len(current)!=1 or current[0]['document_id']!=d['id'] or d['group_number']!='V1900019680':raise RuntimeError('Current source mismatch')
text=(source/'nb231-plain.txt').read_text(encoding='utf-8')
def paragraph(n):
    a=re.search(r'(?:^|\n)\s*'+str(n)+r'\.\s',text)
    if not a:raise RuntimeError('Paragraph absent')
    b=re.search(r'(?:^|\n)\s*'+str(n+1)+r'\.\s',text[a.end():])
    if not b:raise RuntimeError('Paragraph boundary absent')
    return text[a.start():a.end()+b.start()].strip()
cfg=ROOT/'config/rules.json';registry=json.loads(cfg.read_text(encoding='utf-8'))
mapping={'R20':[20],'R22':[22],'R31':[31,32],'R42':[42]}
for rule in registry['rules']:
    quotes=[paragraph(n) for n in mapping[rule['id']]]
    if rule['id']=='R31':
        # Only subclause 4 is in scope. Identity/signature checks are excluded.
        m=re.search(r'(?:^|\n)\s*4\)(.*?)(?=\n\s*5\))',quotes[0],re.S)
        if not m:raise RuntimeError('Cash-count subclause absent')
        quotes[0]='31, подпункт 4: '+m.group(0).strip()
    rule['verified_source_text']='\n\n'.join(quotes);rule['enabled']=True
    rule['verification']='Exact paragraph and exceptions read from full official current document; does not establish applicability to any particular video.'
registry['source_status']='Full official text retrieved. Source history marks this UUID current. Selected paragraphs and exclusions inspected; application requires all visual conditions.'
registry['edition']={'official_document_id':d['id'],'official_is_current':True,'official_revision_timestamp':current[0]['revision_date'],'body_effective_date_note':'Amendments effective 12.07.2026 appear in the source text. Database end_date is not interpreted as repeal.','retrieved_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_text_sha256':hashlib.sha256(d['text_content'].encode()).hexdigest()}
cfg.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'current_official_source_verified':True,'enabled_rule_ids':list(mapping),'real_video_applicability_not_asserted':True}))
