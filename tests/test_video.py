from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.manifest import seconds,normalize
from scripts.synthetic import generate
from cashreview.video import sample,inspect


def test_label_normalization():
    assert normalize('Х-SYNTHETIC-9007')==normalize('X-SYNTHETIC-9007.mov')
    assert seconds('2минута 13 секунда')==133
    assert seconds(None) is None
    assert seconds('02:13')==133


def test_pts_sampling(tmp_path):
    p=generate(tmp_path/'safe.mov');info=inspect(p,decode=True)
    assert info['decoded_frames']==90 and info['pts_monotonic']
    fs=sample(p,[.11,1.37,2.8])
    assert len(fs)==3
    for f,t in zip(fs,[.11,1.37,2.8]):assert 0<=f.sec-t<.034
