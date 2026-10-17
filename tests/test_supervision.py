import json,os,sys,time
from pathlib import Path
import psutil,pytest
from cashreview.supervision import supervise,reconcile_interrupted,atomic_json
ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows owned job object tests')


def run(tmp_path,mode,budget=5):return supervise([sys.executable,str(ROOT/'scripts/synthetic_supervision_worker.py'),mode],tmp_path/mode,budget,3,str(ROOT))


@pytest.mark.parametrize('mode,reason,code',[('success','completed',0),('control_failure','completed',0),
    ('hard_exit','worker_exit',7),('exception','worker_exit',1),('no_report','missing_worker_report',0),
    ('invalid_report','invalid_worker_report',0),('inconsistent_success','invalid_worker_report',0),('server_exit','server_exit',1)])
def test_outcomes_are_durable_safe_and_separate_from_quality(tmp_path,mode,reason,code):
    report=run(tmp_path,mode)
    assert report['reason']==reason and report['worker_exit_code']==code and report['cleanup_complete']
    assert report['quality_gate_passed']==(mode=='success')
    assert report==json.loads((tmp_path/mode/'terminal-safe-summary.json').read_text())
    assert 'Synthetic raw exception' not in json.dumps(report) and 'secret_or_description' not in json.dumps(report)
    if mode=='server_exit':assert report['server_exit_code']==9
    if mode=='hard_exit':assert report['partial_progress_preserved'] and report['completed_cases']==1


def test_hard_deadline_kills_and_records_actual_exit(tmp_path):
    start=time.monotonic();report=run(tmp_path,'timeout',.25)
    assert report['reason']=='deadline' and report['deadline_exceeded'] and not report['quality_gate_passed']
    assert report['worker_exit_code'] is not None and report['cleanup_complete'] and time.monotonic()-start<5


def test_worker_hard_exit_cannot_leave_its_registered_descendant(tmp_path):
    report=run(tmp_path,'orphan')
    pid=json.loads((tmp_path/'orphan/synthetic-child-identity.json').read_text())['pid']
    assert report['worker_exit_code']==7 and report['cleanup_complete'] and not psutil.pid_exists(pid)


def test_repeat_does_not_change_terminal_checkpoint(tmp_path):
    run(tmp_path,'success');path=tmp_path/'success/terminal-safe-summary.json';before=path.read_bytes()
    with pytest.raises(FileExistsError):run(tmp_path,'success')
    assert path.read_bytes()==before


def test_missing_monitor_is_reconciled_without_fabricating_exit_code(tmp_path):
    atomic_json(tmp_path/'monitor-owner.json',{'pid':os.getpid(),'created':psutil.Process().create_time()})
    with pytest.raises(RuntimeError):reconcile_interrupted(tmp_path)
    atomic_json(tmp_path/'monitor-owner.json',{'pid':2147483647,'created':0})
    report=reconcile_interrupted(tmp_path)
    assert report['status']=='interrupted' and report['worker_exit_code'] is None and not report['quality_gate_passed']


def test_primary_report_write_failure_has_explicit_safe_fallback(tmp_path,monkeypatch):
    import cashreview.supervision as supervision
    original=supervision.atomic_json
    def fail_terminal(path,data,**kwargs):
        if Path(path).name=='terminal-safe-summary.json':raise OSError('Synthetic write failure')
        original(path,data,**kwargs)
    monkeypatch.setattr(supervision,'atomic_json',fail_terminal)
    report=run(tmp_path,'success')
    assert report['status']=='failed' and report['reason']=='terminal_write_failed' and not report['quality_gate_passed']
    assert report==json.loads((tmp_path/'success/emergency-safe-summary.json').read_text())


def test_final_status_write_failure_never_publishes_success_terminal(tmp_path,monkeypatch):
    import cashreview.supervision as supervision
    original=supervision.atomic_json
    def fail_success_status(path,data,**kwargs):
        if Path(path).name=='status.json' and data.get('status')=='completed':raise OSError('Synthetic final status write failure')
        original(path,data,**kwargs)
    monkeypatch.setattr(supervision,'atomic_json',fail_success_status)
    report=run(tmp_path,'success')
    assert report['status']=='failed' and not report['quality_gate_passed']
    assert not (tmp_path/'success/terminal-safe-summary.json').exists()
    assert reconcile_interrupted(tmp_path/'success')['status']=='failed'


def test_stale_unowned_directory_is_rejected_before_any_process(tmp_path):
    directory=tmp_path/'success';directory.mkdir();atomic_json(directory/'start-gate.json',{'start':True})
    path=directory/'worker-safe-summary.json';atomic_json(path,{'status':'completed','completed_cases':3,'passed_cases':3,'total_cases':3})
    before=path.read_bytes()
    with pytest.raises(FileExistsError):run(tmp_path,'success')
    assert path.read_bytes()==before and not (directory/'monitor-owner.json').exists()


def test_slow_terminal_persistence_is_included_in_deadline(tmp_path,monkeypatch):
    import cashreview.supervision as supervision
    original=supervision.atomic_json
    def slow_success(path,data,**kwargs):
        if Path(path).name=='terminal-safe-summary.json' and data.get('status')=='completed':time.sleep(1)
        original(path,data,**kwargs)
    monkeypatch.setattr(supervision,'atomic_json',slow_success)
    report=run(tmp_path,'success',1)
    assert report['status']=='failed' and report['reason']=='deadline' and not report['quality_gate_passed']
    assert reconcile_interrupted(tmp_path/'success')['status']=='failed'


def test_post_replace_timeout_and_failed_fallback_cannot_resurrect_success(tmp_path,monkeypatch):
    import cashreview.supervision as supervision
    original=supervision.atomic_json
    def fail_after_commit(path,data,**kwargs):
        if Path(path).name=='emergency-safe-summary.json':raise OSError('Synthetic fallback failure')
        original(path,data,**kwargs)
        if Path(path).name=='terminal-safe-summary.json' and data.get('status')=='completed':raise TimeoutError('Synthetic post-commit timeout')
    monkeypatch.setattr(supervision,'atomic_json',fail_after_commit)
    report=run(tmp_path,'success')
    assert report['status']=='failed' and not report['quality_gate_passed'] and report['emergency_persisted'] is False
    assert not (tmp_path/'success/terminal-safe-summary.json').exists()
    with pytest.raises(RuntimeError):reconcile_interrupted(tmp_path/'success')


def test_monitor_hard_exit_closes_job_and_can_be_reconciled(tmp_path):
    import subprocess
    folder=tmp_path/'outer';code=('from cashreview.supervision import supervise;import sys;'
        'supervise([sys.executable,'+repr(str(ROOT/'scripts/synthetic_supervision_worker.py'))+',"timeout"],'+repr(str(folder))+',60,3,'+repr(str(ROOT))+')')
    outer=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline=time.monotonic()+5
        while not (folder/'start-gate.json').exists() and time.monotonic()<deadline:time.sleep(.02)
        owner=json.loads((folder/'monitor-owner.json').read_text());worker=json.loads((folder/'worker-identity.json').read_text())
        psutil.Process(owner['pid']).kill();outer.wait(timeout=3)
        deadline=time.monotonic()+3
        while psutil.pid_exists(worker['pid']) and time.monotonic()<deadline:time.sleep(.02)
        assert not psutil.pid_exists(worker['pid'])
        report=reconcile_interrupted(folder)
        assert report['status']=='interrupted' and report['worker_exit_code'] is None
    finally:
        from cashreview.processes import kill_tree
        kill_tree(outer.pid)
