"""Bounded child lifetime and fixed-schema durable reports; never collect stdout."""
from pathlib import Path
import os,json,time,sys,subprocess,ctypes
from typing import Literal
import psutil
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .processes import kill_tree


def atomic_json(path,data,deadline=None):
    path=Path(path);temp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=True,allow_nan=False);stream.flush();os.fsync(stream.fileno())
    if deadline is not None and time.monotonic()>deadline:raise TimeoutError('Persistence deadline exceeded')
    temp.replace(path)
    if deadline is not None and time.monotonic()>deadline:raise TimeoutError('Commit deadline exceeded')


class ControlSummary(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    status:Literal['completed','failed']
    completed_cases:int=Field(ge=0)
    passed_cases:int=Field(ge=0)
    total_cases:int=Field(gt=0)
    server_exit_code:int|None=None
    failure:Literal['none','exception','server_exit']='none'

    @model_validator(mode='after')
    def counts(self):
        if not self.passed_cases<=self.completed_cases<=self.total_cases:raise ValueError('Invalid aggregate counts')
        if self.status=='completed' and self.completed_cases!=self.total_cases:raise ValueError('Incomplete aggregate')
        if self.status=='completed' and (self.failure!='none' or self.server_exit_code not in (None,0)):raise ValueError('Failed server cannot complete successfully')
        if self.failure=='server_exit' and self.server_exit_code in (None,0):raise ValueError('Server failure needs a nonzero exit')
        if self.status=='failed' and self.failure=='none':raise ValueError('Failure reason required')
        return self


class ProgressSummary(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    phase:Literal['synthetic_text','synthetic_visual','fixture']
    completed_cases:int=Field(ge=0)
    passed_cases:int=Field(ge=0)
    total_cases:int=Field(gt=0)

    @model_validator(mode='after')
    def counts(self):
        if not self.passed_cases<=self.completed_cases<=self.total_cases:raise ValueError('Invalid progress counts')
        return self


def write_progress(directory,phase,completed,passed,total):
    value=ProgressSummary(phase=phase,completed_cases=completed,passed_cases=passed,total_cases=total)
    atomic_json(Path(directory)/'progress-safe-summary.json',value.model_dump())


class OwnedWindowsJob:
    """Kill-on-close job, scoped to this worker and inherited descendants only.

    https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
    No UI restrictions, OS policy changes, credentials or persistent grants.
    Worker must wait for the start gate before spawning descendants.
    """
    def __init__(self):
        if os.name!='nt':raise RuntimeError('This supervisor requires Windows job objects')
        from ctypes import wintypes as w
        size=ctypes.c_size_t;large=ctypes.c_longlong;u64=ctypes.c_ulonglong
        class Basic(ctypes.Structure):
            _fields_=[('PerProcessUserTimeLimit',large),('PerJobUserTimeLimit',large),('LimitFlags',w.DWORD),
                ('MinimumWorkingSetSize',size),('MaximumWorkingSetSize',size),('ActiveProcessLimit',w.DWORD),
                ('Affinity',size),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,u64) for name in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
        class Extended(ctypes.Structure):
            _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',size),('JobMemoryLimit',size),('PeakProcessMemoryUsed',size),('PeakJobMemoryUsed',size)]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];self.kernel.CreateJobObjectW.restype=w.HANDLE
        self.kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];self.kernel.SetInformationJobObject.restype=w.BOOL
        self.kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];self.kernel.AssignProcessToJobObject.restype=w.BOOL
        self.kernel.CloseHandle.argtypes=[w.HANDLE];self.kernel.CloseHandle.restype=w.BOOL
        self.handle=self.kernel.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        config=Extended();config.BasicLimitInformation.LimitFlags=0x2000
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(config),ctypes.sizeof(config)):
            code=ctypes.get_last_error();self.close();raise ctypes.WinError(code)

    def assign(self,process):
        if not self.kernel.AssignProcessToJobObject(self.handle,int(process._handle)):raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            handle=self.handle;self.handle=None
            if not self.kernel.CloseHandle(handle):raise ctypes.WinError(ctypes.get_last_error())


def await_start_gate():
    """Call before heavy imports or subprocess creation in a supervised worker."""
    root=Path(os.environ['CASH_SUPERVISED_DIR']).resolve();gate=root/'start-gate.json'
    deadline=float(os.environ['CASH_SUPERVISED_DEADLINE'])
    while not gate.exists():
        if time.monotonic()>deadline:raise TimeoutError('Supervisor start gate expired')
        time.sleep(.02)
    return root,deadline


