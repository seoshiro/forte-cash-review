"""Delete only opaque temporary uploads in this profile's stopped, locked store."""
from pathlib import Path
import json
from filelock import FileLock
from cashreview.storage import job_folder_safe,remove_job


def purge_final_uploads(project_root):
    root=Path(project_root).resolve();private=root/'.private';store=private/'final-service';jobs=store/'jobs'
    if not store.exists():return {'removed':0,'blocked':0,'store_present':False}
    if store.is_symlink() or (hasattr(store,'is_junction') and store.is_junction()) or store.resolve()!=private.resolve()/'final-service':raise ValueError('Unexpected upload store')
    if not store.resolve().is_relative_to(root) or jobs.resolve()!=store.resolve()/'jobs':raise ValueError('Upload cleanup escaped project')
    if json.loads((store/'.api-store-contract.json').read_text())!={'contract':'xclip-experimental-v1'}:raise ValueError('Unexpected upload contract')
    result={'removed':0,'blocked':0,'store_present':True}
    # The running native API holds this lock. Never remove an active job store.
    with FileLock(str(store/'.api-service.lock'),timeout=0):
        for folder in list(jobs.iterdir()):
            if not job_folder_safe(folder,jobs):result['blocked']+=1;continue
            if folder.resolve().parent!=jobs.resolve() or not folder.resolve().is_relative_to(store.resolve()):raise ValueError('Unexpected cleanup target')
            remove_job(folder,jobs);result['removed']+=1
    return result
