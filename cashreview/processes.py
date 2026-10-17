"""Terminate an owned subprocess tree, including Windows venv redirector children."""
import psutil
from pathlib import Path


def kill_tree(pid):
    try:root=psutil.Process(pid);targets=root.children(recursive=True)+[root]
    except psutil.NoSuchProcess:return True
    clean=True
    for p in targets:
        try:p.kill()
        except psutil.NoSuchProcess:pass
        except psutil.AccessDenied:clean=False
    _,alive=psutil.wait_procs(targets,timeout=2)
    return clean and not alive


def reap_orphan(folder,project_root,meta):
    """Match the opaque job argument and cwd before touching a recorded PID."""
    try:pid=int((folder/'worker.pid').read_text());worker=psutil.Process(pid)
    except (FileNotFoundError,psutil.NoSuchProcess):return True
    except (OSError,ValueError,psutil.Error):return False
    try:
        args=worker.cmdline()
        if Path(worker.cwd()).resolve()!=project_root.resolve() or 'cashreview.worker' not in args or Path(args[-1]).resolve()!=folder.resolve():return True
        owner=meta.get('server_pid')
        if owner:
            try:
                server=psutil.Process(owner)
                if abs(server.create_time()-meta.get('server_created',0))<.01:return False
            except psutil.NoSuchProcess:pass
        return kill_tree(pid)
    except (psutil.Error,OSError,ValueError,TypeError):return False
