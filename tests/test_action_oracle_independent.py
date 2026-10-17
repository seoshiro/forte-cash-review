"""Independent geometric/input/scorer checks; generated pixels and mock HTTP only."""
from pathlib import Path
import json,re
import numpy as np
import pytest
from hybrid_candidate.action_controls import frames,text_positions,parse

CFG=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-action-probe.json').read_text())
EXPECTED={'exit':[70,110,165,220],'enter':[220,165,110,70],'stay':[70,95,125,150]}


def oracle(xs):
    # Independently specified bounds and semantics, not generator action names.
    inside=[24<x<180 for x in xs]
    if inside[0] and not inside[-1]:return 'exit'
    if not inside[0] and inside[-1]:return 'enter'
    if all(inside):return 'stay'
    return 'unknown'


@pytest.mark.parametrize('label',list(EXPECTED))
def test_text_coordinates_and_generated_red_pixels_match_independent_oracle(label):
    prompt=text_positions(label,CFG)
    xs=json.loads(re.search(r'ordered center x=(\[[^]]+\])',prompt)[1])
    assert json.loads(re.search(r'Black rectangle xyxy=(\[[^]]+\])',prompt)[1])==[24,24,180,232]
    assert CFG['geometry']['disk_radius']==9
    assert xs==EXPECTED[label] and oracle(xs)==label
    centers=[];inside=[]
    for image in frames(label,CFG):
        pixels=np.asarray(image)
        black_y,black_x=np.where(np.all(pixels<10,axis=2))
        assert [black_x.min(),black_y.min(),black_x.max(),black_y.max()]==[24,24,180,232]
        ys,red_x=np.where((pixels[:,:,0]>240)&(pixels[:,:,1]<10)&(pixels[:,:,2]<10))
        assert len(red_x)>0 and (ys.min()+ys.max())/2==120
        assert red_x.max()-red_x.min()==18 and ys.max()-ys.min()==18
        inside.append(24<red_x.min()<red_x.max()<180 and 24<ys.min()<ys.max()<232)
        centers.append((red_x.min()+red_x.max())/2)
    assert centers==EXPECTED[label] and oracle(centers)==label
    assert inside=={'exit':[True,True,True,False],'enter':[False,True,True,True],'stay':[True]*4}[label]


@pytest.mark.parametrize('label',list(EXPECTED))
@pytest.mark.parametrize('constrained',[False,True])
def test_actual_probe_http_body_contains_correct_unique_input_and_scores_response(label,constrained):
    import scripts.qwen_action_probe as probe
    supplied=[]
    class Response:
        status_code=200
        def json(self):return {'choices':[{'message':{'content':json.dumps({'action':label})},'finish_reason':'stop'}],'usage':{}}
    class Client:
        def post(self,url,**kwargs):supplied.append((url,kwargs));return Response()
    class Server:client=Client();base='http://127.0.0.1:1'
    expected_prompt=text_positions(label,CFG)
    result,finish,_=probe.request(Server(),[],expected_prompt,constrained,CFG,probe.time.monotonic()+60)
    body=supplied[0][1]['json']
    assert supplied[0][0].endswith('/v1/chat/completions')
    assert body['messages']==[{'role':'user','content':[{'type':'text','text':expected_prompt}]}]
    assert ('response_format' in body)==constrained
    assert result==oracle(EXPECTED[label]) and finish=='stop'


def test_old_parser_and_score_distinguish_perfect_permuted_and_constant_outputs():
    labels=['exit','enter','stay']
    def score(outputs):return sum(parse(json.dumps({'action':answer}))==expected for expected,answer in zip(labels,outputs))
    assert score(labels)==3
    assert score(['enter','stay','exit'])==0
    assert [score([constant]*3) for constant in labels]==[1,1,1]
