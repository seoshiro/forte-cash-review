"""Tiny fault fixtures, no models, data, networking or private response reads."""
from pathlib import Path
import os,sys,time,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import await_start_gate,atomic_json,write_progress


def main():
    directory,deadline=await_start_gate();mode=sys.argv[1]
    write_progress(directory,'fixture',1,1,3)
    report={'status':'completed','completed_cases':3,'passed_cases':3,'total_cases':3,'failure':'none','server_exit_code':None}
    if mode=='hard_exit':os._exit(7)
    if mode=='timeout':time.sleep(60)
    if mode=='exception':raise RuntimeError('Synthetic raw exception must never leave the worker')
    if mode=='control_failure':report['passed_cases']=2
    if mode=='inconsistent_success':report.update(failure='server_exit',server_exit_code=9)
    if mode=='no_report':return
    if mode=='invalid_report':
        atomic_json(directory/'worker-safe-summary.json',{'secret_or_description':'Synthetic forbidden extra field'});return
    if mode in ('server_exit','orphan'):
        code='import os;os._exit(9)' if mode=='server_exit' else 'import time;time.sleep(60)'
        child=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        atomic_json(directory/'synthetic-child-identity.json',{'pid':child.pid})
        if mode=='orphan':os._exit(7)
        report.update(status='failed',completed_cases=1,passed_cases=1,failure='server_exit',server_exit_code=child.wait())
    atomic_json(directory/'worker-safe-summary.json',report)
    if report['status']=='failed':sys.exit(1)


if __name__=='__main__':main()
