"""Bounded local preparation and experiment, logs remain in .private."""
from pathlib import Path
import sys,subprocess,os,json
root=Path(__file__).resolve().parents[1];os.chdir(root)
status={'status':'preparing'};out=root/'.private/cpu-experiment-status.json'
try:
    subprocess.run([sys.executable,'scripts/download_small.py'],check=True,timeout=1800)
    out.write_text(json.dumps({'status':'extracting_train_tune'}),encoding='utf-8')
    subprocess.run([sys.executable,'scripts/cpu_baseline.py'],check=True,timeout=5400)
    status={'status':'done'}
except Exception as e:status={'status':'failed','error_type':type(e).__name__}
out.write_text(json.dumps(status),encoding='utf-8');print(json.dumps(status));sys.exit(status['status']!='done')
