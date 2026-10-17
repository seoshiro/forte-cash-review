"""Synthetic primitive extraction; no bank rules or direct action-label prompt."""
from io import BytesIO
import base64
from hybrid_candidate.decomposition import body, KEYS
from hybrid_candidate.action_controls import frames


def visual_body(action, cfg):
    request = body(action, cfg['text_cells'][0], cfg)
    content = []
    for index, image in enumerate(frames(action, cfg)):
        buffer = BytesIO()
        image.save(buffer, 'JPEG', quality=cfg['inference']['jpeg_quality'])
        content.extend([
            {'type': 'text', 'text': 'F' + str(index) + ':'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')}},
        ])
    content.append({'type': 'text', 'text':
        'Observe the red disk and black outlined rectangle in four ordered images F0,F1,F2,F3. '
        'Fully inside means the entire red disk is within the outlined rectangle. '
        'Return only a JSON object with exactly three Boolean fields: first_inside for F0, '
        'last_inside for F3, all_inside for whether the disk is fully inside in every supplied image. No explanation.'})
    request['messages'][0]['content'] = content
    return request


def derive_state(facts):
    if not isinstance(facts, dict) or set(facts) != set(KEYS) or any(type(facts[k]) is not bool for k in KEYS):
        return None
    first, last, every = (facts[k] for k in KEYS)
    if every:
        return 'stay' if first and last else None
    if first and not last:
        return 'exit'
    if not first and last:
        return 'enter'
    return None
