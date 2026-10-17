"""Manual launch only; no browser automation or model inference."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if __name__=='__main__':
    try:
        from local_review.main import main
        main()
    except Exception as error:
        print('Local review did not start: '+type(error).__name__+'. Existing files/processes were preserved.');sys.exit(1)
