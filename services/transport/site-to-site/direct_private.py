"""Checkpoint only explicit local direct-control files in the portable store."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location('direct_private_store', ROOT / 'scripts/private_store.py')
store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store)


def checkpoint(paths):
    data = store.load()
    for path in paths:
        path = Path(path)
        relative = path.relative_to(ROOT / '.local')
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError('unsafe_direct_checkpoint')
        payload = path.read_bytes()
        record = dict(path=str(relative), value=base64.b64encode(payload).decode(),
                      sha256=hashlib.sha256(payload).hexdigest(),
                      provenance='Approved persistent direct SSTP control')
        existing = next((r for r in data['files'] if r['path'] == record['path']), None)
        if existing:
            existing.update(record)
        else:
            data['files'].append(record)
    store.write_private(ROOT / '.local/secrets.json', (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())
