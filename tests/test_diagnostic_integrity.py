import numpy as np
from scripts.prototype_cache_diagnostic import cache_inventory,verify_inventory,centroids
from scripts.diagnose_qvt_mechanics import mechanical_conclusion


def test_cache_digest_inventory_detects_changed_input(tmp_path):
    cache=tmp_path/'.private/qvt-control/features';cache.mkdir(parents=True)
    path=cache/('a'*64+'.npz');np.savez(path,features=np.zeros((3,4)))
    inventory=cache_inventory([{'sha256':'a'*64}],tmp_path)
    assert verify_inventory(inventory,tmp_path)
    np.savez(path,features=np.ones((3,4)))
    assert not verify_inventory(inventory,tmp_path)


def test_mechanics_conclusion_fails_closed():
    assert mechanical_conclusion({'normalization':True}).startswith('Mechanical checks pass')
    assert mechanical_conclusion({'normalization':True,'direction':False}).startswith('One or more')
    assert mechanical_conclusion({}).startswith('One or more')
    assert mechanical_conclusion({'untyped':'true'}).startswith('One or more')


def test_centroids_give_each_negative_video_equal_mass():
    def item(target,features,point=None):
        return {'target':target,'times':np.arange(len(features),dtype=float),'features':np.array(features,dtype=float),'label_sec':point}
    positive,negative=centroids([item(1,[[1.,0.]],0.),item(0,[[1.,0.]]*2),item(0,[[0.,1.]]*10)],'static')
    np.testing.assert_allclose(positive,[1.,0.])
    np.testing.assert_allclose(negative,[2**-.5,2**-.5])
