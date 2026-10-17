"""Isolated headless Edge QA. Hard guard: only whitelisted synthetic server.

Never point this script at real datasets/results or the local annotation viewer.
"""
from pathlib import Path
import json,time,sys
import httpx
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8765'
out=ROOT/'.private/ui-qa';out.mkdir(parents=True,exist_ok=True)
health=httpx.get(BASE+'/healthz',timeout=5,trust_env=False).json()
if health.get('mode')!='synthetic_test':raise RuntimeError('UI screenshots forbidden outside synthetic mode')
files=[ROOT/'.private/synthetic/positive.mov',ROOT/'.private/synthetic/safe.mov']
if not all(f.exists() for f in files):raise RuntimeError('Synthetic fixtures missing')
errors=[];external=[];checks={};start=time.monotonic()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU',reduced_motion='reduce')
        def route(r):
            if r.request.url.startswith((BASE+'/', 'blob:','data:')):r.continue_()
            else:external.append(r.request.resource_type);r.abort()
        context.route('**/*',route)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE,wait_until='networkidle');expect(page.locator('#empty')).to_be_visible()
        checks['empty_state']=True
        page.screenshot(path=str(out/'synthetic-empty-desktop.png'),full_page=True)
        page.locator('#access').click();page.locator('#key').fill('temporary-local-test-only');page.locator('#save-key').click()
        page.locator('#file').set_input_files(str(files[0]));page.locator('#submit').click()
        expect(page.locator('#workspace')).to_be_visible(timeout=30000)
        expect(page.locator('#frames img')).to_have_count(3)
        page.locator('#video').evaluate('(v)=>v.play()')
        page.wait_for_function('document.getElementById("video").currentTime>0.2',timeout=10000)
        page.locator('#video').evaluate('(v)=>v.pause()')
        checks['synthetic_h264_playback']=True
        checks['positive_flow']=True
        checks['evidence_decodes']=page.locator('#frames img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>0)')
        checks['desktop_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#timeline button').first.click();checks['timeline_navigation']=True
        page.screenshot(path=str(out/'synthetic-positive-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});checks['mobile_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/'synthetic-positive-mobile.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':1000})
        page.locator('#file').set_input_files(str(files[1]));page.locator('#submit').click()
        expect(page.locator('#workspace')).to_be_visible(timeout=30000)
        expect(page.locator('#verdict')).to_have_text('Нарушение не обнаружено')
        expect(page.locator('#frames img')).to_have_count(0);expect(page.locator('#timeline button')).to_have_count(0)
        checks['negative_flow_clears_evidence']=True
        page.locator('#file').set_input_files({'name':'corrupt.mov','mimeType':'video/quicktime','buffer':b'corrupt synthetic test'})
        page.locator('#submit').click();expect(page.locator('#error')).to_be_visible(timeout=30000);expect(page.locator('#workspace')).to_be_hidden()
        checks['technical_failure_not_verdict']=True
        page.locator('#access').click();page.locator('#key').fill('wrong-temporary-test-only');page.locator('#save-key').click()
        page.locator('#file').set_input_files(str(files[1]));page.locator('#submit').click();expect(page.locator('#error')).to_contain_text('ключ')
        checks['wrong_key_error']=True
        browser.close()
    passed=all(checks.values()) and not errors and not external
    result={'status':'PASS' if passed else 'FAIL','browser':'isolated headless Microsoft Edge via Playwright','mode':'synthetic_test','checks':checks,'page_errors':len(errors),'external_requests':len(external),'elapsed_sec':time.monotonic()-start,'screenshots':'synthetic only, local .private/ui-qa','detector_quality_tested':False}
except Exception as e:
    result={'status':'FAIL','error_type':type(e).__name__,'checks':checks,'detector_quality_tested':False}
    errors.append(type(e).__name__)
(out/'private-errors.json').write_text(json.dumps(errors),encoding='utf-8');(out/'safe-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));sys.exit(result['status']!='PASS')
