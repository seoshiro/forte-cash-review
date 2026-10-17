import numpy as np
from PIL import Image
from xclip_candidate.spatial import prepare_view,select_fallback,evaluate,accepted
G={'crop_xyxy_normalized':[.1,.05,.9,.95],'output_side':224,'padding_rgb':[124,116,104]}


def test_full_field_preserves_edges_and_fixed_crop_drops_outer_border():
    image=Image.new('RGB',(200,100),'blue')
    for x in range(10):
        for y in range(100):image.putpixel((x,y),(255,0,0))
    full=prepare_view(image,G);crop=prepare_view(image,G,True)
    assert full.size==crop.size==(224,224)
    assert full.getpixel((0,0))==(124,116,104) and full.getpixel((0,100))[0]>200
    assert crop.getpixel((0,100))[2]>200 and crop.getpixel((0,100))[0]<10


def test_fallback_uses_frozen_zero_without_looking_at_labels():
    assert select_fallback((.2,1.),(-.1,2.))==(.2,1.)
    assert select_fallback((.4,1.),(.1,2.))==(.4,2.)
    assert select_fallback((-.2,1.),(-.1,2.))==(-.1,1.)


def test_every_held_group_is_absent_from_both_centroid_fits(monkeypatch):
    import xclip_candidate.spatial as module
    original=module.centroids;seen=[]
    def fit(items,arm):seen.append(({i['group'] for i in items},arm));return original(items,arm)
    monkeypatch.setattr(module,'centroids',fit)
    items=[]
    for group in ['a','b','c']:
        for target in [0,1]:
            vectors=np.tile([0.,1.] if not target else [1.,0.],(2,1))
            items.append({'group':group,'target':target,'label_sec':.5 if target else None,'sha256':group+str(target),
                'times':np.array([.5,1.5]),'full_field':vectors,'central_crop':vectors})
    report,_=evaluate(items)
    assert len(seen)==6 and all(len(groups)==2 for groups,arm in seen)
    assert [groups for groups,arm in seen]==[set('bc'),set('bc'),set('ac'),set('ac'),set('ab'),set('ab')]
    assert all(value['confusion_matrix_tn_fp_fn_tp']==[[3,0],[0,3]] for value in report.values())


def test_original_registration_replacement_is_rejected_before_input_loading(tmp_path,monkeypatch):
    import pytest
    import scripts.xclip_spatial as runner
    path=tmp_path/'.private/xclip-control/registration.json';path.parent.mkdir(parents=True);path.write_text('original')
    monkeypatch.setattr(runner,'ROOT',tmp_path);monkeypatch.setattr(runner,'FILES',[])
    registration={'code_sha256':{},'original_registration_sha256':runner.sha(path),'source_sha256':['synthetic']}
    calls=[];monkeypatch.setattr(runner,'inputs',lambda:(calls.append(True) or [{'sha256':'synthetic'}]))
    runner.verify_registered(registration);assert calls==[True];path.write_text('changed')
    with pytest.raises(ValueError,match='Original registration changed'):runner.verify_registered(registration)
    assert calls==[True]
