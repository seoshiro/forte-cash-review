"""User-invoked local handoff window. Never open through cloud screen capture."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    import tkinter as tk
    from cashreview.local_secrets import load
    directory=ROOT/'.private/research-access-live';keys=load(directory/'credentials.dpapi');endpoint=json.loads((directory/'endpoint.json').read_text())
    if keys['purpose']!='research-prototype-only' or time.time()>=keys['expires_unix'] or not endpoint['active_expected']:raise RuntimeError('Research access expired')
    window=tk.Tk();window.title('TerenOi — private research access')
    tk.Label(window,text='Исследовательский прототип: типы событий и правила не подтверждены.\nКлюч показывается только локально. Не делитесь скриншотом этого окна.',padx=20,pady=15).pack()
    partial_path=ROOT/'.private/partial-contract-access/endpoint.json';extra=''
    if partial_path.exists():
        partial=json.loads(partial_path.read_text())
        if partial.get('active_expected'):extra='\nPartial API v1 (experimental, types/rules unverified): '+partial['url']
    text=tk.Text(window,width=95,height=10);text.insert('1.0','Research UI: '+endpoint['url']+extra+'\n\nX-API-Key: '+keys['primary']+'\n\nExpires: '+time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(keys['expires_unix'])));text.configure(state='disabled');text.pack(padx=20,pady=10)
    tk.Button(window,text='Закрыть',command=window.destroy).pack(pady=15);window.mainloop()


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
