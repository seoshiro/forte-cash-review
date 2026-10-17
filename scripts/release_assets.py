"""Exact, reviewed public documentation assets. Never allow arbitrary media."""
import hashlib

SAFE_PUBLIC_ASSETS = {
    'docs/assets/upload-empty.png': {
        'sha256': '740cca8a9de0df8d6604a2832f87a23e1932ec2bd008af3321e332024dc00ea8',
        'bytes': 69762,
        'scope': 'Actual empty synthetic-test UI; no selected file, media, key, job or result',
    },
}


def approved_asset(name, data):
    item = SAFE_PUBLIC_ASSETS.get(name)
    return bool(item and len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'])
