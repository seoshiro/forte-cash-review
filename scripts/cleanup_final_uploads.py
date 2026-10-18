"""User-invoked fallback cleanup; running native store lock prevents deletion."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.session_cleanup import purge_final_uploads
from cashreview.supervision import atomic_json
from cashreview.technical_diagnostics import safe_exception

if __name__=='__main__':
    try:
        result=purge_final_uploads(ROOT);report={'status':'PASS' if not result['blocked'] else 'partial','scope':'Stopped final-profile temporary uploads only; original dataset untouched',**result}
        atomic_json(ROOT/'.private/final-access/upload-cleanup-safe-summary.json',report);print(json.dumps(report))
    except Exception as error:print(json.dumps({'status':'blocked','diagnostic':safe_exception(error,ROOT),'private_content_emitted':False}));raise SystemExit(1)
