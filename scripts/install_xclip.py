"""Public pinned model bootstrap; never accesses bank data or runs inference."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from huggingface_hub import HfApi
    from cashreview.supervision import atomic_json
    from scripts.prepare_xclip import main as prepare
    cfg=json.loads((ROOT/'config/xclip-artifacts.json').read_text())
    info=HfApi(token=False).model_info(cfg['repo'],revision=cfg['revision'],files_metadata=True,timeout=30)
    license_name=info.card_data.get('license') if info.card_data else None
    if info.sha!=cfg['revision'] or license_name!='mit':raise ValueError('Official pinned revision/license mismatch')
    artifacts=[]
    for row in info.siblings:
        artifacts.append({'rfilename':row.rfilename,'size':row.size,'lfs':{'sha256':row.lfs.sha256} if row.lfs else None})
    weight=next(r for r in artifacts if r['rfilename']==cfg['weight_file'])
    if weight['size']!=cfg['weight_bytes'] or not weight['lfs'] or weight['lfs']['sha256']!=cfg['weight_sha256']:raise ValueError('Official pinned weight identity mismatch')
    directory=ROOT/'.private/xclip-prepare';directory.mkdir(parents=True,exist_ok=True)
    atomic_json(directory/'metadata.json',{'revision':info.sha,'license':license_name,'artifacts':artifacts})
    prepare()


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'failed','technical_error_type':type(e).__name__,'private_content_emitted':False}));sys.exit(1)
