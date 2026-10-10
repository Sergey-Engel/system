"""Generate a local checksum inventory after reviewing accepted lab reports."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ['20260912T164318Z', '20260912T164426Z']


def main():
    os.umask(0o077)
    for run in RUNS:
        report = json.loads((ROOT / 'lab/results' / run / 'report.json').read_text())
        assert report['accepted'] and len(report['results']) == 20
    latest = ROOT / 'lab/results' / RUNS[-1]
    assert json.loads((latest / 'input-integrity.json').read_text())['unchanged']
    tested = json.loads((latest / 'input-sha256.json').read_text())
    for name, checksum in tested.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == checksum, 'Tested input changed: ' + name
    meta = {}
    for p in sorted(ROOT.rglob('*')):
        if p.is_symlink():
            raise RuntimeError('Unexpected symlink: ' + str(p.relative_to(ROOT)))
        if p.is_dir():
            p.chmod(0o700)
            continue
        if p.name == 'stage3_artifact_inventory.json' or '__pycache__' in p.parts:
            continue
        if p.name != 'xray':
            p.chmod(0o600)
        meta[str(p.relative_to(ROOT))] = dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            bytes=p.stat().st_size, mode=oct(p.stat().st_mode & 0o777))
    inventory = dict(created_utc=datetime.now(timezone.utc).isoformat(),
        scope='Local staging/evidence only; not a deployment approval or digital signature',
        accepted_runs=RUNS, files=meta)
    path = ROOT / 'stage3_artifact_inventory.json'
    path.write_text(json.dumps(inventory, indent=2) + '\n')
    path.chmod(0o600)
    print('Inventory generated: ' + str(len(meta)) + ' files; all tested inputs match')


if __name__ == '__main__':
    main()
