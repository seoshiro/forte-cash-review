from pathlib import Path
import sys,json,base64
from io import BytesIO
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cashreview.observations import parse_observation
from scripts.qa_model_api import verify_frames
from scripts.synthetic import generate
from cashreview.video import sample


def event():return {'rule_id':'R22','timestamp_sec':3.0,'confidence':.9,'all_conditions_visible':True,'observation':'Искусственный пример схемы.','limitation':''}


def test_empty_and_valid_model_json():
    assert parse_observation('{"events":[]}',{'R22'},0,10)['events']==[]
    assert parse_observation('```json\n'+json.dumps({'events':[event()]})+'\n```',{'R22'},0,10)['events'][0]['confidence']==.9


@pytest.mark.parametrize('change',[{'confidence':float('nan')},{'confidence':2.0},{'all_conditions_visible':'true'},{'timestamp_sec':99.0},{'rule_id':'INVENTED'}])
def test_invalid_outputs_are_technical_errors_with_safe_messages(change):
    e=event();e.update(change)
    with pytest.raises(ValueError) as caught:parse_observation(json.dumps({'events':[e]}),{'R22'},0,10)
    assert e['observation'] not in str(caught.value)


def test_evidence_matches_timestamped_source_pixels(tmp_path):
    path=generate(tmp_path/'safe.mov',positive=True);f=sample(path,[1.0],960)[0]
    b=BytesIO();f.image.save(b,'JPEG',quality=85)
    result={'violations':[{'timecode_sec':round(f.sec,3),'evidence_frames':[{'timestamp_sec':round(f.sec,3),'image_base64':base64.b64encode(b.getvalue()).decode()}]}]}
    assert verify_frames(path,result)==1
    b=BytesIO();Image.new('RGB',(320,240),'blue').save(b,'JPEG',quality=85)
    result['violations'][0]['evidence_frames'][0]['image_base64']=base64.b64encode(b.getvalue()).decode()
    with pytest.raises(ValueError,match='pixels differ'):verify_frames(path,result)
