"""Private human annotation viewer; only binds loopback. NEVER capture this UI with cloud tools."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,secrets,urllib.parse
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'.private/dataset';token=secrets.token_urlsafe(24)
rows=[r for r in json.loads((DATA/'manifest.json').read_text(encoding='utf-8')) if r['split'] in ['train','tune'] and not r['error']]
HTML='''<!doctype html><html lang="ru"><meta charset="utf-8"><title>ЛОКАЛЬНО — не отправлять кадры в облако</title><style>body{font:16px Segoe UI;background:#edf1e8;max-width:1000px;margin:32px auto;color:#1d392b}video{width:100%;max-height:520px;background:#13281c}button,select,input,textarea{font:inherit;padding:9px;margin:6px}textarea{width:90%}strong{color:#933}label{display:block}</style><h1>Локальный просмотр и аннотации</h1><strong>Реальные данные: запрещены cloud screenshots / vision / пересылка содержимого.</strong><p>Holdout недоступен. Автоматические результаты не изменяются. Экспорт сохраняйте только в .private/annotations.</p><select id="pick"></select><p id="meta"></p><video id="v" controls muted></video><p><button id="label-time">Перейти к официальному времени</button></p><label>Категория события <input id="category"></label><label>Наблюдение (только видимое)<textarea id="obs"></textarea></label><label>Правило и условия применимости<textarea id="rule"></textarea></label><label>Ограничения<textarea id="limits"></textarea></label><label>Группа съёмки / дубль (без идентификации лиц)<input id="group"></label><label>Релевантность кадра <select id="relevance"><option value="unreviewed">Не проверено</option><option value="yes">Да</option><option value="no">Нет</option></select></label><button id="save">Сохранить локальную аннотацию</button><p id="status"></p><script>let rows=[],i=0;const $=id=>document.getElementById(id);fetch('rows?token=TOKEN').then(r=>r.json()).then(r=>{rows=r;r.forEach((x,j)=>{let o=document.createElement('option');o.value=j;o.textContent=`${j+1} / ${x.split}`;$('pick').append(o)});load()});function load(){i=+$('pick').value;let r=rows[i];$('v').src=`media/${i}?token=TOKEN`;$('meta').textContent=`${r.split}; официальная метка ${r.target}; время ${r.label_sec??'отсутствует'}; ${r.duration_sec.toFixed(2)} с`;$('group').value=r.group;for(let id of ['category','obs','rule','limits'])$(id).value=''}$('pick').onchange=load;$('label-time').onclick=()=>{if(rows[i].label_sec!==null)$('v').currentTime=rows[i].label_sec};$('save').onclick=async()=>{let a={index:i,timestamp_sec:$('v').currentTime,category:$('category').value,observation:$('obs').value,rule:$('rule').value,limitations:$('limits').value,scene_group:$('group').value,frame_relevance:$('relevance').value};let r=await fetch('annotation?token=TOKEN',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(a)});$('status').textContent=r.ok?'Сохранено только локально':'Ошибка записи'};</script></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        u=urllib.parse.urlsplit(self.path)
        if urllib.parse.parse_qs(u.query).get('token')!=[token]:self.send_error(403);return
        if u.path=='/':data=HTML.replace('TOKEN',token).encode('utf-8');mime='text/html; charset=utf-8'
        elif u.path=='/rows':data=json.dumps([{k:r[k] for k in ['target','label_sec','duration_sec','split','group']} for r in rows]).encode('utf-8');mime='application/json'
        elif u.path.startswith('/media/'):
            try:r=rows[int(u.path.split('/')[-1])];p=Path(r['path'])
            except (IndexError,ValueError):self.send_error(404);return
            size=p.stat().st_size;start,end=0,size-1;status=200
            if self.headers.get('Range'):
                import re
                m=re.fullmatch(r'bytes=(\d+)-(\d*)',self.headers['Range'])
                if not m:self.send_error(416);return
                start=int(m[1]);end=min(size-1,int(m[2]) if m[2] else size-1);status=206
                if not 0<=start<=end<size:self.send_error(416);return
            self.send_response(status);self.send_header('Content-Type','video/quicktime');self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(end-start+1))
            if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            try:
                with p.open('rb') as f:
                    f.seek(start);remaining=end-start+1
                    while remaining:
                        chunk=f.read(min(1024*1024,remaining));self.wfile.write(chunk);remaining-=len(chunk)
            except (BrokenPipeError,ConnectionResetError):pass
            return
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        u=urllib.parse.urlsplit(self.path)
        if u.path!='/annotation' or urllib.parse.parse_qs(u.query).get('token')!=[token]:self.send_error(403);return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n>20000:raise ValueError()
            a=json.loads(self.rfile.read(n));r=rows[int(a.pop('index'))];a['source_sha256']=r['sha256'];a['split']=r['split'];out=ROOT/'.private/annotations';out.mkdir(exist_ok=True)
            with (out/'human.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(a,ensure_ascii=False)+'\n')
        except (ValueError,KeyError,IndexError):self.send_error(400);return
        self.send_response(204);self.end_headers()

if __name__=='__main__':
    link=f'http://127.0.0.1:8766/?token={token}';(ROOT/'.private/local-review-url.txt').write_text(link,encoding='ascii')
    print('Private viewer ready on loopback. URL is saved in .private/local-review-url.txt. Do not open it with cloud browser tools.')
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
