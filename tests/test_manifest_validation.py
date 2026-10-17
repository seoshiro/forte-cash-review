import pytest,copy
from scripts.manifest import seconds,label_error,validate_saved_split


@pytest.mark.parametrize('text,expected',[('1минута 8 секунда',68),('2минуты 13 секунды',133),('68 сек',68),('1:08',68),('01:01:08.5',3668.5),('1,5с',1.5),(None,None)])
def test_supported_full_timestamp_formats(text,expected):assert seconds(text)==expected


@pytest.mark.parametrize('text',['1.5м','-8с','11 сек мусор','NaN','inf','1:60','1:2:60','1:2:3:4','-1','1м90с','1м8.5'])
def test_partial_nonfinite_and_invalid_timestamps_are_rejected(text):
    with pytest.raises(ValueError):seconds(text)


def test_positive_point_is_required_negative_point_is_unknown():
    assert label_error(1,None,10)=='positive_missing_timestamp'
    assert label_error(0,None,10) is None
    assert label_error(0,0,10)=='negative_has_timestamp'
    assert label_error(1,10,10)=='label_outside_video'
    assert label_error(1,float('nan'),10)=='label_outside_video'


def test_saved_split_refuses_changed_labels_inventory_groups_and_cross_group_split():
    rows=[{'sha256':'a'*64,'group':'g0'},{'sha256':'b'*64,'group':'g0'}]
    base={'labels_sha256':'fixture','assignments':{'a'*64:'train','b'*64:'train'},'groups':{'a'*64:'g0','b'*64:'g0'}}
    validate_saved_split(base,rows,'fixture')
    variants=[]
    changed=copy.deepcopy(base);changed['labels_sha256']='changed';variants.append(changed)
    changed=copy.deepcopy(base);changed['assignments'].pop('b'*64);variants.append(changed)
    changed=copy.deepcopy(base);changed['groups']['b'*64]='other';variants.append(changed)
    changed=copy.deepcopy(base);changed['assignments']['b'*64]='tune';variants.append(changed)
    changed=copy.deepcopy(base);changed['assignments']['b'*64]=None;variants.append(changed)
    for changed in variants:
        with pytest.raises(ValueError):validate_saved_split(changed,rows,'fixture')
