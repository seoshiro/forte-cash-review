"""Only generated media may reach this headless browser. Never use real selection."""
from pathlib import Path
import sys,json,time,socket,subprocess,uuid,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    import httpx
    from playwright.sync_api import sync_playwright,expect
    from cashreview.processes import kill_tree
    out=ROOT/'.private/train-review-synthetic-qa';out.mkdir(exist_ok=True)
    run=out/('run-'+uuid.uuid4().hex);run.mkdir()
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    base=f'http://127.0.0.1:{port}';token='temporary-synthetic-review-only'
    with (run/'server.stdout.log').open('w') as stdout,(run/'server.stderr.log').open('w') as stderr:
        server=subprocess.Popen([str(ROOT/'.venv-patched/Scripts/python.exe'),str(ROOT/'scripts/synthetic_review_server.py'),'--port',str(port),'--out',str(run)],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    checks={};errors=[];external=[];tick=time.monotonic()
    try:
        deadline=time.monotonic()+15
        while True:
            try:health=httpx.get(base+'/healthz',trust_env=False,timeout=2).json();break
            except (httpx.HTTPError,ValueError):
                if time.monotonic()>deadline or server.poll() is not None:raise TimeoutError('Synthetic server not ready')
                time.sleep(.05)
        if health.get('mode')!='synthetic_review_test':raise RuntimeError('Browser forbidden for real review mode')
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu'])
            context=browser.new_context(viewport={'width':1280,'height':1000},locale='ru-RU')
            def route(r):
                if r.request.url.startswith(base+'/'):r.continue_()
                else:external.append(r.request.resource_type);r.abort()
            context.route('**/*',route);page=context.new_page();page.on('pageerror',lambda e:errors.append(type(e).__name__))
            page.goto(base+'/?token='+token,wait_until='networkidle');expect(page.locator('#cases button')).to_have_count(8)
            page.wait_for_function('()=>document.getElementById("video").readyState>=1',timeout=15000)
            checks['no_autoplay']=page.locator('#video').evaluate('(v)=>v.paused&&!v.autoplay')
            checks['negative_time_stays_missing']=page.locator('#seek').is_disabled() and page.locator('#reviewed_time_sec').input_value()==''
            page.locator('#cases button').nth(1).click();page.wait_for_function('()=>document.getElementById("video").readyState>=1')
            page.locator('#seek').click();page.wait_for_function('()=>Math.abs(document.getElementById("video").currentTime-1)<0.1')
            checks['official_time_seek_without_play']=page.locator('#video').evaluate('(v)=>v.paused')
            page.locator('#video').evaluate('(v)=>v.play()');page.wait_for_function('()=>document.getElementById("video").currentTime>1.2');page.locator('#video').evaluate('(v)=>v.pause()')
            checks['generated_mov_playback']=True
            page.locator('#cases button').first.click()
            for i in range(8):
                page.locator('#label_matches').select_option('unclear');page.locator('#rule_or_type').fill('Synthetic QA only')
                page.locator('#visibility').select_option('insufficient');page.locator('#comment').fill('Generated geometry, not banking data')
                page.locator('#save').click()
                expect(page.locator('#progress')).to_contain_text(f'Сохранено {i+1} из 8')
            checks['eight_answers_saved_locally']=True
            page.reload(wait_until='networkidle');expect(page.locator('#progress')).to_contain_text('Сохранено 8 из 8')
            checks['reload_preserves_answers']=page.locator('#rule_or_type').input_value()=='Synthetic QA only'
            checks['desktop_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.set_viewport_size({'width':390,'height':844});checks['mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            browser.close()
        report={'status':'PASS' if all(checks.values()) and not errors and not external else 'FAIL','checks':checks,'page_errors':len(errors),'external_requests':len(external),
                'elapsed_sec':time.monotonic()-tick,'source':'generated geometry MOV only','bank_data_read':False,'screenshots_taken':False,'backend_runtime':'venv-patched','browser_driver_runtime':'existing UI-test environment; no models imported'}
    except Exception as error:
        report={'status':'FAIL','error_type':type(error).__name__,'checks':checks,'bank_data_read':False,'screenshots_taken':False,
                'synthetic_error':str(error)[:500],'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)]}
    finally:kill_tree(server.pid)
    (run/'safe-summary.json').write_text(json.dumps(report,indent=2));(out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));return report['status']!='PASS'
if __name__=='__main__':sys.exit(main())
