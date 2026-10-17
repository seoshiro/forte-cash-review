"""Synthetic-only headless UI review test. Hardware GPU rendering disabled."""
from pathlib import Path
import json,time,sys,httpx
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8765';out=ROOT/'.private/ui-review-qa';out.mkdir(exist_ok=True)
if httpx.get(BASE+'/healthz',trust_env=False,timeout=5).json().get('mode')!='synthetic_test':raise RuntimeError('Only synthetic server is allowed for UI capture')
checks={};errors=[];external=[];gate={'pending':True};started=time.monotonic()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu'])
        context=browser.new_context(viewport={'width':1440,'height':1100},locale='ru-RU',reduced_motion='reduce')
        def route(request):
            if not request.request.url.startswith((BASE+'/', 'blob:','data:')):external.append(request.request.resource_type);request.abort();return
            if request.request.url.endswith('/reviews') and request.request.method=='GET' and gate['pending']:
                response=request.fetch();data=response.json();data.update(ready=False,notification=None)
                for item in data.get('contexts',[]):item.update(status='pending',result='Синтетическая задержка контекста',limitation='')
                request.fulfill(response=response,json=data);return
            request.continue_()
        context.route('**/*',route);page=context.new_page();page.on('pageerror',lambda error:errors.append(type(error).__name__))
        page.goto(BASE,wait_until='networkidle');expect(page.locator('#review-notification')).to_be_hidden()
        page.locator('#access').click();page.locator('#key').fill('temporary-local-test-only');page.locator('#save-key').click()
        page.locator('#file').set_input_files(str(ROOT/'.private/synthetic/positive.mov'));page.locator('#submit').click()
        expect(page.locator('#review-notification')).to_be_hidden()
        expect(page.locator('#workspace')).to_be_visible(timeout=30000)
        expect(page.locator('.review-panel')).to_have_count(1)
        expect(page.locator('#review-notification')).to_be_hidden()
        expect(page.locator('[data-decision=confirmed]')).to_be_disabled();checks['no_notification_before_context_done']=True
        gate['pending']=False
        expect(page.locator('#review-notification')).to_be_visible(timeout=10000)
        expect(page.locator('[data-decision=confirmed]')).to_be_enabled();checks['local_notification_after_context_done']=True
        for value,label in [('confirmed','Подтверждено'),('rejected','Отклонено'),('insufficient_data','Недостаточно данных')]:
            page.locator('.review-panel textarea').fill('Искусственная тестовая заметка')
            page.locator('[data-decision='+value+']').click()
            expect(page.locator('.review-decision')).to_contain_text(label)
            expect(page.locator('.review-feedback')).to_contain_text('сохранено')
            assert page.evaluate("async()=>JSON.stringify(await request('/api/v1/jobs/'+current.job_id))===JSON.stringify(current)")
        checks['three_decisions_preserve_competition_result']=True
        page.evaluate('render()')
        expect(page.locator('.review-decision')).to_contain_text('Недостаточно данных')
        expect(page.locator('.review-panel textarea')).to_have_value('Искусственная тестовая заметка')
        page.locator('#timeline button').first.click();checks['reopened_card_fetches_saved_decision']=True
        checks['evidence_original_jpeg_decodes']=page.locator('#frames img').evaluate_all('(xs)=>xs.length>0&&xs.every(x=>x.complete&&x.naturalWidth>0)')
        checks['desktop_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/'synthetic-review-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});checks['mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/'synthetic-review-mobile.png'),full_page=True)
        page.locator('#file').set_input_files(str(ROOT/'.private/synthetic/safe.mov'))
        expect(page.locator('#workspace')).to_be_hidden();expect(page.locator('#review-notification')).to_be_hidden()
        checks['new_video_clears_old_result_and_notification']=True
        browser.close()
    report={'status':'PASS' if all(checks.values()) and not errors and not external else 'FAIL',
            'checks':checks,'page_errors':len(errors),'external_requests':len(external),
            'elapsed_sec':time.monotonic()-started,'input':'whitelisted generated synthetic MOV only',
            'hardware_gpu_rendering':False,'model_quality_tested':False}
except Exception as error:report={'status':'FAIL','error_type':type(error).__name__,'checks':checks,'model_quality_tested':False}
(out/'safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));sys.exit(report['status']!='PASS')
