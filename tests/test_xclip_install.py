"""Public metadata bootstrap guards, no actual downloads/models/data."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import scripts.install_xclip as installer


@pytest.mark.parametrize('license_name,weight_hash',[('cc-by-nc-4.0','good'),('mit','wrong')])
def test_bootstrap_rejects_unapproved_license_or_weight_before_prepare(tmp_path,monkeypatch,license_name,weight_hash):
    import huggingface_hub
    config=tmp_path/'config';config.mkdir();(config/'xclip-artifacts.json').write_text(json.dumps({'repo':'synthetic/public-model','revision':'pinned',
        'weight_file':'model.safetensors','weight_bytes':123,'weight_sha256':'good'}))
    monkeypatch.setattr(installer,'ROOT',tmp_path)
    info=SimpleNamespace(sha='pinned',card_data={'license':license_name},siblings=[SimpleNamespace(rfilename='model.safetensors',size=123,lfs=SimpleNamespace(sha256=weight_hash))])
    monkeypatch.setattr(huggingface_hub,'HfApi',lambda token:SimpleNamespace(model_info=lambda *args,**kwargs:info))
    with pytest.raises(ValueError):installer.main()
    assert not (tmp_path/'.private/xclip-prepare/metadata.json').exists()
