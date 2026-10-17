"""Local research API only; fixed temporary test key, never a jury deployment."""
from pathlib import Path
import os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from xclip_candidate.experimental import PACK_DIRECTORY
    if not (ROOT/PACK_DIRECTORY/'prototypes.json').exists():raise RuntimeError('Prepare the private experimental prototype pack first')
    os.environ.update(CASH_MODE='xclip_experimental',CASH_ENGINE='xclip_experimental',
        CASH_PRIVATE=str(ROOT/'.private/xclip-experimental-service'),CASH_API_KEY='temporary-xclip-experimental-only')
    import uvicorn
    from cashreview.api import create_app
    uvicorn.run(create_app(),host='127.0.0.1',port=8768,access_log=False,log_level='warning')
