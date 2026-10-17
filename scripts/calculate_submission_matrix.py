"""Reproduce criterion maxima and configured timing; never estimate an award."""
from datetime import datetime, timedelta
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def calculate():
    cfg = json.loads((ROOT / 'config/submission-criteria.json').read_text())
    deadline = datetime.fromisoformat(cfg['user_deadline_utc'].replace('Z', '+00:00'))
    return {
        'split': 'technical',
        'criterion_maximum_total': sum(row['max_points'] for row in cfg['criteria']),
        'criterion_count': len(cfg['criteria']),
        'user_deadline_utc': deadline.isoformat(),
        'feature_freeze_utc': (deadline - timedelta(hours=cfg['feature_freeze_hours_before_user_deadline'])).isoformat(),
        'availability_reserve_start_utc': (deadline - timedelta(hours=cfg['availability_reserve_hours_before_user_deadline'])).isoformat(),
        'awarded_score_estimated': False,
        'scheduled_automation_created': False,
    }


if __name__ == '__main__':
    result = calculate()
    path = ROOT / '.private/submission-matrix/safe-summary.json'
    if path.exists():
        if json.loads(path.read_text()) != result:
            raise ValueError('Saved aggregate differs from the configured calculation')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result))
