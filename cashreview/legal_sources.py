"""Deterministic public-law HTML paragraph provenance; no media/model inputs."""
from html.parser import HTMLParser
import re,hashlib


def canonical(value):return re.sub(r'\s+',' ',value).strip()
def digest(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()


class Paragraphs(HTMLParser):
    def __init__(self,wanted):
        super().__init__(convert_charrefs=True);self.wanted=set(wanted);self.found={};self.current=None;self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=='p':
            if self.current is not None:raise ValueError('Nested source paragraph')
            key=dict(attrs).get('id')
            if key in self.wanted:
                if key in self.found:raise ValueError('Duplicate source anchor')
                self.current=key;self.text=[]
        elif tag=='br' and self.current:self.text.append(' ')
    def handle_data(self,data):
        if self.current:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='p' and self.current:
            self.found[self.current]=canonical(''.join(self.text));self.current=None;self.text=[]


def verified_quotes(document,versions,pin):
    if document.get('id')!=pin['document_id'] or document.get('group_number')!=pin['group_number']:raise ValueError('Official identity mismatch')
    if document.get('is_actual') is not True:raise ValueError('Official actuality flag missing')
    current=[row for row in versions['versions'] if row.get('is_current')]
    if len(current)!=1 or current[0]['document_id']!=document['id']:raise ValueError('Current edition mismatch')
    text=document['text_content']
    if digest(text)!=pin['text_content_sha256']:raise ValueError('Official source digest changed')
    anchors=[anchor for rule in pin['quotes'].values() for anchor in rule['anchors']]
    if len(anchors)!=len(set(anchors)):raise ValueError('Ambiguous configured anchors')
    parser=Paragraphs(anchors);parser.feed(text);parser.close()
    if parser.current or set(parser.found)!=set(anchors) or not all(parser.found.values()):raise ValueError('Missing source paragraph')
    quotes={}
    for rule,info in pin['quotes'].items():
        parts=[parser.found[key] for key in info['anchors']]
        if not parts[0].startswith(info['first_prefix']):raise ValueError('Paragraph number mismatch')
        if digest(canonical(' '.join(parts)))!=info['canonical_sha256']:raise ValueError('Canonical quotation changed')
        quotes[rule]=parts
    return quotes,current[0]


def validate_registry(registry,provenance,document,versions,pin):
    quotes,current=verified_quotes(document,versions,pin)
    identifiers=[rule['id'] for rule in registry['rules']]
    if len(identifiers)!=len(set(identifiers)) or set(identifiers)!=set(quotes):raise ValueError('Registry identity/cardinality mismatch')
    expected={'document_url':pin['document_url'],'api_url':pin['api_url'],'versions_url':pin['versions_url'],
        'official_document_id':document['id'],'official_name':document['official_name'],'official_is_current':True,
        'official_revision_timestamp':current['revision_date'],'text_content_sha256':digest(document['text_content']),
        'canonical_quote_sha256':{key:pin['quotes'][key]['canonical_sha256'] for key in quotes},
        'parser':'stdlib HTMLParser p-id extraction + Unicode whitespace normalization',
        'separate_plain_text_input_used':False,'semantic_detector_accepted':False}
    if any(provenance.get(key)!=value for key,value in expected.items()):raise ValueError('Provenance differs from verified source')
    if registry['source']!=pin['document_url'] or registry['edition']!={**provenance,'source_text_sha256':expected['text_content_sha256']}:raise ValueError('Registry edition/provenance mismatch')
    for rule in registry['rules']:
        key=rule['id'];text='\n\n'.join(quotes[key]);text=('31, подпункт 4: '+text) if key=='R31' else text
        if canonical(rule['verified_source_text'])!=canonical(text):raise ValueError('Registry quotation mismatch')
        if rule['source_anchors']!=[pin['document_url']+'#'+anchor for anchor in pin['quotes'][key]['anchors']]:raise ValueError('Registry source anchors mismatch')
        if rule['canonical_quote_sha256']!=pin['quotes'][key]['canonical_sha256']:raise ValueError('Registry quote digest mismatch')
        if rule.get('semantic_detector_accepted') is not False:raise ValueError('Source check is not detector acceptance')
    return quotes
