#!/usr/bin/env python3
"""Validate repository links, profile parity, inventory and known-secret exclusion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zipfile

from private_store import ROOT, load, local_root, materialize

IGNORED = {'.git', '.local', '.venv', '__pycache__', '.pytest_cache', 'node_modules'}
LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\s*\)')


def anchor_slug(title):
    return re.sub(r'[^\w\s-]', '', title.lower()).strip().replace(' ', '-')


def public_files(root=ROOT):
    for folder, directories, names in os.walk(root):
        directories[:] = [name for name in directories if name not in IGNORED]
        for name in names:
            path = Path(folder) / name
            if name != '.DS_Store' and path.suffix != '.pyc':
                yield path


def resolve_link(document, reference):
    reference = unquote(reference)
    if urlsplit(reference).scheme or reference.startswith(('#', '//')):
        return None
    reference, _, anchor = reference.partition('#')
    reference = reference.split('?', 1)[0]
    if not reference:
        return None
    if reference.startswith(('/', '~')):
        return 'absolute_file_link'
    target = document.parent / reference
    if not target.exists():
        return 'missing_file_link'
    if anchor and target.suffix == '.md':
        headings = re.findall(r'^#{1,6}\s+(.+?)\s*#*$', target.read_text(), re.MULTILINE)
        if anchor not in {anchor_slug(title) for title in headings}:
            return 'missing_heading_anchor'
    return None


def validate():
    problems = []
    store = load()
    private = local_root()
    profile_inventory = json.loads((ROOT / 'config/inventory/clients.json').read_text())['profiles']
    expected = {item['path'] for item in profile_inventory}
    actual = {str(path.relative_to(private / 'clients')) for path in (private / 'clients').rglob('*')
              if path.is_file() and path.suffix in {'.conf', '.json'}}
    if len(expected) != len(profile_inventory) or expected != actual:
        problems.append({'check': 'profile_set'})
    for item in profile_inventory:
        path = private / 'clients' / item['path']
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            problems.append({'check': 'profile_hash', 'path': item['path']})
    materialized = materialize(verify_only=True)
    inventory = json.loads((ROOT / 'config/inventory/observations.json').read_text())
    ids = [item['id'] for item in inventory['devices']]
    if len(ids) != len(set(ids)) or len(ids) != len({(p['owner'], p['device']) for p in profile_inventory}):
        problems.append({'check': 'device_inventory_cardinality'})
    # Hash fields named psk are metadata, not the pre-shared key itself.
    known = {record['value']: record['id'] for record in store.get('records', [])
             if isinstance(record.get('value'), str) and len(record['value']) >= 10 and
             '/hashes/' not in record.get('id', '')}
    files = list(public_files())
    for path in files:
        relative = str(path.relative_to(ROOT))
        if path.is_symlink():
            problems.append({'check': 'public_symlink', 'path': relative})
            continue
        if path.suffix == '.docx':
            with zipfile.ZipFile(path) as document:
                content = '\n'.join(document.read(name).decode(errors='ignore')
                                    for name in document.namelist() if name.endswith('.xml'))
        else:
            content = path.read_bytes().decode(errors='ignore')
        if re.search(r'-----BEGIN (?:OPENSSH |RSA |EC |ENCRYPTED )?PRIVATE KEY-----', content):
            problems.append({'check': 'private_key_in_public', 'path': relative})
        if any(value in content for value in known):
            problems.append({'check': 'known_secret_in_public', 'path': relative})
        if path.suffix == '.md':
            for match in LINK.finditer(content):
                reason = resolve_link(path, match[1] or match[2])
                if reason:
                    problems.append({'check': reason, 'path': relative, 'line': content[:match.start()].count('\n') + 1})
        if path.suffix == '.html':
            for reference in re.findall(r'(?:href|src)=["\']([^"\']+)', content):
                reason = resolve_link(path, reference)
                if reason:
                    problems.append({'check': reason, 'path': relative})
    ignored = subprocess.run(['git', 'check-ignore', '.local/secrets.json', '.venv/bin/python'],
                             cwd=ROOT, capture_output=True, text=True)
    if set(ignored.stdout.splitlines()) != {'.local/secrets.json', '.venv/bin/python'}:
        problems.append({'check': 'private_git_ignore'})
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, capture_output=True, text=True, check=True)
    if any(name.startswith(('.local/', '.venv/')) for name in staged.stdout.splitlines()):
        problems.append({'check': 'private_staged'})
    return {'status': 'PASSED' if not problems else 'FAILED', 'public_files': len(files),
            'profiles': len(expected), 'devices': len(ids), 'private_files': materialized['files'],
            'problems': problems}


if __name__ == '__main__':
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['status'] == 'PASSED' else 1)
