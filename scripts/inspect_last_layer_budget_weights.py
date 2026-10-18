"""Parameter-only audit of the completed restart, no media or predictions."""
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts import inspect_last_layer_weights as audit
from scripts.summarize_xclip_last_layer_budget import EXPECTED_REGISTRATION, OUT


if __name__ == '__main__':
    try:
        audit.OUT = OUT; audit.EXPECTED_REGISTRATION = EXPECTED_REGISTRATION
        audit.main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False})); sys.exit(1)
