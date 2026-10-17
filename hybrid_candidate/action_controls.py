"""Synthetic geometric action controls; no bank scenes or answer text in images."""
from PIL import Image,ImageDraw
import json


def frames(action,cfg):
    g=cfg['geometry'];positions=g['stay_x'] if action=='stay' else g['exit_x']
    if action=='enter':positions=list(reversed(positions))
    if action not in ['exit','enter','stay']:raise ValueError('Only generated action controls permitted')
    result=[]
    for x in positions:
        image=Image.new('RGB',(g['frame_side'],g['frame_side']),'white');draw=ImageDraw.Draw(image)
        draw.rectangle(tuple(g['boundary_xyxy']),outline='black',width=4);r=g['disk_radius'];y=g['y']
        draw.ellipse((x-r,y-r,x+r,y+r),fill='red');result.append(image)
    return result


def montage(images):
    side=images[0].width;result=Image.new('RGB',(side*2,side*2),'white')
    draw=ImageDraw.Draw(result)
    for index,image in enumerate(images):
        x=(index%2)*side;y=(index//2)*side;result.paste(image,(x,y));draw.text((x+5,y+5),'F'+str(index),fill='black')
    return result


def short_prompt():
    return ('Classify red disk motion in four ordered frames F0,F1,F2,F3. A black rectangle marks the region. '
        'exit: disk starts inside and ends outside; enter: starts outside and ends inside; stay: remains inside; unknown: unclear. '
        'If one image contains four panels, read them in row-major order F0,F1,F2,F3. '
        'Return only JSON {"action":"exit|enter|stay|unknown"}, with exactly one allowed action value.')


def long_prompt():
    return (short_prompt()+' Observe the first and last supplied positions and compare them with the black boundary. '
        'Use all four frames in order. A displacement that stays inside does not count as exit. '
        'Crossing from outside to inside is enter, even if the disk ends near the boundary. '
        'Crossing from inside to outside is exit. The object is the red disk, and the region is the outlined rectangle. '
        'Do not infer identities, intention or hidden state. Do not classify the movement of a panel label. '
        'The same definitions apply to separate images and a four-panel image. '
        'Keep the response to the single action field. Use unknown only when the supplied geometry cannot establish the motion.')


def text_positions(action,cfg):
    g=cfg['geometry'];positions=g['stay_x'] if action=='stay' else g['exit_x']
    if action=='enter':positions=list(reversed(positions))
    return 'Fictional coordinate control. Black rectangle xyxy='+str(g['boundary_xyxy'])+'; red disk center y='+str(g['y'])+'; ordered center x='+str(positions)+'. '+short_prompt()


def schema():
    return {'type':'object','additionalProperties':False,'properties':{'action':{'type':'string','enum':['exit','enter','stay','unknown']}},'required':['action']}


def parse(value):
    try:result=json.loads(value)
    except (ValueError,TypeError):return None
    if not isinstance(result,dict) or set(result)!={'action'} or result['action'] not in ['exit','enter','stay','unknown']:return None
    return result['action']
