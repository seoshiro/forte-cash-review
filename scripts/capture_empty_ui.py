"""Actual existing UI screenshot; new browser context, no files/keys/jobs."""
from pathlib import Path
import json,hashlib,time,sys
import httpx
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8765'
OUT=ROOT/'.private/share-ui';OUT.mkdir(exist_ok=True)


def main():
    if httpx.get(BASE+'/healthz',trust_env=False,timeout=3).json().get('mode')!='synthetic_test':raise RuntimeError('Synthetic server required')
    blocked=[];requested=[];errors=[];start=time.monotonic()
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu'])
        context=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU',reduced_motion='reduce')
        def route(r):
            url=r.request.url;path=url.removeprefix(BASE)
            allowed=(r.request.method=='GET' and url.startswith(BASE+'/') and (path in ('/','/healthz','/favicon.ico') or path.startswith('/static/')))
            if allowed:requested.append(path);r.continue_()
            else:blocked.append(r.request.resource_type);r.abort()
        context.route('**/*',route);page=context.new_page();page.on('pageerror',lambda e:errors.append(type(e).__name__))
        page.goto(BASE+'/',wait_until='networkidle');expect(page.locator('#empty')).to_be_visible()
        expect(page.locator('#workspace')).to_be_hidden();expect(page.locator('#statusbox')).to_be_hidden()
        expect(page.locator('#error')).to_be_hidden();expect(page.locator('#key-dialog')).to_be_hidden()
        expect(page.locator('#review-notification')).to_be_hidden()
        assert page.locator('#file').evaluate('(e)=>e.files.length')==0
        assert page.locator('#key').input_value()==''
        assert page.locator('#frames img').count()==0 and page.locator('#events').inner_text()==''
        assert page.locator('#timeline button').count()==0
        assert page.locator('video').evaluate_all('(xs)=>xs.every(x=>!x.getAttribute("src")&&!x.getAttribute("poster")&&!x.querySelector("source"))')
        assert page.locator('img,canvas').count()==0
        assert page.evaluate('localStorage.length===0&&sessionStorage.length===0')
        assert not context.cookies() and not blocked and not errors
        screenshot=OUT/'forte-current-upload-ui.png';page.screenshot(path=str(screenshot),full_page=True)
        browser.close()
    result={'status':'PASS','capture':'Actual current localhost UI, fresh empty state; no design changes',
        'no_media_loaded':True,'no_file_selected':True,'no_key_entered':True,'no_jobs_requested':True,'no_cookies_or_storage':True,
        'bank_data_or_results_opened':False,'gpu_rendering':False,'external_requests':0,'blocked_requests':len(blocked),
        'allowed_requests':len(requested),'page_errors':len(errors),'elapsed_sec':time.monotonic()-start,
        'png_bytes':screenshot.stat().st_size,'png_sha256':hashlib.sha256(screenshot.read_bytes()).hexdigest()}
    (OUT/'safe-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'failed','technical_error_type':type(e).__name__,'private_content_emitted':False}),flush=True);sys.exit(1)
