from pathlib import Path
from scripts.release_assets import SAFE_PUBLIC_ASSETS,approved_asset


def test_only_exact_reviewed_empty_ui_asset_is_allowed():
    root=Path(__file__).resolve().parents[1]
    name='docs/assets/upload-empty.png';data=(root/name).read_bytes()
    assert set(SAFE_PUBLIC_ASSETS)=={name}
    assert approved_asset(name,data)
    assert not approved_asset(name,data+b'changed')
    assert not approved_asset('docs/assets/another.png',data)
    assert not approved_asset('.private/frame.png',data)
