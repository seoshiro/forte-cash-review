"""Read only completed aggregate reports for the authorized identical restart."""
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.xclip_last_layer_budget import configure, OUT, CONFIG, original
from scripts.summarize_xclip_last_layer import main
EXPECTED_REGISTRATION = '66bd2c2ab9f49ee073c37e31b7379035e3e76bd0f64b5d6381b3efa1e6dcca36'


if __name__ == '__main__':
    try:
        (OUT / 'calculation-safe-summary.json').unlink(missing_ok=True)
        configure()
        main(out=OUT, config_path=CONFIG, expected_registration=EXPECTED_REGISTRATION, verifier=original.verify)
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False})); sys.exit(1)
