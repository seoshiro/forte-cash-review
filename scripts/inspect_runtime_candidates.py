"""Read-only official runtime metadata; does not download/install candidate wheels."""
from pathlib import Path
import httpx,re,json,urllib.parse
import ctypes
ROOT=Path(__file__).resolve().parents[1]
record={'installed_environment_changed':False,'wheels_downloaded':False,'channels':{}}
with httpx.Client(timeout=40,follow_redirects=True,trust_env=False) as c:
    for channel in ['cu128','cu130']:
        html=c.get(f'https://download.pytorch.org/whl/{channel}/torch/').raise_for_status().text
        links=re.findall(r'href="([^"]+)"',html)
        record['channels'][channel]=[urllib.parse.urljoin(f'https://download.pytorch.org/whl/{channel}/torch/',x.replace('&amp;','&')) for x in links if 'cp312-cp312-win_amd64.whl' in x and ('torch-2.13.' in x or 'torch-2.14.' in x)]
    data=c.get('https://pypi.org/pypi/torchvision/json').raise_for_status().json()
    record['vision_latest']={'version':data['info']['version'],'requires':[x for x in data['info']['requires_dist'] if x.startswith('torch')]}
    for version in ['2.13.0','2.14.1']:
        d=c.get(f'https://pypi.org/pypi/torch/{version}/json').raise_for_status().json()
        record['torch_'+version]={'listed_vulnerability_ids':[v['id'] for v in d.get('vulnerabilities',[])]}
    html=c.get('https://download.pytorch.org/whl/cu130/torchvision/').raise_for_status().text
    vision=[urllib.parse.urljoin('https://download.pytorch.org/whl/cu130/torchvision/',x) for x in re.findall(r'href="([^"]+)"',html) if 'torchvision-0.29.1%2Bcu130-cp312-cp312-win_amd64.whl' in x]
    selected=[x for x in record['channels']['cu130'] if 'torch-2.14.1%2B' in x]+vision
    if len(selected)!=2:raise RuntimeError('Compatible official candidate wheels not unique')
    artifacts=[]
    for value in selected:
        url,fragment=urllib.parse.urldefrag(value);digest=urllib.parse.parse_qs(fragment)['sha256'][0]
        h=c.head(url).raise_for_status();size=int(h.headers['content-length'])
        artifacts.append({'url':url,'sha256':digest,'bytes':size,'filename':urllib.parse.unquote(url.split('/')[-1])})
    record['selected_artifacts']=artifacts
driver=ctypes.WinDLL('nvcuda.dll');version=ctypes.c_int();code=driver.cuDriverGetVersion(ctypes.byref(version))
record['driver_api']={'return_code':code,'version':version.value,'supports_cuda130_by_api_version':code==0 and version.value>=13000}
(ROOT/'.private/updated-cuda-candidates.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
