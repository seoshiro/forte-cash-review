"""Label-free pixel observations. Arrays and media remain local."""
from pathlib import Path
import time
import numpy as np
from PIL import ImageOps


def longest_fraction(values):
    longest=current=0
    for value in values:
        current=current+1 if value else 0;longest=max(longest,current)
    return longest/max(1,len(values))


def summarize_frames(images,times,cfg):
    if len(images)<3 or len(images)!=len(times):raise ValueError('Insufficient PTS frames')
    settings=cfg['features'];size=settings['analysis_size'];grid=settings['grid_size']
    if size%grid:raise ValueError('Grid dimensions are incompatible')
    # Preserve aspect ratio with fixed black padding; do not crop scene content.
    from PIL import Image
    masks=[np.asarray(ImageOps.pad(Image.new('L',image.size,255),(size,size),color=0))>0 for image in images]
    if any(not np.array_equal(mask,masks[0]) for mask in masks):raise ValueError('Frame geometry changed')
    mask=masks[0]
    frames=np.array([np.asarray(ImageOps.pad(image.convert('L'),(size,size)),dtype=np.float32)/255 for image in images])
    if not np.isfinite(frames).all() or not np.all(np.diff(times)>0):raise ValueError('Invalid frame/PTS arrays')
    signed=np.diff(frames,axis=0);signed-=np.median(signed[:,mask],axis=1)[:,None,None]
    signed[:,~mask]=0
    motion=np.abs(signed)
    state=(np.abs(frames[1:]-np.median(frames,axis=0))>settings['state_threshold']).astype(np.float32)
    state[:,~mask]=0
    cell=size//grid
    valid_counts=mask.reshape(grid,cell,grid,cell).sum(axis=(1,3)).reshape(grid*grid)
    def pool(array):return array.reshape(len(array),grid,cell,grid,cell).sum(axis=(2,4)).reshape(len(array),grid*grid)/np.maximum(valid_counts,1)
    m=pool(motion);s=pool(state);windows=np.concatenate([m,s],axis=1)
    energy=m.mean(1);active=energy>settings['active_motion_threshold']
    correlation=float(np.corrcoef(energy[:-1],energy[1:])[0,1]) if len(energy)>2 and min(np.std(energy[:-1]),np.std(energy[1:]))>1e-8 else 0.
    concentration=m.max(1)/np.maximum(m.sum(1),1e-8)
    extra=[float(active.mean()),longest_fraction(active),longest_fraction(~active),correlation,
        float(concentration.mean()),float(np.quantile(concentration,.9))]
    bag=np.concatenate([windows.mean(0),windows.std(0),np.quantile(windows,.9,axis=0),extra]).astype(np.float32)
    if windows.shape[1]!=18 or bag.shape!=(60,) or not np.isfinite(bag).all():raise ValueError('Invalid fixed feature schema')
    return {'window_times':np.asarray(times[1:]),'windows':windows,'bag':bag,'motion_candidate_sec':float(times[1+int(np.argmax(energy))])}


def extract(path,cfg):
    from cashreview.video import validate_input,sample
    start=time.monotonic();info=validate_input(Path(path));settings=cfg['features']
    grid=np.arange(0,max(.01,info['duration_sec']-.1),settings['frame_step_sec']).tolist()
    frames=sample(Path(path),grid,max_side=settings['decode_max_side'])
    result=summarize_frames([frame.image for frame in frames],[frame.sec for frame in frames],cfg)
    result['elapsed_sec']=time.monotonic()-start;result['frames']=len(frames)
    return result
