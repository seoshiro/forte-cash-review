"""Generated local HTTP only; no external access, media, keys or model loads."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from contextlib import contextmanager
from scripts.preflight_local_access import inspect_local


@contextmanager
def server(redirect):
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.path)
            self.send_response(302 if redirect else 200)
            if redirect:self.send_header('Location','/must-never-be-fetched')
            self.end_headers()
            if not redirect:self.wfile.write(b'{"mode":"synthetic_test","private_field":"not-for-output"}')
        def log_message(self,*args):pass
    instance=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=instance.serve_forever);thread.start()
    try:yield instance.server_port,received
    finally:instance.shutdown();instance.server_close();thread.join(timeout=2)


def test_health_preflight_returns_selected_safe_fields_only():
    with server(False) as (port,received):
        value=inspect_local(port)
    assert value['health_reachable'] and value['synthetic_test_mode'] and not value['competition_release_ready']
    assert received==['/healthz'] and 'not-for-output' not in str(value) and 'private_field' not in value


def test_preflight_does_not_follow_any_http_redirect():
    # Same-origin redirect proves the handler blocks before another request.
    # A regression remains contained to loopback, without testing an external host.
    with server(True) as (port,received):
        value=inspect_local(port)
    assert not value['health_reachable'] and value['technical_error_type']=='HTTPError'
    assert received==['/healthz']
