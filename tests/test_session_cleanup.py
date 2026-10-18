import json
import pytest
from filelock import FileLock,Timeout
from cashreview.session_cleanup import purge_final_uploads


def store(root):
    directory=root/'.private/final-service';(directory/'jobs').mkdir(parents=True)
    (directory/'.api-store-contract.json').write_text(json.dumps({'contract':'xclip-experimental-v1'}));return directory


def test_cleanup_removes_only_opaque_uploads_and_preserves_other_directories(tmp_path):
    directory=store(tmp_path);job=directory/'jobs'/('a'*32);job.mkdir();(job/'input.mov').write_bytes(b'generated fixture')
    other=directory/'jobs/manual';other.mkdir();(tmp_path/'source.mov').write_bytes(b'untouched source fixture')
    result=purge_final_uploads(tmp_path);assert result['removed']==1 and result['blocked']==1 and not job.exists() and other.exists()
    assert (tmp_path/'source.mov').read_bytes()==b'untouched source fixture'


def test_running_native_store_lock_blocks_cleanup(tmp_path):
    directory=store(tmp_path);job=directory/'jobs'/('a'*32);job.mkdir()
    with FileLock(str(directory/'.api-service.lock')):
        with pytest.raises(Timeout):purge_final_uploads(tmp_path)
    assert job.exists()


def test_wrong_contract_cannot_be_purged(tmp_path):
    directory=store(tmp_path);(directory/'.api-store-contract.json').write_text(json.dumps({'contract':'other'}))
    with pytest.raises(ValueError):purge_final_uploads(tmp_path)
