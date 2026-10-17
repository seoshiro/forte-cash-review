import pytest
from scripts.oracle_diagnostic import parse_features,pool_features,oracle_times,point_coverage

def test_features_are_strict_and_pooling_preserves_uncertainty():
    assert parse_features('{"signals":["yes","no","unclear"]}',3)==['yes','no','unclear']
    for text in ['{"signals":[true]}','{"signals":["maybe"]}','{"signals":["yes"],"extra":1}']:
        with pytest.raises(ValueError,match='invalid_primitive_structure'):parse_features(text,1)
    assert pool_features([['no','unclear','no'],['yes','no','no']])==['yes','unclear','no']

def test_oracle_uses_actual_point_and_clamps_without_negative_zero_imputation():
    assert oracle_times(8.,10.,[-3,0,1,3])==[5.,8.,9.,9.9]
    assert oracle_times(0.1,2.,[-3,0,1,3])==[0.,0.1,1.1,1.9]
    records=[{'target':1,'label_sec':5.,'sampled_pts':[0.,5.1,8.]},{'target':0,'label_sec':None,'sampled_pts':[0.,3.]}]
    result=point_coverage(records,[.05,.25])
    assert result['0.05']=={'positive_annotations':1,'hits':0,'hit_rate':0.}
    assert result['0.25']=={'positive_annotations':1,'hits':1,'hit_rate':1.}
