from pathlib import Path
import argparse,json,hashlib,secrets,html,os,socket,sys
ROOT=Path(__file__).resolve().parents[1]

def load_selected():
    registration=ROOT/'.private/oracle-diagnostic-r1/registration.json'
    selection=json.loads(registration.read_text())['source_sha256']
    manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
    index={r['sha256']:r for r in manifest if r['split']=='train' and not r['error']}
    rows=[index[key] for key in selection]
    if len(rows)!=8 or len(set(selection))!=8:raise RuntimeError('Frozen eight-case TRAIN selection required')
    for row in rows:
        path=Path(row['path']).resolve()
        if not path.is_relative_to(Path(r'C:\Users\gokusen\Downloads\open\videos').resolve()):raise RuntimeError('Unexpected source root')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:raise RuntimeError('Source changed; review not started')
    return rows,hashlib.sha256(registration.read_bytes()).hexdigest()

def main():
    import uvicorn,httpx
    from .app import create_review_app
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8767);args=parser.parse_args()
    if not 1024<=args.port<=65535:raise ValueError('Invalid local port')
    private=ROOT/'.private/manual-review';private.mkdir(parents=True,exist_ok=True)
    ready=private/'ready.json';shortcut=private/'Open-TRAIN-review.html';internet_shortcut=private/'Open-TRAIN-review.url';base=f'http://127.0.0.1:{args.port}'
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',args.port));free=True
        except OSError:free=False
    if not free:
        try:
            known=json.loads(ready.read_text());health=httpx.get(base+'/healthz',timeout=2,trust_env=False).json()
            if health['review_app']=='train_manual_v1' and health['mode']=='private_train_review' and health['instance']==known['instance'] and shortcut.exists():
                print('Private TRAIN form is already running. Open .private/manual-review/Open-TRAIN-review.url yourself.');return
        except (OSError,ValueError,KeyError,httpx.HTTPError):pass
        raise RuntimeError('Local port occupied; existing process was not changed')
    rows,registration_sha=load_selected();token=secrets.token_urlsafe(24)
    app=create_review_app(rows,private,token,registration_sha)
    url=base+'/?token='+token
    internet_shortcut.write_text('[InternetShortcut]\nURL='+url+'\n',encoding='utf-8')
    shortcut.write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Локальная TRAIN-проверка</title><h1>Локальная проверка восьми TRAIN-роликов</h1><p>Не отправляйте кадры и описания в чат. Видео запускается только вашей кнопкой.</p><p><a href="'+html.escape(url,quote=True)+'">Открыть приватную форму</a></p><p>Если форма недоступна, запустите Start-TRAIN-review.cmd из папки проекта. После проверки в чат достаточно написать «готово».</p></html>',encoding='utf-8')
    ready.write_text(json.dumps({'port':args.port,'pid':os.getpid(),'instance':hashlib.sha256(token.encode('ascii')).hexdigest()[:16],'selected_cases':8,'media_autoplay':False,'registration_sha256':registration_sha},indent=2))
    print('Private TRAIN form ready. Open .private/manual-review/Open-TRAIN-review.url yourself. No browser or media is started automatically.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False,log_level='warning')

if __name__=='__main__':main()
