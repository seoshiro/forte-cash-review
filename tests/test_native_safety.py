import json,time,socket
from types import SimpleNamespace
import pytest
from cashreview.offline import deny_network
from cashreview.observations import ObservationError
from cashreview.video import Sample
from gguf_candidate.engine import GGUFEngine
from PIL import Image

def test_network_exception_only_allows_exact_literal_loopback_port(monkeypatch):
    calls=[]
    for owner,name in [(socket.socket,'connect'),(socket.socket,'connect_ex'),(socket,'create_connection'),(socket,'getaddrinfo')]:
        monkeypatch.setattr(owner,name,lambda *a,**k:calls.append(a) or [])
    deny_network([18765])
    socket.create_connection(('127.0.0.1',18765))
    socket.getaddrinfo('127.0.0.1',18765)
    assert len(calls)==2
    for address in [('example.org',18765),('127.0.0.1',443),('localhost',18765),('192.168.1.1',18765)]:
        with pytest.raises(RuntimeError):socket.create_connection(address)
    with pytest.raises(RuntimeError):socket.getaddrinfo('example.org',443)
    assert len(calls)==2

def fake_engine(responses):
    from pathlib import Path
    root=Path(__file__).resolve().parents[1];engine=object.__new__(GGUFEngine)
    engine.config=json.loads((root/'config/budget-protocol.json').read_text())['candidate']
    engine.registry=json.loads((root/'config/rules.json').read_text(encoding='utf-8'));engine.telemetry=[];engine.gate_calls=[];engine.calls=[]
    def complete(*args):engine.calls.append(True);return responses.pop(0),{'generation_sec':0.}
    engine.server=SimpleNamespace(complete=complete)
    return engine

def test_native_negative_has_no_detail_and_positive_has_no_default_event():
    frames=[Sample(0.,Image.new('RGB',(64,64)))]
    negative=fake_engine(['{"visible_violation":false}'])
    assert negative.observe(frames,2,192,time.monotonic()+5)['events']==[] and len(negative.calls)==1
    positive=fake_engine(['{"visible_violation":true}','{"events":[],"limitation":""}'])
    assert positive.observe(frames,2,192,time.monotonic()+5)['events']==[] and len(positive.calls)==2

def test_native_malformed_gate_is_error_not_clear():
    engine=fake_engine(['{"visible_violation":"false"}'])
    with pytest.raises(ObservationError):engine.observe([Sample(0.,Image.new('RGB',(64,64)))],2,192,time.monotonic()+5)
