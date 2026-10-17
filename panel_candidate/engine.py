from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
from cashreview.video import Sample
from gguf_candidate.engine import GGUFEngine
from gguf_candidate.runtime import NativeServer

CELL=384
HEADER=32
CANVAS=(2*CELL,2*(CELL+HEADER))
PIXEL_LIMIT=1024*32*32

def panel_image(frames):
    if not 1<=len(frames)<=4:raise ValueError('A panel requires one to four source frames')
    image=Image.new('RGB',CANVAS,(16,20,25));draw=ImageDraw.Draw(image)
    try:font=ImageFont.truetype('arial.ttf',24)
    except OSError:font=ImageFont.load_default(size=24)
    positions=[]
    for index,frame in enumerate(frames):
        if frame.image.mode!='RGB' or max(frame.image.size)>CELL:raise ValueError('Panel source must be already sampled RGB, max side384')
        x=(index%2)*CELL;y=(index//2)*(CELL+HEADER)
        draw.text((x+8,y+2),f'F{index} | {frame.sec:.3f}s',font=font,fill=(255,255,255))
        px=x+(CELL-frame.image.width)//2;py=y+HEADER+(CELL-frame.image.height)//2
        image.paste(frame.image,(px,py)) # Exact source pixels: no crop or second resize.
        positions.append({'frame_id':f'F{index}','timestamp_sec':frame.sec,'x':px,'y':py,'width':frame.image.width,'height':frame.image.height})
    if image.width*image.height>PIXEL_LIMIT:raise ValueError('Panel exceeds registered pixel budget')
    return image,positions

class PanelServer(NativeServer):
    def __init__(self,private,vision_batch_tokens=2048):
        super().__init__(private,vision_batch_tokens=vision_batch_tokens,image_max_tokens=1024);self.panels=[]
    def complete(self,frames,prompt,schema,max_tokens,deadline):
        image,positions=panel_image(frames);self.panels.append(positions)
        text,metric=super().complete([Sample(frames[0].sec,image)],prompt,schema,max_tokens,deadline)
        metric.update(logical_frames=len(frames),encoded_images=1,panel_width=image.width,panel_height=image.height,
                      panel_source_resized=False,panel_source_cropped=False,panel_pts=[f.sec for f in frames])
        return text,metric

class PanelEngine(GGUFEngine):
    def __init__(self,private):
        super().__init__(private,vision_batch_tokens=2048);self._initial_observation=True;self.coarse_candidate=False
    def make_server(self,private,vision_batch_tokens):return PanelServer(private,vision_batch_tokens)
    def observe(self,frames,max_events,token_limit,deadline):
        initial=self._initial_observation;self._initial_observation=False;start=len(self.gate_calls);observations=[]
        for offset in range(0,len(frames),4):
            observations.append(super().observe(frames[offset:offset+4],max_events,token_limit,deadline))
        if initial:self.coarse_candidate=any(x['visible_violation'] for x in self.gate_calls[start:])
        events=[event for observation in observations for event in observation['events']]
        # Preserve the previous global cap and its selection policy; both panels
        # are evaluated, even when the first one already proposed an event.
        events=sorted(events,key=lambda e:(-e['confidence'],e['timestamp_sec']))[:max_events]
        return {'events':events,'limitation':'Оценена только выборка кадров.'}
    def analyze(self,path,job_id,private,strategy=None):
        self._initial_observation=True;self.coarse_candidate=False;self.server.panels=[]
        result=super().analyze(path,job_id,private,strategy)
        p=Path(private);m=json.loads((p/'metrics.json').read_text());m.update(engine_family='native_panel4',coarse_gate_candidate=self.coarse_candidate,
            panel_count=len(self.server.panels),panel_source_resized=False,panel_pixel_limit=PIXEL_LIMIT)
        (p/'metrics.json').write_text(json.dumps(m,indent=2))
        (p/'panel-pts.private.json').write_text(json.dumps(self.server.panels,indent=2))
        return result
