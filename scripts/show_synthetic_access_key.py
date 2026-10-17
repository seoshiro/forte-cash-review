"""User-invoked local-only handoff window. Never run under cloud UI capture."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from cashreview.local_secrets import load
    import tkinter as tk
    directory=ROOT/'.private/access-synthetic';keys=load(directory/'credentials.dpapi')
    if keys['purpose']!='synthetic-infrastructure-only':raise ValueError('Wrong purpose')
    endpoint=json.loads((directory/'endpoint.json').read_text())
    root=tk.Tk();root.title('Контур / TerenOi — только искусственное инфраструктурное демо')
    tk.Label(root,text='Это временный ключ синтетического демо, не ключ жюри.\nНе отправляйте банковские видео. Не делайте скриншот этого окна.',padx=20,pady=15).pack()
    text=tk.Text(root,width=90,height=7);text.insert('1.0','URL: '+endpoint['url']+'\n\nX-API-Key: '+keys['primary']+'\n\nТуннель может уже быть остановлен; статус смотрите в локальном отчёте.');text.configure(state='disabled');text.pack(padx=20,pady=10)
    tk.Button(root,text='Закрыть',command=root.destroy).pack(pady=15);root.mainloop()


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
