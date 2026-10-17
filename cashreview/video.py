from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import av
import numpy as np
from PIL import Image


@dataclass
class Sample:
    sec: float
    image: Image.Image


def inspect(path: Path, decode: bool = False) -> dict:
    with av.open(str(path)) as c:
        s = c.streams.video[0]
        info = {"duration_sec": float(c.duration / av.time_base) if c.duration else float(s.duration * s.time_base),
                "width": s.width, "height": s.height, "codec": s.codec_context.name,
                "fps": float(s.average_rate) if s.average_rate else None,
                "time_base": str(s.time_base), "rotation": s.metadata.get("rotate", "0"),
                "audio_ignored": True, "decode_ok": None}
        if decode:
            count, last, monotonic, rot = 0, None, True, set()
            first = None
            for f in c.decode(s):
                if f.pts is None:
                    raise ValueError("Missing PTS")
                t = float(f.pts * f.time_base)
                first = t if first is None else first
                monotonic &= last is None or t >= last
                last, count = t, count + 1
                rot.add(float(getattr(f, "rotation", 0)))
            info.update(decode_ok=count > 0, decoded_frames=count, pts_monotonic=monotonic,
                        first_pts_sec=first, last_pts_sec=last, frame_rotations=sorted(rot))
        return info


def sample(path: Path, times: list[float], max_side: int = 448) -> list[Sample]:
    """Sequential PTS-aware decoding; no FPS arithmetic and no audio decoding."""
    targets = sorted(set(max(0, float(t)) for t in times))
    result, i = [], 0
    with av.open(str(path)) as c:
        s = c.streams.video[0]
        origin = float(s.start_time * s.time_base) if s.start_time is not None else 0.0
        rotation = float(s.metadata.get("rotate", 0))
        for f in c.decode(s):
            if f.pts is None:
                continue
            t = float(f.pts * f.time_base) - origin
            if i >= len(targets):
                break
            if t + 0.0001 < targets[i]:
                continue
            img = f.to_image().convert("RGB")
            # PyAV 14 exposes display matrix rotation on the frame.
            rot = float(getattr(f, "rotation", 0)) or rotation
            if rot:
                img = img.rotate(rot, expand=True)
            img.thumbnail((max_side, max_side))
            result.append(Sample(max(0.0, t), img))
            while i < len(targets) and targets[i] <= t + 0.0001:
                i += 1
    if not result:
        raise ValueError("No decodable video frames")
    return result


def dhash(img: Image.Image) -> int:
    a = np.asarray(img.convert("L").resize((9, 8)))
    v = (a[:, 1:] > a[:, :-1]).flatten()
    return sum(int(b) << i for i, b in enumerate(v))
