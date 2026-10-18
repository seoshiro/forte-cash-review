"""Local-only inference origin; no keys generated or results logged here."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def create_origin(directory):
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session,FinalOrigin
    from xclip_candidate.experimental import load_prototypes,PACK_DIRECTORY
    directory=Path(directory).resolve();record=validate_session(load(directory/'credentials.dpapi'))
    load_prototypes(ROOT/PACK_DIRECTORY)
    os.environ.update(CASH_MODE='xclip_experimental',CASH_ENGINE='xclip_experimental',CASH_PRIVATE=str(ROOT/'.private/final-service'),
        CASH_API_KEY=','.join(record[k] for k in ['jury','operator','other_owner']),CASH_JOB_BUDGET_SEC='295',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
    from cashreview.api import create_app
    return FinalOrigin(create_app(),record,directory)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
    try:
        import uvicorn
        uvicorn.run(create_origin(args.directory),host='127.0.0.1',port=8771,access_log=False,log_level='critical',limit_concurrency=16)
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'private_content_emitted':False}));raise SystemExit(1)
