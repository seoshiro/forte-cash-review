"""Loopback generated-only fault fixture; never imported by real delivery."""
from pathlib import Path
import argparse,hashlib,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def create_origin(directory,budget):
    from scripts.synthetic import generate
    directory=Path(directory).resolve();media=generate(directory/'fixtures/safe.mov')
    os.environ.update(CASH_MODE='synthetic_test',CASH_ENGINE='baseline',CASH_PRIVATE=str(directory/'service'),
        CASH_API_KEY='temporary-loopback-fault-only',CASH_TEST_HASHES=hashlib.sha256(media.read_bytes()).hexdigest(),
        CASH_TEST_DELAY_SEC='10',CASH_JOB_BUDGET_SEC=str(budget))
    from cashreview.api import create_app
    return create_app()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--port',type=int,required=True);parser.add_argument('--budget',type=float,required=True);args=parser.parse_args()
    try:
        import uvicorn
        uvicorn.run(create_origin(args.directory,args.budget),host='127.0.0.1',port=args.port,access_log=False,log_level='critical')
    except Exception:raise SystemExit(1)
