import importlib
import pytest


@pytest.mark.parametrize('name', ['scripts.summarize_temporal_learnability',
                                  'scripts.summarize_xclip_temporal_recipe'])
def test_failed_reverification_revokes_old_calculation_success(tmp_path, monkeypatch, name):
    module = importlib.import_module(name)
    monkeypatch.setattr(module, 'OUT', tmp_path)
    old = tmp_path / 'calculation-safe-summary.json'
    old.write_text('{"status":"PASS","synthetic_old_value":1}')
    with pytest.raises(FileNotFoundError): module.main()
    assert not old.exists()
