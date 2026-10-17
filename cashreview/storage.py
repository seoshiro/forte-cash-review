"""Opaque API job storage only. Never traverses dataset or manual-review paths."""
from pathlib import Path
import json,math,re,shutil

def job_folder_safe(folder:Path,jobs:Path):
    try:
        if not re.fullmatch(r'[0-9a-f]{32}',folder.name) or not folder.is_dir() or folder.is_symlink():return False
        if hasattr(folder,'is_junction') and folder.is_junction():return False
        return folder.resolve()==jobs.resolve()/folder.name
    except OSError:return False

def raw_meta(folder):
    try:
        value=json.loads((folder/'meta.json').read_text(encoding='utf-8'))
        return value if type(value) is dict else {}
    except (OSError,ValueError,UnicodeError):return {}

def valid_meta(folder):
    value=raw_meta(folder);created=value.get('created');owner=value.get('owner')
    if type(owner) is not str or not re.fullmatch(r'[0-9a-f]{64}',owner):return None
    if type(created) not in (float,int):return None
    try:
        if not math.isfinite(created) or created<=0:return None
    except OverflowError:return None
    return value

def remove_job(folder,jobs):
    if not job_folder_safe(folder,jobs):raise ValueError('Unsafe API cleanup target')
    shutil.rmtree(folder.resolve())

def cleanup_expired(jobs,active,now,ttl=3600):
    report={'removed':0,'errors':0}
    try:folders=list(jobs.iterdir())
    except OSError:return {'removed':0,'errors':1}
    for folder in folders:
        if folder.name in active or not job_folder_safe(folder,jobs):continue
        try:
            meta=valid_meta(folder);created=meta['created'] if meta else folder.stat().st_mtime
            if now-created>ttl:remove_job(folder,jobs);report['removed']+=1
        except (OSError,ValueError,TypeError):report['errors']+=1
    return report
