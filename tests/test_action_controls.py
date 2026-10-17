from pathlib import Path
import json
from hybrid_candidate.action_controls import frames,montage,parse,short_prompt,long_prompt
CFG=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-action-probe.json').read_text())


def test_enter_is_exact_reverse_exit_without_answer_overlays():
    forward=frames('exit',CFG);reverse=frames('enter',CFG)
    assert [im.tobytes() for im in reverse]==[im.tobytes() for im in reversed(forward)]
    assert all(im.size==(256,256) for im in forward)
    packed=montage(forward)
    assert packed.size==(512,512) and packed.width*packed.height==sum(im.width*im.height for im in forward)


def test_strict_action_parser_never_relabels_format_error_as_unknown():
    assert parse('{"action":"exit"}')=='exit' and parse('{"action":"unknown"}')=='unknown'
    assert parse('exit') is None and parse('{"action":"exit","reason":"extra"}') is None
    assert parse('{"action":"invalid"}') is None
    assert short_prompt() in long_prompt()


def test_phase_timeout_cannot_accept_a_late_response(monkeypatch):
    import pytest
    import scripts.qwen_action_probe as probe
    class Response:
        status_code=200
        def json(self):return {'choices':[{'message':{'content':'{"action":"exit"}'},'finish_reason':'stop'}],'usage':{}}
    class Client:
        def post(self,*args,**kwargs):return Response()
    class Server:client=Client();base='http://127.0.0.1:1'
    clock=iter([0.,0.,21.]);monkeypatch.setattr(probe.time,'monotonic',lambda:next(clock))
    with pytest.raises(TimeoutError,match='Late native response'):probe.request(Server(),[],short_prompt(),True,CFG,100.)
