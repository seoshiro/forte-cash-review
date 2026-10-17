from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from cashreview.video import Sample
from panel_candidate.engine import panel_image,PanelEngine,CANVAS,PIXEL_LIMIT
from gguf_candidate.engine import GGUFEngine

def test_panel_preserves_exact_pixels_aspect_and_each_pts():
    frames=[Sample(t,Image.new('RGB',(121,83),color)) for t,color in [(0.1,(200,0,0)),(2.3,(0,200,0)),(5.7,(0,0,200)),(9.9,(230,230,0))]]
    image,positions=panel_image(frames)
    assert image.size==CANVAS and image.width*image.height<=PIXEL_LIMIT
    assert [p['timestamp_sec'] for p in positions]==[f.sec for f in frames]
    for f,p in zip(frames,positions):
        crop=image.crop((p['x'],p['y'],p['x']+p['width'],p['y']+p['height']))
        assert crop.size==f.image.size and crop.tobytes()==f.image.tobytes()

def test_both_coarse_panels_evaluated_and_global_event_cap_preserved(monkeypatch):
    engine=object.__new__(PanelEngine);engine._initial_observation=True;engine.gate_calls=[];calls=[]
    def observed(self,frames,max_events,token_limit,deadline):
        calls.append([f.sec for f in frames]);self.gate_calls.append({'visible_violation':frames[0].sec>0})
        return {'events':[{'confidence':.9,'timestamp_sec':frames[-1].sec}],'limitation':''}
    monkeypatch.setattr(GGUFEngine,'observe',observed)
    frames=[Sample(float(i),Image.new('RGB',(64,64))) for i in range(8)]
    result=engine.observe(frames,2,192,100)
    assert calls==[[0.,1.,2.,3.],[4.,5.,6.,7.]] and engine.coarse_candidate
    assert [e['timestamp_sec'] for e in result['events']]==[3.,7.]
