"""Patched runtime backend for synthetic-only browser QA. No real manifest import."""
from pathlib import Path
import sys,argparse,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    import uvicorn
    from scripts.synthetic import generate
    from local_review.app import create_review_app
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out).resolve()
    if not out.is_relative_to(ROOT/'.private/train-review-synthetic-qa'):raise ValueError('Synthetic output must stay in test workspace')
    out.mkdir(parents=True,exist_ok=True);path=generate(out/'generated-safe.mov');sha=hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[{'split':'train','path':str(path),'sha256':sha,'target':i%2,'label_sec':1. if i%2 else None,'duration_sec':3.} for i in range(8)]
    app=create_review_app(rows,out/'server-private','temporary-synthetic-review-only','synthetic-registration-only',synthetic=True)
    uvicorn.run(app,host='127.0.0.1',port=a.port,access_log=False,log_level='warning')
