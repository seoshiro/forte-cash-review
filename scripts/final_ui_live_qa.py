"""Live final browser-to-model flow with generated media. No captures, logs or keys out."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json
from cashreview.technical_diagnostics import safe_exception
OUT=ROOT/'.private/final-ui-live-qa'


def main():
    from playwright.sync_api import sync_playwright,expect
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session
    from cashreview.schemas import Done
    from scripts.synthetic import generate
    OUT.mkdir(exist_ok=False);record=validate_session(load(ROOT/'.private/final-access/credentials.dpapi'))
    endpoint=json.loads((ROOT/'.private/final-access/endpoint.json').read_text());assert endpoint['active_expected'];base=endpoint['url'];movie=generate(OUT/'generated.mov')
    errors=[];external=[];started=time.monotonic();phase='browser_start'
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu','--disable-background-networking'])
            context=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU')
            def route(item):
                if item.request.url.startswith((base+'/', 'blob:','data:')):item.continue_()
                else:external.append(item.request.resource_type);item.abort()
            context.route('**/*',route);page=context.new_page();page.on('pageerror',lambda error:errors.append(type(error).__name__))
            for asset in ['style.css','research.css','research.js']:
                actual=context.request.get(base+'/static/'+asset);assert actual.status==200
                assert hashlib.sha256(actual.body()).digest()==hashlib.sha256((ROOT/'static'/asset).read_bytes()).digest()
            phase='real_final_ui';page.goto(base+'/',wait_until='networkidle',timeout=30000)
            assert page.evaluate('getComputedStyle(document.body).margin')=='0px'
            expect(page.locator('#empty')).to_be_visible();expect(page.locator('.research-banner')).to_contain_text('Экспериментальный API доступен')
            page.locator('#access').click();page.locator('#key').fill(record['jury']);page.locator('#save-key').click();assert page.locator('#key').input_value()==''
            assert page.evaluate('localStorage.length===0 && sessionStorage.length===0')
            page.locator('#file').set_input_files(str(movie));upload_started=time.monotonic()
            with page.expect_response(lambda r:r.request.method=='POST' and r.url==base+'/api/experimental/xclip/analyze',timeout=30000) as response:page.locator('#submit').click()
            assert response.value.status==200;job=response.value.json()['job_id']
            expect(page.locator('#workspace')).to_be_visible(timeout=120000);ui_wall=time.monotonic()-upload_started
            assert ui_wall<300
            phase='jury_api_equivalence'
            result=context.request.get(base+'/api/v1/jobs/'+job,headers={'X-API-Key':record['jury']});assert result.status==200;Done.model_validate(result.json())
            assert context.request.get(base+'/api/v1/jobs/'+job,headers={'X-API-Key':record['operator']}).status==404
            control=subprocess.run([str(ROOT/'.venv-patched/Scripts/python.exe'),str(ROOT/'scripts/final_access.py'),'restart-origin'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60)
            assert control.returncode==0 and json.loads(control.stdout)['same_public_url'] is True
            restored=context.request.get(base+'/api/v1/jobs/'+job,headers={'X-API-Key':record['jury']});assert restored.status==200 and restored.json()==result.json()
            assert page.evaluate('localStorage.length===0 && sessionStorage.length===0')
            desktop=page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.set_viewport_size({'width':390,'height':844})
            mobile=page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert desktop and mobile and not errors and not external
            browser.close()
        report={'status':'PASS','scope':'Actual final UI to actual frozen local baseline, generated MOV and locally loaded jury key only; no model quality',
            'jury_ui_jobs_completed':1,'upload_click_to_rendered_result_sec':ui_wall,'total_browser_check_sec':time.monotonic()-started,
            'same_job_valid_in_official_v1_shape':True,'other_operator_cannot_read_jury_job':True,'key_input_cleared':True,'key_not_in_web_storage':True,
            'all_ui_assets_match_local_source':True,'global_styles_applied':True,
            'completed_jury_job_survived_current_origin_restart':True,'canonical_public_url_unchanged':True,
            'desktop_mobile_no_overflow':True,'js_errors':len(errors),'external_page_requests':len(external),'captures_created':0,
            'bank_data_used':False,'predictions_frames_or_keys_emitted':False}
        atomic_json(OUT/'safe-summary.json',report);print(json.dumps(report))
    except Exception as error:
        atomic_json(OUT/'failure-safe-summary.json',{'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT),'private_content_emitted':False});raise


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
