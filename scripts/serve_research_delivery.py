"""Prepare a separate protected research origin; no tunnel/key creation."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def create_origin(credentials_file):
    from cashreview.local_secrets import load
    from cashreview.research_delivery import validate_credentials,ResearchOrigin
    from xclip_candidate.experimental import load_prototypes,PACK_DIRECTORY
    record=validate_credentials(load(credentials_file))
    load_prototypes(ROOT/PACK_DIRECTORY)  # Existing preserved baseline; no new model inference.
    os.environ.update(CASH_MODE='xclip_experimental',CASH_ENGINE='xclip_experimental',
                      CASH_PRIVATE=str(ROOT/'.private/research-delivery-service'),CASH_API_KEY=record['primary']+','+record['other_owner'],
                      HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
    from cashreview.api import create_app
    return ResearchOrigin(create_app(),[record['primary'],record['other_owner']],record['expires_unix'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--credentials-file',type=Path,required=True);args=parser.parse_args()
    try:
        import uvicorn
        uvicorn.run(create_origin(args.credentials_file),host='127.0.0.1',port=8769,access_log=False,log_level='critical',limit_concurrency=16)
    except Exception as error:
        print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'credentials_or_private_data_emitted':False}));raise SystemExit(1)
