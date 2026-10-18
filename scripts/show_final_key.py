"""Explicitly user-opened local jury handoff. Never screen-capture this window."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    import tkinter as tk
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session
    directory=ROOT/'.private/final-access';record=validate_session(load(directory/'credentials.dpapi'));endpoint=json.loads((directory/'endpoint.json').read_text())
    if not endpoint['active_expected'] or (directory/'revoke-jury.request').exists():raise RuntimeError('Jury access inactive')
    window=tk.Tk();window.title('TerenOi — temporary jury access')
    tk.Label(window,text='EXPERIMENTAL PROTOTYPE: types and rules unverified.\nPrivate key shown locally only. Do not screenshot this window.',padx=20,pady=15).pack()
    text=tk.Text(window,width=100,height=12);text.insert('1.0','Canonical UI/API: '+endpoint['url']+'\n\nX-API-Key (jury): '+record['jury']+'\n\nExpires: 2026-10-18 18:59:59 UTC / 23:59:59 Astana\n\nPOST /api/v1/analyze (file)\nGET /api/v1/jobs/{job_id}\n\nPrivate repository access must be granted by its owner separately.');text.configure(state='disabled');text.pack(padx=20,pady=10)
    tk.Button(window,text='Close',command=window.destroy).pack(pady=15);window.mainloop()


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
