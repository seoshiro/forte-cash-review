"""Entirely generated figures; no source videos, identities or bank rules."""
import json
from PIL import Image, ImageDraw

STATES = ['EXIT', 'ENTER', 'STAY', 'UNKNOWN']


def positions(state, cfg):
    g = cfg['synthetic']
    xs = g['stay_x'] if state == 'STAY' else g['exit_x']
    if state == 'ENTER':
        xs = list(reversed(xs))
    if state not in STATES[:3]:
        raise ValueError('Generated state only')
    return xs


def frames(state, layout, cfg):
    g = cfg['synthetic']
    side = g['side']
    left, top, right, bottom = g['region_xyxy']
    if layout not in [0, 1]:
        raise ValueError('Frozen layouts only')
    if layout:
        left, right = side-right, side-left
    images = []
    for raw_x in positions(state, cfg):
        x = side-raw_x if layout else raw_x
        y = g['figure_y']
        image = Image.new('RGB', (side, side), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((left, top, right, bottom), fill=(235, 245, 235), outline='black', width=5)
        draw.text((left+12, top+12), 'WORK ZONE', fill='black')
        center = (left+right)//2
        draw.rectangle((center-60, 320, center+60, 345), fill=(150, 110, 70))
        draw.ellipse((x-9, y-35, x+9, y-17), fill='red')
        draw.rectangle((x-9, y-16, x+9, y+10), fill='red')
        draw.line((x-9, y-12, x-20, y+8), fill='red', width=6)
        draw.line((x+9, y-12, x+20, y+8), fill='red', width=6)
        draw.line((x-5, y+9, x-14, y+35), fill='red', width=7)
        draw.line((x+5, y+9, x+14, y+35), fill='red', width=7)
        images.append(image)
    return images


def prompt(layout):
    definitions = [
        'EXIT: the red figure starts fully inside the black outlined work zone and ends fully outside it.',
        'ENTER: the red figure starts fully outside the work zone and ends fully inside it.',
        'STAY: the red figure remains fully inside the work zone in all supplied frames.',
        'UNKNOWN: images are missing or the movement cannot be determined.',
    ]
    if layout:
        definitions = definitions[1:] + definitions[:1]
    return ('Inspect the four ordered images F0,F1,F2,F3. Classify the visible red figure relative to the black outlined work zone. '
            + ' '.join(definitions) + ' Use the supplied image order. Return only JSON {"state":"VALUE"} with one of EXIT, ENTER, STAY, UNKNOWN. No explanation.')


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse(text, pilot=False, count=8):
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4].strip()
    try:
        value = json.loads(text, object_pairs_hook=no_duplicates)
    except (ValueError, TypeError):
        return None
    if not pilot:
        return value if isinstance(value, dict) and set(value) == {'state'} and value['state'] in STATES else None
    if not isinstance(value, dict) or set(value) != {'departed', 'frame_index'} or value['departed'] not in ['YES', 'NO', 'UNKNOWN']:
        return None
    index = value['frame_index']
    if value['departed'] == 'YES':
        return value if type(index) is int and 0 <= index < count else None
    return value if index is None else None


def pilot_prompt():
    return ('Inspect the supplied frames in time order. Is there clearly visible movement of a person initially located at a workstation '
            'away from that workstation, while another person remains visible near it? YES only when this movement is supported by the supplied images. '
            'NO means no such movement is visible in these sampled images. UNKNOWN means the view or sequence is insufficient to judge. '
            'Do not infer identity, cashier role, whether service is finished, intent, rules or a legal violation. '
            'Return only JSON with exactly two fields: departed (YES, NO or UNKNOWN) and frame_index '
            '(the earliest supplied zero-based frame showing the departure for YES; null for NO or UNKNOWN). No explanation.')


def pilot_selection(rows):
    if any(row.get('split') != 'train' for row in rows):
        raise ValueError('Pilot selection accepts TRAIN metadata only')
    selected = []
    used = set()
    for target in [0, 1]:
        candidates = sorted((r for r in rows if r['target'] == target), key=lambda r: r['sha256'])
        subset = []
        for row in candidates:
            if row['group'] in used:
                continue
            subset.append(row)
            used.add(row['group'])
            if len(subset) == 3:
                break
        if len(subset) != 3:
            raise ValueError('Insufficient unique TRAIN groups for the frozen pilot')
        selected.extend(subset)
    return sorted(selected, key=lambda r: r['sha256'])
