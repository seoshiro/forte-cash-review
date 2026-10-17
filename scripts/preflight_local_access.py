"""Read-only loopback health/installation inventory. Never create external access."""
from pathlib import Path
import argparse,json,shutil,urllib.request
ROOT=Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return None


def inspect_local(port):
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid local port')
    result={'scope':'loopback health only','public_access_test':False,'tunnel_started':False,'firewall_changed':False,
        'permanent_key_created':False,'remote_or_push_created':False,'health_reachable':False,
        'cloudflared_on_path':shutil.which('cloudflared') is not None,'ngrok_on_path':shutil.which('ngrok') is not None}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open('http://127.0.0.1:'+str(port)+'/healthz',timeout=3) as response:
            payload=response.read(2049)
            if len(payload)>2048:raise ValueError('Unexpected health response size')
            data=json.loads(payload)
            result.update(health_reachable=response.status==200,synthetic_test_mode=data.get('mode')=='synthetic_test',
                experimental_mode=data.get('mode')=='xclip_experimental')
    except Exception as error:result['technical_error_type']=type(error).__name__
    result['competition_release_ready']=False
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    result=inspect_local(args.port)
    directory=ROOT/'.private/access-preflight';directory.mkdir(exist_ok=True)
    (directory/'safe-summary.json').write_text(json.dumps(result,indent=2),encoding='ascii')
    print(json.dumps(result),flush=True)
