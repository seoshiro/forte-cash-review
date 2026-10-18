import copy, json
from pathlib import Path
import pytest
from scripts.xclip_last_layer_budget import validate_identical_protocol

ROOT = Path(__file__).resolve().parents[1]


def protocols():
    return (json.loads((ROOT / 'config/xclip-last-layer-protocol.json').read_text()),
            json.loads((ROOT / 'config/xclip-last-layer-budget1800.json').read_text()))


def test_only_wall_caps_and_protocol_identity_change():
    old, current = protocols(); validate_identical_protocol(old, current)
    assert current['budget']['owned_wall_sec'] == current['budget']['learning_phase_wall_sec'] == 1800
    assert current['budget']['maximum_runs'] == 1


@pytest.mark.parametrize('section,key,value', [
    ('head', 'steps', 499), ('head', 'seed', 1), ('head', 'learning_rate', .01),
    ('evaluation', 'folds', 23), ('evaluation', 'threshold_logit', .1),
    ('model', 'rank', 4), ('adapter_optimizer', 'anchor_strength', 1.),
    ('budget', 'max_torch_reserved_mib', 5500), ('budget', 'maximum_tune_runs', 1)])
def test_any_recipe_or_other_resource_change_is_rejected(section, key, value):
    old, current = protocols(); changed = copy.deepcopy(current); changed[section][key] = value
    with pytest.raises(ValueError): validate_identical_protocol(old, changed)
