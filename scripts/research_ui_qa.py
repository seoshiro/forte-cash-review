"""Synthetic-only browser UI fixture, all HTTP intercepted before any network.

This tests rendering and client states, not model quality or real API transport.
It never opens real service jobs, bank media, annotations or model output.
"""
from pathlib import Path
from io import BytesIO
import base64, json, sys, time
from PIL import Image, ImageDraw
import av
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.private/research-ui-qa'
BASE = 'http://127.0.0.1:18769'
KEY = 'temporary-ui-fixture-only'


def image_at(index):
    image = Image.new('RGB', (320, 180), '#183d35')
    draw = ImageDraw.Draw(image)
    draw.rectangle((30 + index * 8, 60, 90 + index * 8, 120), fill='#e7b658')
    draw.text((20, 20), 'SYNTHETIC UI FIXTURE', fill='white')
    return image


def fixtures():
    OUT.mkdir(exist_ok=True)
    movie = OUT / 'generated-shapes.mov'
    with av.open(str(movie), 'w') as container:
        stream = container.add_stream('libx264', rate=10)
        stream.width = 320; stream.height = 180; stream.pix_fmt = 'yuv420p'
        for i in range(40):
            frame = av.VideoFrame.from_image(image_at(i // 10))
            for packet in stream.encode(frame): container.mux(packet)
        for packet in stream.encode(): container.mux(packet)
    frames = []
    for sec in (1., 2., 3.):
        buffer = BytesIO(); image_at(int(sec)).save(buffer, 'JPEG')
        frames.append({'timestamp_sec': sec, 'image_base64': base64.b64encode(buffer.getvalue()).decode('ascii')})
    return movie, frames


def main():
    movie, frames = fixtures(); start = time.monotonic()
    checks = {}; errors = []; blocked = []; state = {'case': 'positive', 'sequence': 0, 'polls': 0}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--disable-gpu'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='ru-RU', reduced_motion='reduce')
        def route(r):
            request = r.request; url = request.url
            if url.startswith(('blob:', 'data:')):
                r.continue_(); return
            if not url.startswith(BASE + '/'):
                blocked.append(request.resource_type); r.abort(); return
            path = url.removeprefix(BASE)
            if path == '/':
                r.fulfill(path=str(ROOT / 'static/research.html'), content_type='text/html; charset=utf-8'); return
            if path in ('/static/style.css', '/static/research.css', '/static/research.js'):
                r.fulfill(path=str(ROOT / path.lstrip('/')), content_type='text/javascript' if path.endswith('.js') else 'text/css'); return
            if path == '/favicon.ico': r.fulfill(status=204); return
            if path.startswith('/api/experimental/xclip/'):
                if request.headers.get('x-api-key') != KEY:
                    r.fulfill(status=401, json={'detail': 'Synthetic unauthorized'}); return
                if request.method == 'POST' and path.endswith('/analyze'):
                    state['sequence'] += 1; state['polls'] = 0
                    state['job'] = f"{state['sequence']:032x}"
                    r.fulfill(json={'job_id': state['job']}); return
                if request.method == 'GET' and path.endswith('/' + state['job']):
                    state['polls'] += 1
                    result = {'job_id': state['job'], 'status': 'processing'}
                    if state['polls'] > 1:
                        positive = state['case'] in ('positive', 'malformed')
                        result.update(status='done', mode='xclip_experimental', binary_decision='violation' if positive else 'no_violation',
                                      decision_margin=.2 if positive else -.2, threshold=0.0, event_type_status='unverified',
                                      rule_application_status='not_assessed', release_eligible=False, duration_sec=4., elapsed_engine_sec=.1,
                                      candidate_timecode_sec=2. if positive else None, candidate_frames=frames if positive else [],
                                      limitation='Binary research candidate only; type, physical explanation and legal rule are unverified. No complete multi-event detection claim.')
                        if state['case'] == 'failed': result = {'job_id': state['job'], 'status': 'failed'}
                        if state['case'] == 'malformed': result['event_type_status'] = 'verified'
                        if state['case'] == 'extra_field': result['extra'] = True
                        if state['case'] == 'bad_elapsed': result['elapsed_engine_sec'] = -1
                        if state['case'] == 'bad_limitation': result['limitation'] = 'unsupported assertion'
                    r.fulfill(json=result); return
            blocked.append('unexpected_fixture_path'); r.abort()
        context.route('**/*', route)
        page = context.new_page(); page.on('pageerror', lambda e: errors.append(type(e).__name__))
        page.goto(BASE + '/', wait_until='networkidle')
        page.locator('.research-banner strong').evaluate('(e)=>e.textContent="СИНТЕТИЧЕСКАЯ UI-ПРОВЕРКА · качество модели не тестируется"')
        expect(page.locator('#empty')).to_be_visible(); checks['empty'] = True
        def key(value):
            page.locator('#access').click(); page.locator('#key').fill(value); page.locator('#save-key').click()
            assert page.locator('#key').input_value() == ''
        def upload():
            page.locator('#file').set_input_files(str(movie)); page.locator('#submit').click()
        key(KEY); upload(); expect(page.locator('#workspace')).to_be_visible(timeout=15000)
        expect(page.locator('#verdict')).to_have_text('Есть кандидат для ручной проверки')
        expect(page.locator('#frames img')).to_have_count(3)
        checks['positive_and_images'] = page.locator('#frames img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth===320)')
        page.wait_for_function('document.getElementById("video").readyState>=1')
        page.locator('#timeline button').click()
        page.wait_for_function('Math.abs(document.getElementById("video").currentTime-2)<.1')
        checks['timestamp_navigation'] = True
        page.locator('#before').click(); page.wait_for_function('document.getElementById("video").currentTime<.1')
        page.locator('#context').click(); page.wait_for_function('document.getElementById("video").currentTime>.2')
        page.locator('#video').evaluate('(v)=>v.pause()'); checks['synthetic_video_context'] = True
        checks['desktop_no_overflow'] = page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT / 'synthetic-research-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        checks['mobile_no_overflow'] = page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT / 'synthetic-research-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 1000})
        state['case'] = 'negative'; upload(); expect(page.locator('#verdict')).to_have_text('Кандидат не найден', timeout=15000)
        expect(page.locator('#frames img')).to_have_count(0); expect(page.locator('#timeline button')).to_have_count(0)
        expect(page.locator('#result-note')).to_contain_text('не подтверждает отсутствие нарушения')
        checks['negative_clears_evidence_and_preserves_uncertainty'] = True
        for case in ('failed', 'malformed', 'extra_field', 'bad_elapsed', 'bad_limitation'):
            state['case'] = case; upload(); expect(page.locator('#error')).to_be_visible(timeout=15000)
            expect(page.locator('#workspace')).to_be_hidden(); expect(page.locator('#frames img')).to_have_count(0)
            checks[case + '_fails_without_verdict'] = True
        key('wrong-temporary-fixture'); upload(); expect(page.locator('#error')).to_contain_text('ключ', timeout=15000)
        checks['wrong_key'] = True
        checks['no_browser_storage_or_cookies'] = page.evaluate('localStorage.length===0&&sessionStorage.length===0') and not context.cookies()
        browser.close()
    result = {'status': 'PASS' if all(checks.values()) and not errors and not blocked else 'FAIL',
              'checks': checks, 'page_errors': len(errors), 'unexpected_or_external_requests': len(blocked),
              'http_fixture_intercepted_no_server': True, 'synthetic_media_generated_in_this_run': True,
              'bank_data_or_real_results_opened': False, 'model_quality_tested': False, 'actual_api_transport_tested': False,
              'elapsed_sec': time.monotonic() - start}
    (OUT / 'safe-summary.json').write_text(json.dumps(result, indent=2)); print(json.dumps(result))
    return result['status'] != 'PASS'


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'technical_error_type': type(error).__name__, 'raw_content_emitted': False}))
        sys.exit(1)
