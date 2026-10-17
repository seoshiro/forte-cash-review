import copy
import pytest
from cashreview.legal_sources import canonical,digest,verified_quotes,validate_registry


def fixture(html=None):
    html=html or '<p id="a">20. First&nbsp;<span>public</span> requirement.</p><p id="b">Second\n public condition.</p>'
    document={'id':'synthetic-source','group_number':'synthetic-law','is_actual':True,'text_content':html,'official_name':'Synthetic unit law'}
    pin={'document_id':document['id'],'group_number':document['group_number'],'text_content_sha256':digest(html),
        'quotes':{'RULE':{'anchors':['a','b'],'first_prefix':'20.','canonical_sha256':digest('20. First public requirement. Second public condition.')}}}
    versions={'versions':[{'is_current':True,'document_id':document['id'],'revision_date':'synthetic'}]}
    return document,versions,pin


def registry_fixture():
    document,versions,pin=fixture();pin.update(document_url='https://unit.invalid/law',api_url='https://unit.invalid/api',versions_url='https://unit.invalid/versions')
    provenance={key:pin[key] for key in ['document_url','api_url','versions_url']}
    provenance.update(official_document_id=document['id'],official_name=document['official_name'],official_is_current=True,
        official_revision_timestamp='synthetic',text_content_sha256=digest(document['text_content']),
        canonical_quote_sha256={'RULE':pin['quotes']['RULE']['canonical_sha256']},retrieved_utc='synthetic',
        parser='stdlib HTMLParser p-id extraction + Unicode whitespace normalization',separate_plain_text_input_used=False,semantic_detector_accepted=False)
    registry={'source':pin['document_url'],'edition':{**provenance,'source_text_sha256':provenance['text_content_sha256']},
        'rules':[{'id':'RULE','verified_source_text':'20. First public requirement. Second public condition.',
            'source_anchors':[pin['document_url']+'#a',pin['document_url']+'#b'],
            'canonical_quote_sha256':pin['quotes']['RULE']['canonical_sha256'],'semantic_detector_accepted':False}]}
    return registry,provenance,document,versions,pin


def test_registry_identity_and_full_provenance_are_bound_to_actual_source():
    assert set(validate_registry(*registry_fixture()))=={'RULE'}
    mutations=[lambda r:r.update(rules=[]),lambda r:r['rules'].append(copy.deepcopy(r['rules'][0])),
        lambda r:r['edition'].update(official_document_id='wrong'),lambda r:r['edition'].update(official_revision_timestamp='wrong'),
        lambda r:r.update(source='https://other.invalid'),lambda r:r['rules'][0].update(source_anchors=['wrong']),
        lambda r:r['rules'][0].update(canonical_quote_sha256='wrong'),lambda r:r['rules'][0].update(semantic_detector_accepted=True)]
    for mutate in mutations:
        values=registry_fixture();mutate(values[0])
        with pytest.raises(ValueError):validate_registry(*values)
    values=registry_fixture();values[1]['text_content_sha256']='wrong';values[0]['edition']['text_content_sha256']='wrong';values[0]['edition']['source_text_sha256']='wrong'
    with pytest.raises(ValueError):validate_registry(*values)


def test_direct_html_entities_inline_tags_and_whitespace_link_to_exact_quotes():
    quotes,current=verified_quotes(*fixture())
    assert quotes=={'RULE':['20. First public requirement.','Second public condition.']}
    assert current['document_id']=='synthetic-source'
    assert canonical(' A\u00a0 B\n C ' )=='A B C'


def test_altered_raw_source_or_quote_is_rejected():
    document,versions,pin=fixture();document['text_content']+=' '
    with pytest.raises(ValueError):verified_quotes(document,versions,pin)
    document,versions,pin=fixture();pin['quotes']['RULE']['canonical_sha256']=digest('Different quotation')
    with pytest.raises(ValueError):verified_quotes(document,versions,pin)


@pytest.mark.parametrize('html',[
    '<p id="a">20. First public requirement.</p><p id="a">Repeated.</p><p id="b">Second public condition.</p>',
    '<p id="a">20. First public requirement.</p>',
    '<p id="a">21. First public requirement.</p><p id="b">Second public condition.</p>',
    '<p id="a">20. <p id="b">Second public condition.</p></p>'
])
def test_ambiguous_missing_wrong_number_or_nested_anchors_fail_closed(html):
    with pytest.raises(ValueError):verified_quotes(*fixture(html))


def test_wrong_or_multiple_current_editions_and_actuality_are_rejected():
    document,versions,pin=fixture();versions['versions'][0]['document_id']='other'
    with pytest.raises(ValueError):verified_quotes(document,versions,pin)
    document,versions,pin=fixture();versions['versions'].append(copy.deepcopy(versions['versions'][0]))
    with pytest.raises(ValueError):verified_quotes(document,versions,pin)
    document,versions,pin=fixture();document['is_actual']=False
    with pytest.raises(ValueError):verified_quotes(document,versions,pin)
