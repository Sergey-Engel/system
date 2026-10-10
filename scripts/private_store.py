#!/usr/bin/env python3
"""Materialize and verify the local-only portable credential store."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def local_root():
    return Path(os.environ.get('SYSTEM_PRIVATE_ROOT', str(ROOT / '.local'))).resolve()


def write_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    if path.is_symlink():
        raise ValueError('Refusing symlink destination')
    fd, temporary = tempfile.mkstemp(prefix='.private-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if path.is_symlink():
            raise ValueError('Refusing symlink destination')
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load(root=None):
    path = (root or local_root()) / 'secrets.json'
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:
        raise ValueError('Credential store must be a private regular file')
    data = json.loads(path.read_text())
    if data['schema_version'] != 1:
        raise ValueError('Unsupported credential store schema')
    return data


def materialize(root=None, verify_only=False):
    root = (root or local_root()).resolve()
    data = load(root)
    seen, validated = set(), []
    for record in data['files']:
        relative = PurePosixPath(record['path'])
        if (not relative.parts or relative.is_absolute() or '..' in relative.parts or
                str(relative) in seen or str(relative) == 'secrets.json'):
            raise ValueError('Unsafe or duplicate materialized path')
        seen.add(str(relative))
        target = root / relative
        if any(parent.is_symlink() for parent in (target, *target.parents) if parent != root):
            raise ValueError('Refusing symlink in materialized path')
        if not target.resolve().is_relative_to(root):
            raise ValueError('Materialized path escapes private root')
        payload = base64.b64decode(record['value'], validate=True)
        if hashlib.sha256(payload).hexdigest() != record['sha256']:
            raise ValueError('Credential record checksum mismatch')
        validated.append((target, payload))
    for target, payload in validated:
        if not verify_only:
            write_private(target, payload)
        if target.is_symlink() or target.read_bytes() != payload or target.stat().st_mode & 0o077:
            raise ValueError('Materialized credential differs from canonical record')
    return {'status': 'VERIFIED', 'files': len(seen), 'records': len(data.get('records', []))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(materialize(args.root, args.verify_only)))
