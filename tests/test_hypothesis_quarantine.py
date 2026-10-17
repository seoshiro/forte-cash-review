import pytest
from scripts.quarantine_hypotheses import inspect_structure
M=[{'original_id':'X-1','split':'train'},{'original_id':'Х-2','split':'holdout'}]


def test_structured_hypotheses_keep_nontrain_separate_without_exporting_text():
    index=inspect_structure('X-1\nSYNTHETIC claim only.\nХ-2\nSYNTHETIC other.\n',M)
    assert [r['split'] for r in index]==['train','holdout']
    assert all(set(row)=={'canonical_id','split','start_char','end_char'} for row in index)


@pytest.mark.parametrize('text',['Preface\nX-1\nclaim','X-1\nclaim Х-2','X-1\nclaim\nX-1\nclaim',
    'X-9\nclaim','X-1\nclaim видео2','X-1: same-line description','X-1\nclaim X-1000',
    'X-1\nclaim X-2suffix','X-1\nclaim X‑2'])
def test_any_ambiguous_reference_quarantines_whole_file(text):
    with pytest.raises(ValueError):inspect_structure(text,M)


def test_setup_and_status_write_failure_never_emit_private_exception(tmp_path,monkeypatch,capsys):
    import scripts.quarantine_hypotheses as module
    target=tmp_path/'unavailable';monkeypatch.setattr(module,'OUT',target)
    original=type(target).mkdir
    def fail(path,*args,**kwargs):
        if path==target:raise PermissionError('PRIVATE_PATH_OR_CONTENT')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(type(target),'mkdir',fail);module.main()
    output=capsys.readouterr()
    assert 'PRIVATE_PATH_OR_CONTENT' not in output.out and not output.err
    assert 'PermissionError' in output.out and 'safe_status_not_published' in output.out


@pytest.mark.parametrize('dash',['-','\u2010','\u2011','\u2012','\u2013','\u2014','\u2212'])
def test_duplicate_header_with_any_accepted_dash_quarantines(dash):
    with pytest.raises(ValueError):inspect_structure('X-1\nSYNTHETIC first.\nX'+dash+'1\nSYNTHETIC duplicate.\n',M)


def test_nonowner_attempt_cannot_overwrite_prior_status_or_inspect(tmp_path,monkeypatch,capsys):
    import scripts.quarantine_hypotheses as module
    monkeypatch.setattr(module,'OUT',tmp_path)
    (tmp_path/'inspection-attempt.json').write_text('{}')
    prior=b'{"safe_prior_result": true}'
    (tmp_path/'safe-status.json').write_bytes(prior)
    def forbidden():raise AssertionError('MUST_NOT_READ_SOURCE')
    monkeypatch.setattr(module,'inspect_local',forbidden)
    module.main()
    output=capsys.readouterr()
    assert not output.err and 'MUST_NOT_READ_SOURCE' not in output.out
    assert 'FileExistsError' in output.out and 'safe_status_not_published' in output.out
    assert (tmp_path/'safe-status.json').read_bytes()==prior
