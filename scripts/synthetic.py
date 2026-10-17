"""Generate abstract safe test media locally, no human or banking footage."""
from pathlib import Path
import av, numpy as np


def generate(path:Path,positive=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    with av.open(str(path),'w',format='mov',options={'movflags':'faststart'}) as c:
        s=c.add_stream('libx264',rate=30);s.width=320;s.height=240;s.pix_fmt='yuv420p';s.options={'crf':'25','preset':'ultrafast'}
        for i in range(90):
            a=np.zeros((240,320,3),dtype=np.uint8);a[:]=[31,57,45];x=20+i*2
            a[90:140,x:min(x+40,320)]=[220,170,75] if positive else [150,185,140]
            f=av.VideoFrame.from_ndarray(a,format='rgb24')
            for p in s.encode(f):c.mux(p)
        for p in s.encode():c.mux(p)
    return path

if __name__=='__main__':
    generate(Path('.private/synthetic/safe.mov'))
    print('Safe abstract MOV generated locally')
