"""Fault injection checks commit authority without any training/media."""
import json
from pathlib import Path
import numpy as np
import pytest
from xclip_candidate.last_layer import Head,Adapter
import xclip_candidate.fit_checkpoints as module


def test_failed_commit_marker_keeps_prior_fit_and_ignores_pending_payloads(tmp_path,monkeypatch):
    cfg=json.loads((Path(__file__).resolve().parents[1]/'config/xclip-last-layer-protocol.json').read_text())
    items=[{'sha256':'synthetic','group':'generated','target':1,'label_sec':1.}]
    def fake_fit(items,cfg,enabled,check,device):
        return ((np.zeros(512),np.eye(512,8)),Head(cfg['head']),Adapter(cfg['model']) if enabled else None),{'optimizer_steps':500}
    cache=module.CompletedFits(tmp_path/'fits','registered',fake_fit,maximum=2);cache(items,cfg,False,device='cpu')
    original=module.atomic_json
    def fail_marker(path,*args,**kwargs):
        if Path(path).name=='commit.json':raise OSError('Synthetic disk commit interruption')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(module,'atomic_json',fail_marker)
    with pytest.raises(OSError):cache(items,cfg,True,device='cpu')
    assert cache.count()==1 and not (tmp_path/'fits/0002').exists()
    assert any(p.name.startswith('.pending-') for p in (tmp_path/'fits').iterdir())
    monkeypatch.setattr(module,'atomic_json',original)
    resumed=module.CompletedFits(tmp_path/'fits','registered',fake_fit,maximum=2)
    resumed(items,cfg,False,device='cpu');resumed(items,cfg,True,device='cpu')
    assert resumed.count()==2
