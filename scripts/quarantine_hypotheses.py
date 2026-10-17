"""Local-only conservative index. Never emit user text, IDs, paths or exceptions."""
from pathlib import Path
import json,re,hashlib,sys,unicodedata
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.private/user-hypotheses'
ORIGINAL_REGISTRATION_SHA='c9e0b0010fdc9c234a9bad0da0d48832edea73e1acff7ad6ec73bae2be498e07'
DASHES=r'\-\u2010\u2011\u2012\u2013\u2014\u2212'
IDENTIFIER=rf'[X\u0425x\u0445][ \t]*[{DASHES}][ \t]*\d{{1,3}}'
HEADER=re.compile(rf'^[ \t]*({IDENTIFIER})(?:\.mov)?[ \t]*:?[ \t\r]*$',re.IGNORECASE|re.MULTILINE)
CANDIDATE=re.compile(rf'(?<!\w)[X\u0425x\u0445][ \t]*[{DASHES}][ \t]*[^\s,;:)\]]*')
AMBIGUOUS=re.compile(r'\b(?:видео|ролик|video)\s*[-_#№]?\s*\d',re.IGNORECASE)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def canonical(value):
    text=unicodedata.normalize('NFKC',str(value)).strip()
    match=re.fullmatch(rf'[X\u0425x\u0445][ \t]*[{DASHES}][ \t]*(\d{{1,3}})(?:\.mov)?',text,re.IGNORECASE)
    if not match:raise ValueError('Noncanonical identifier')
    return 'X-'+str(int(match[1]))


def inspect_structure(text,manifest):
    """Return indices only after whole-file validation. No semantic assessment."""
    mapping={}
    for row in manifest:
        key=canonical(row['original_id'])
        if key in mapping:raise ValueError('Manifest identifier ambiguity')
        if row['split'] not in ['train','tune','holdout']:raise ValueError('Unknown split')
        mapping[key]=row['split']
    headers=list(HEADER.finditer(text))
    if not headers or text[:headers[0].start()].strip('\ufeff \t\r\n'):raise ValueError('Unstructured prefix')
    result=[];seen=set()
    for index,header in enumerate(headers):
        key=canonical(header[1]);end=headers[index+1].start() if index+1<len(headers) else len(text)
        body=text[header.end():end]
        if key not in mapping or key in seen or not body.strip():raise ValueError('Unknown duplicate or empty section')
        seen.add(key)
        if AMBIGUOUS.search(body) or any(canonical(ref[0].rstrip('.!?'))!=key for ref in CANDIDATE.finditer(body)):raise ValueError('Ambiguous body reference')
        result.append({'canonical_id':key,'split':mapping[key],'start_char':header.start(),'end_char':end})
    # Non-TRAIN content must not enter any proposed TRAIN index. The original
    # whole file remains quarantined and no slices/text are exported here.
    return result


def inspect_local():
    inventory=json.loads((OUT/'metadata-inventory.json').read_text(encoding='ascii'))
    if len(inventory['files'])!=1:raise ValueError('Need exactly one metadata match')
    entry=inventory['files'][0];path=Path(entry['path']);downloads=Path('C:/Users/gokusen/Downloads').resolve()
    if path.is_symlink() or path.resolve().parent!=downloads or path.suffix.casefold()!='.txt':raise ValueError('Unapproved local source')
    if not all(token.casefold() in path.name.casefold() for token in ['Excel','объяснений','поэтому']):raise ValueError('Unapproved filename')
    stat=path.stat()
    if not 0<stat.st_size<=65536 or stat.st_size!=entry['bytes'] or stat.st_mtime!=entry['modified_utc_epoch']:raise ValueError('Source metadata changed')
    registration_path=ROOT/'.private/xclip-control/registration.json'
    if digest(registration_path)!=ORIGINAL_REGISTRATION_SHA:raise ValueError('Original registration changed')
    registration=json.loads(registration_path.read_text());manifest_path=ROOT/'.private/dataset/manifest.json'
    for name in ['.private/dataset/manifest.json','.private/dataset/split.json']:
        if digest(ROOT/name)!=registration['frozen_sha256'][name]:raise ValueError('Frozen split identity changed')
    # Only this local process reads bytes. It has no model/network calls, prints,
    # logging, content-derived error messages, training or metric integration.
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)!=stat.st_size or path.stat().st_mtime!=stat.st_mtime:raise ValueError('Source changed while reading')
    text=raw.decode('utf-8-sig',errors='strict')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'));index=inspect_structure(text,manifest)
    record={'provenance':'User-stated authorship with general legal phrasing assistance; not independently verified',
        'epistemic_status':'UNVERIFIED_USER_HYPOTHESES_NOT_GROUND_TRUTH','source_sha256':hashlib.sha256(raw).hexdigest(),
        'original_registration_sha256':ORIGINAL_REGISTRATION_SHA,'source_path':str(path),
        'whole_file_quarantined':True,'syntactic_index_only':True,'semantic_correspondence_verified':False,
        'train_review_index':[row for row in index if row['split']=='train'],'excluded_nontrain_sections':sum(row['split']!='train' for row in index),
        'text_slices_exported':False,'training_metrics_or_model_calls':False,'requires_local_human_provenance_and_correspondence_review':True}
    with (OUT/'quarantined-index.json').open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
    return bool(record['train_review_index'])


def main():
    owns_attempt=False
    try:
        OUT.mkdir(parents=True,exist_ok=True)
        with (OUT/'inspection-attempt.json').open('x') as stream:
            owns_attempt=True
            json.dump({'local_index_inspection_started':True},stream)
        separable=inspect_local()
        result={'found':True,'status':'quarantined_pending_local_review','syntactic_train_index_possible':separable,
            'safe_semantic_train_only_use_established':False,'content_emitted':False,'training_or_metrics_used':False,'original_modified':False}
    except Exception as error:
        result={'found':True,'status':'whole_file_quarantined','syntactic_train_index_possible':False,
            'safe_semantic_train_only_use_established':False,'technical_error_type':type(error).__name__,
            'content_emitted':False,'training_or_metrics_used':False,'original_modified':False}
    if owns_attempt:
        try:(OUT/'safe-status.json').write_text(json.dumps(result,indent=2),encoding='ascii')
        except Exception:result['safe_status_publication_failed']=True
    else:result['safe_status_not_published']=True
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
