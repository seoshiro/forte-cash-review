from types import SimpleNamespace
from io import BytesIO
from PIL import Image
import pytest
from scripts.synthetic import generate
from cashreview.video import sample
from budget_candidate.evidence import event_frames
from budget_candidate.runtime_guard import disable_artifact_loaders

def encoded(frame):
    buffer=BytesIO();frame.image.save(buffer,'JPEG',quality=85);return buffer.getvalue()

def test_batch_evidence_preserves_pts_and_jpeg_for_overlapping_edge_events(tmp_path):
    path=generate(tmp_path/'safe.mov',positive=True);duration=3.0;times=[0.,.01,1.0,1.02,2.85]
    batches=event_frames(path,times,duration)
    for timestamp,batch in zip(times,batches):
        original=sample(path,[max(0,timestamp-1),timestamp,min(duration-.1,timestamp+1)],960)
        assert [f.sec for f in batch]==[f.sec for f in original]
        assert [encoded(f) for f in batch]==[encoded(f) for f in original]
    assert event_frames(path,[],duration)==[]

def test_executable_artifact_loader_guard_rejects_before_loading():
    touched=[]
    def unsafe(*args,**kwargs):touched.append(True)
    fake=SimpleNamespace(load=unsafe,serialization=SimpleNamespace(load=unsafe),
                         jit=SimpleNamespace(load=unsafe),export=SimpleNamespace(load=unsafe))
    report=disable_artifact_loaders(fake)
    assert len(report['blocked_loaders'])==4
    for function in [fake.load,fake.serialization.load,fake.jit.load,fake.export.load]:
        with pytest.raises(RuntimeError,match='disabled'):function('untrusted.pt2')
    assert touched==[]
