from cashreview.local_secrets import save,load


def test_user_scoped_dpapi_roundtrip_uses_only_fixed_dummy(tmp_path):
    path=tmp_path/'dummy.dpapi';value={'purpose':'synthetic-unit-test','key':'temporary-fixed-unit-test-only'}
    save(path,value)
    assert b'temporary-fixed-unit-test-only' not in path.read_bytes()
    assert load(path)==value