def supervise(command,run_dir,budget_sec,expected_cases,cwd):
    """One exclusive run. No model/media access is performed by this monitor."""
    if not 0<budget_sec<=1800 or type(expected_cases) is not int or expected_cases<=0:raise ValueError('Invalid supervisor budget/count')
    directory=Path(run_dir).resolve();directory.mkdir(parents=True,exist_ok=False)
    with (directory/'monitor-owner.json').open('x',encoding='ascii') as stream:
        json.dump({'pid':os.getpid(),'created':psutil.Process().create_time()},stream);stream.flush();os.fsync(stream.fileno())
    start=time.monotonic();deadline=start+budget_sec;proc=None;job=None
    report={'status':'failed','reason':'monitor_exception','worker_exit_code':None,'server_exit_code':None,
        'completed_cases':0,'passed_cases':0,'expected_cases':expected_cases,'quality_gate_passed':False,
        'budget_sec':budget_sec,'deadline_exceeded':False,'cleanup_complete':False,'worker_report_valid':False,
        'stdout_collected':False,'raw_private_content_emitted':False}
    atomic_json(directory/'status.json',{'status':'running','expected_cases':expected_cases,'budget_sec':budget_sec})
    try:
        job=OwnedWindowsJob();env=os.environ.copy()
        for key in ['CASH_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','HF_TOKEN','HUGGING_FACE_HUB_TOKEN']:env.pop(key,None)
        env.update(CASH_SUPERVISED_DIR=str(directory),CASH_SUPERVISED_DEADLINE=str(deadline))
        proc=subprocess.Popen(list(command),cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(proc)
        atomic_json(directory/'worker-identity.json',{'pid':proc.pid,'created':psutil.Process(proc.pid).create_time()})
        atomic_json(directory/'start-gate.json',{'start':True})
        while proc.poll() is None:
            if time.monotonic()>=deadline:
                report.update(reason='deadline',deadline_exceeded=True);break
            time.sleep(min(.05,max(0,deadline-time.monotonic())))
        if not report['deadline_exceeded']:
            report['worker_exit_code']=proc.returncode
            path=directory/'worker-safe-summary.json'
            if path.is_file():
                try:
                    if path.stat().st_size>4096:raise ValueError('Safe summary too large')
                    child=ControlSummary.model_validate_json(path.read_text(encoding='utf-8'))
                    if child.total_cases!=expected_cases:raise ValueError('Unexpected control count')
                    report.update(worker_report_valid=True,completed_cases=child.completed_cases,passed_cases=child.passed_cases,server_exit_code=child.server_exit_code)
                    if proc.returncode==0 and child.status=='completed':report.update(status='completed',reason='completed',quality_gate_passed=child.passed_cases==expected_cases)
                    else:report['reason']=child.failure if child.failure!='none' else 'worker_exit'
                except (OSError,ValueError,UnicodeError):report['reason']='invalid_worker_report'
            else:report['reason']='worker_exit' if proc.returncode else 'missing_worker_report'
    except BaseException as error:
        report.update(status='failed',reason='monitor_exception',quality_gate_passed=False,error_type=type(error).__name__)
    finally:
        if not report['worker_report_valid']:
            try:
                path=directory/'progress-safe-summary.json'
                if path.stat().st_size>4096:raise ValueError('Progress too large')
                progress=ProgressSummary.model_validate_json(path.read_text(encoding='utf-8'))
                if progress.total_cases!=expected_cases:raise ValueError('Wrong progress count')
                report.update(completed_cases=progress.completed_cases,passed_cases=progress.passed_cases,partial_progress_preserved=True)
            except (OSError,ValueError,UnicodeError):report['partial_progress_preserved']=False
        try:
            if job:job.close()  # Includes descendants even after worker hard exit.
            if proc:
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    kill_tree(proc.pid);proc.wait(timeout=3)
                report['worker_exit_code']=proc.returncode
            report['cleanup_complete']=True
        except BaseException as error:report.update(status='failed',quality_gate_passed=False,cleanup_complete=False,cleanup_error_type=type(error).__name__)
        report['elapsed_sec']=time.monotonic()-start
        if report['elapsed_sec']>budget_sec and report['status']=='completed':report.update(status='failed',reason='deadline',deadline_exceeded=True,quality_gate_passed=False)
        # No success publication until cleanup and the final time check complete.
        try:
            # Terminal is the authoritative commit marker. Every other required
            # write must succeed before a successful terminal can be published.
            atomic_json(directory/'status.json',{'status':report['status'],'reason':report['reason'],'authority':'terminal-safe-summary.json'},deadline=deadline if report['status']=='completed' else None)
            atomic_json(directory/'terminal-safe-summary.json',report,deadline=deadline if report['status']=='completed' else None)
        except OSError as error:
            late=isinstance(error,TimeoutError)
            report.update(status='failed',reason='deadline' if late else 'terminal_write_failed',quality_gate_passed=False,
                deadline_exceeded=report['deadline_exceeded'] or late,elapsed_sec=time.monotonic()-start)
            # A late atomic replace may already have committed a success. Revoke
            # it BEFORE any fallback write which could itself fail.
            if (directory/'terminal-safe-summary.json').exists():
                (directory/'terminal-safe-summary.json').unlink()
            try:atomic_json(directory/'emergency-safe-summary.json',report)
            except OSError:report['emergency_persisted']=False
            try:atomic_json(directory/'status.json',{'status':'failed','reason':report['reason'],'authority':'emergency-safe-summary.json'})
            except OSError:pass  # Emergency report remains authoritative.
    return report


def reconcile_interrupted(run_dir):
    """Do not invent exit codes when a monitor was forcibly terminated."""
    directory=Path(run_dir)
    if (directory/'emergency-safe-summary.json').exists():return json.loads((directory/'emergency-safe-summary.json').read_text())
    if (directory/'terminal-safe-summary.json').exists():return json.loads((directory/'terminal-safe-summary.json').read_text())
    owner=json.loads((directory/'monitor-owner.json').read_text())
    try:
        if abs(psutil.Process(owner['pid']).create_time()-owner['created'])<.01:raise RuntimeError('Run still has a live monitor')
    except psutil.NoSuchProcess:pass
    report={'status':'interrupted','reason':'monitor_disappeared','worker_exit_code':None,'server_exit_code':None,
        'quality_gate_passed':False,'raw_private_content_emitted':False}
    atomic_json(directory/'terminal-safe-summary.json',report);atomic_json(directory/'status.json',{'status':'interrupted','reason':'monitor_disappeared'})
    return report
