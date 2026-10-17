import json,time
from types import SimpleNamespace
from PIL import Image
from cashreview.video import Sample
from gguf_candidate.runtime import NativeServer

def test_native_schema_uses_actual_b11712_nested_envelope():
    captured={}
    class Client:
        def post(self,url,**kwargs):
            captured.update(kwargs['json'])
            return SimpleNamespace(status_code=200,json=lambda:{'choices':[{'message':{'content':'{"present":false}'}}],'usage':{}})
    server=object.__new__(NativeServer);server.client=Client();server.base='http://127.0.0.1:12345'
    schema={'type':'object','properties':{'present':{'type':'boolean'}},'required':['present'],'additionalProperties':False}
    server.complete([Sample(0.,Image.new('RGB',(16,16)))],'Synthetic request',schema,32,time.monotonic()+10)
    assert captured['response_format']=={'type':'json_schema','json_schema':{'schema':schema}}
    assert 'schema' not in captured['response_format']
