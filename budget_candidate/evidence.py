"""One PTS-aware decode pass; unchanged JPEG source pixels and timestamps."""
from bisect import bisect_left
from cashreview.video import sample

def event_frames(path,timestamps,duration):
    targets=[[max(0,t-1),t,min(duration-.1,t+1)] for t in timestamps]
    if not targets:return []
    frames=sample(path,[t for event in targets for t in event],960)
    seconds=[f.sec for f in frames];result=[]
    for event in targets:
        selected={}
        for timestamp in sorted(set(event)):
            index=bisect_left(seconds,timestamp-.0001)
            if index>=len(frames):raise ValueError('Evidence target has no decodable PTS')
            frame=frames[index];selected[frame.sec]=frame
        result.append([selected[t] for t in sorted(selected)])
    return result
