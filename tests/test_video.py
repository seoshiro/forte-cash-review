from pathlib import Path
import sys,struct
import pytest,av
from threading import Thread
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.manifest import seconds,normalize
from scripts.synthetic import generate
from cashreview.video import sample,inspect
from PIL import Image,ImageDraw
from fractions import Fraction


def test_label_normalization():
    assert normalize('Х-SYNTHETIC-9007')==normalize('X-SYNTHETIC-9007.mov')
    assert seconds('2минута 13 секунда')==133
    assert seconds(None) is None
    assert seconds('02:13')==133


def test_pts_sampling(tmp_path):
    p=generate(tmp_path/'safe.mov');info=inspect(p,decode=True)
    assert info['decoded_frames']==90 and info['pts_monotonic']
    fs=sample(p,[.11,1.37,2.8])
    assert len(fs)==3
    for f,t in zip(fs,[.11,1.37,2.8]):assert 0<=f.sec-t<.034


def test_renamed_network_playlist_cannot_contact_native_ffmpeg_http(tmp_path):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            requests.append(self.path);self.send_response(404);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        path=tmp_path/'renamed.mov'
        path.write_text(f'ffconcat version 1.0\nfile http://127.0.0.1:{server.server_port}/safe.mov\n',encoding='ascii')
        with pytest.raises(av.error.InvalidDataError):inspect(path)
        assert requests==[]
    finally:server.shutdown();server.server_close();thread.join()


def test_mov_display_matrix_rotation_applies_to_evidence(tmp_path):
    path=tmp_path/'quadrants.mov';im=Image.new('RGB',(320,240));draw=ImageDraw.Draw(im)
    for box,color in [((0,0,159,119),'red'),((160,0,319,119),'green'),((0,120,159,239),'blue'),((160,120,319,239),'yellow')]:draw.rectangle(box,fill=color)
    with av.open(str(path),'w',format='mov') as container:
        stream=container.add_stream('libx264',rate=30);stream.width=320;stream.height=240;stream.pix_fmt='yuv420p'
        for _ in range(30):
            for packet in stream.encode(av.VideoFrame.from_image(im)):container.mux(packet)
        for packet in stream.encode():container.mux(packet)
    data=bytearray(path.read_bytes());index=data.index(b'tkhd');assert data[index+4]==0
    # Version-zero QuickTime track header matrix: one clockwise quarter turn.
    data[index+44:index+80]=struct.pack('>9i',0,65536,0,-65536,0,0,0,0,1073741824)
    rotated=tmp_path/'rotated.mov';rotated.write_bytes(data)
    frame=sample(rotated,[.5])[0]
    assert frame.image.size==(240,320)
    assert frame.image.getpixel((20,20))[2]>200  # source bottom-left blue
    assert frame.image.getpixel((220,20))[0]>200 # source top-left red


def test_variable_pts_are_used_instead_of_average_fps(tmp_path):
    path=tmp_path/'variable.mov'
    with av.open(str(path),'w',format='mov') as c:
        stream=c.add_stream('libx264',rate=30,options={'bf':'0'});stream.width=160;stream.height=96;stream.pix_fmt='yuv420p'
        stream.time_base=Fraction(1,30);stream.codec_context.time_base=Fraction(1,30)
        for pts in [0,1,3,10,20,40]:
            f=av.VideoFrame.from_image(Image.new('RGB',(160,96),(30,60,40)));f.pts=pts;f.time_base=Fraction(1,30)
            for packet in stream.encode(f):c.mux(packet)
        for packet in stream.encode():c.mux(packet)
    actual=[f.sec for f in sample(path,[.05,.3,.8])]
    assert actual==pytest.approx([.1,10/30,40/30],abs=.001)
