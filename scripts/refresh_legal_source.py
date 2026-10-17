"""Fetch only pinned official public law and link source to registry quotations."""
from pathlib import Path
import sys,json,datetime,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.legal_sources import verified_quotes,validate_registry,canonical,digest
OUT=ROOT/'.private/sources/current-nb231'


def main():
    import httpx
    pin=json.loads((ROOT/'config/legal-source-pin.json').read_text());OUT.mkdir(exist_ok=True,parents=True)
    fetched=datetime.datetime.now(datetime.timezone.utc).isoformat();raw={}
    with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as client:
        for name,key in [('document','api_url'),('versions','versions_url')]:
            chunks=[];size=0
            with client.stream('GET',pin[key]) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>10*1024*1024:raise ValueError('Bounded official source exceeded')
                    chunks.append(chunk)
            raw[name]=b''.join(chunks);(OUT/(name+'.json')).write_bytes(raw[name])
    document=json.loads(raw['document']);document=document.get('document',document);versions=json.loads(raw['versions'])
    quotes,current=verified_quotes(document,versions,pin)
    registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
    identifiers=[r['id'] for r in registry['rules']]
    if len(identifiers)!=len(set(identifiers)) or set(identifiers)!=set(quotes):raise ValueError('Registry scope/cardinality mismatch')
    for rule in registry['rules']:
        text='\n\n'.join(quotes[rule['id']])
        if rule['id']=='R31':text='31, подпункт 4: '+text
        if canonical(rule['verified_source_text'])!=canonical(text):raise ValueError('Existing registry quotation mismatch')
        rule['verified_source_text']=text
        rule['source_anchors']=[pin['document_url']+'#'+key for key in pin['quotes'][rule['id']]['anchors']]
        rule['canonical_quote_sha256']=pin['quotes'][rule['id']]['canonical_sha256'];rule['semantic_detector_accepted']=False
        rule['verification']='Direct extraction from pinned current official text_content; exact quote hashes and existing-registry comparison passed. No visual applicability or detector acceptance implied.'
    rules={r['id']:r for r in registry['rules']}
    rules['R20']['applicability_scope']='Глава 2, параграф 2: приём наличных денег. Пункт содержит две самостоятельные ветви; текущая гипотеза охватывает только хранение ранее принятой наличности.'
    rules['R20']['visual_conditions']='Подтверждены приём наличных, принадлежность денег к ранее принятой операции, рабочее место и последовательность до/после; ранее принятые деньги наблюдаемо остаются вне подходящего устройства. Если назначение устройства или принадлежность денег не установлены, условие не установлено. Присутствие клиента при пересчёте — отдельная ветвь, автоматически не распознаётся.'
    note=' Видимый замок или положение крышки сами по себе не устанавливают соответствие устройства требованию «закрывающихся на ключ».'
    if note not in rules['R20']['exclusions']:rules['R20']['exclusions']+=note
    rules['R22']['applicability_scope']='Глава 2, параграф 2: консервативно ограничено подтверждённой процедурой приёма наличных, без расширения на любое обслуживание.'
    rules['R22']['visual_conditions']='Подтверждены приём наличных, незавершённое обслуживание клиента, границы рабочего места, роль кассового работника и фактический уход в последовательности до/после.'
    rules['R31']['applicability_scope']='Глава 2, параграф 3: выдача наличных. Применять вместе со всеми исключениями пункта 32 для целой упаковки банкнот и условий выдачи монет; неподтверждённая целостность не означает нарушение.'
    rules['R31']['exclusions']='Учитывать перечисленные пунктом 32 условия выдачи по обозначенным суммам в упаковках при целостности. Неполная пачка и неполный корешок различаются: банкноты из неполных либо повреждённых корешков требуют полистного пересчёта, монеты из неполных мешков — пересчёта по кружкам. Неустановленные полнота, целостность, вид упаковки или последовательность означают неустановленность условия; отсутствие видимого ручного пересчёта само по себе недостаточно.'
    rules['R42']['applicability_scope']='Глава 2, параграф 4: внутренние кассовые операции. Приём/выдача клиентам прямо исключены; роль контролирующего работника определена пунктом 2(2), а не наличием второго человека.'
    rules['R42']['role_reference_urls']=[pin['document_url']+'#z531',pin['document_url']+'#z539']
    provenance={'document_url':pin['document_url'],'api_url':pin['api_url'],'versions_url':pin['versions_url'],
        'official_document_id':document['id'],'official_name':document['official_name'],'official_is_current':True,
        'official_revision_timestamp':current['revision_date'],'retrieved_utc':fetched,
        'text_content_sha256':digest(document['text_content']),'response_sha256':{key:hashlib.sha256(value).hexdigest() for key,value in raw.items()},
        'canonical_quote_sha256':{key:pin['quotes'][key]['canonical_sha256'] for key in quotes},
        'parser':'stdlib HTMLParser p-id extraction + Unicode whitespace normalization',
        'parser_code_sha256':hashlib.sha256((ROOT/'cashreview/legal_sources.py').read_bytes()).hexdigest(),
        'refresh_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_pin_sha256':hashlib.sha256((ROOT/'config/legal-source-pin.json').read_bytes()).hexdigest(),
        'separate_plain_text_input_used':False,'semantic_detector_accepted':False}
    (OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    registry['source_status']='Current official API edition and direct HTML quotes freshly verified through one linked provenance manifest; no visual detector or video applicability established.'
    registry['edition']={**provenance,'source_text_sha256':provenance['text_content_sha256']}
    validate_registry(registry,provenance,document,versions,pin)
    (ROOT/'config/rules.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
    safe={'status':'PASS','official_versions_count':len(versions['versions']),'unique_current_editions':1,'linked_registry_rules':len(quotes),
        'source_text_sha256':provenance['text_content_sha256'],'registry_canonical_quotes_unchanged':True,
        'raw_html_to_quote_link_verified':True,'separate_plain_text_input_used':False,'semantic_detectors_accepted':0,
        'bank_data_used':False,'fetched_utc':fetched,'provenance_sha256':hashlib.sha256((OUT/'provenance.json').read_bytes()).hexdigest()}
    (OUT/'safe-summary.json').write_text(json.dumps(safe,indent=2));print(json.dumps(safe))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'bank_data_used':False}));sys.exit(1)
