"""Offline full-MAC identity and IEEE manufacturer lookup; never routing authority."""
import argparse
import csv
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import time

import managed

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / 'config/inventory/lan-devices.json'
CACHE = ROOT / '.local/cache/mac-vendors.json'
SOURCES = (
    ('https://standards-oui.ieee.org/oui/oui.csv', 6),
    ('https://standards-oui.ieee.org/oui28/mam.csv', 7),
    ('https://standards-oui.ieee.org/oui36/oui36.csv', 9),
    ('https://standards-oui.ieee.org/iab/iab.csv', 9),
)


def canonical(value):
    return managed.mac(value.replace('-', ':').upper())


def text(value, limit=120):
    if not isinstance(value, str):
        raise ValueError('invalid_device_name')
    cleaned = ''.join(c for c in value if c.isprintable()).strip()
    return cleaned[:limit] if limit is not None else cleaned


@lru_cache(maxsize=4)
def _json(path, modified, size):
    if size > 16_000_000:
        raise ValueError('oversized_name_database')
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        raise ValueError('invalid_name_database')
    return value


def read(path):
    path = Path(path)
    stat = path.stat()
    return _json(str(path), stat.st_mtime_ns, stat.st_size)


class DeviceNames:
    def __init__(self, inventory=INVENTORY, cache=CACHE):
        self.bindings, self.prefixes = {}, {}
        self.health = dict(inventory='unavailable', vendors='unavailable')
        try:
            records = read(inventory)['bindings']
            if not isinstance(records, list):
                raise ValueError('invalid_name_bindings')
            bindings = {}
            for record in records:
                mac, name = canonical(record['mac']), text(record['name'])
                if not name or mac in bindings:
                    raise ValueError('ambiguous_name_binding')
                bindings[mac] = name
            self.bindings = bindings
            self.health['inventory'] = 'ready'
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
        try:
            data = read(cache)
            prefixes = data['prefixes']
            if not isinstance(prefixes, dict) or any(not re.fullmatch(r'(?:[0-9A-F]{6}|[0-9A-F]{7}|[0-9A-F]{9})', k)
                    or not isinstance(v, str) for k, v in prefixes.items()):
                raise ValueError('invalid_vendor_prefixes')
            fetched = float(data['fetched_at'])
            self.prefixes = prefixes
            self.health.update(vendors='ready' if 0 <= time.time() - fetched < 90 * 86400 else 'stale', fetched_at=fetched)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass

    def resolve(self, mac, hostname=''):
        key = canonical(mac)
        local = bool(int(key[:2], 16) & 2)
        vendor = None
        if not local:
            raw = key.replace(':', '')
            vendor = next((text(self.prefixes[raw[:n]]) for n in (9, 7, 6) if raw[:n] in self.prefixes), None) or None
            if vendor and vendor.casefold() in ('private', 'ieee registration authority'):
                vendor = None
        host = text(hostname)
        if host.replace('-', ':').upper() == key:
            host = ''
        if key in self.bindings:
            label, source = self.bindings[key], 'inventory'
        elif host:
            label, source = host, 'dhcp'
        elif vendor:
            label, source = vendor + ' device', 'manufacturer'
        else:
            label, source = 'Unknown device (private MAC)' if local else 'Unknown device', 'unknown'
        return dict(label=label, name_source=source, manufacturer=vendor, mac_type='local' if local else 'universal')


def parse_csv(blob, width):
    rows = csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
    if not {'Registry', 'Assignment', 'Organization Name'}.issubset(rows.fieldnames or []):
        raise ValueError('invalid_ieee_csv')
    result = {}
    for row in rows:
        prefix, vendor = row['Assignment'].strip().upper(), text(row['Organization Name'], limit=None)
        if not re.fullmatch('[0-9A-F]{' + str(width) + '}', prefix) or not vendor:
            raise ValueError('invalid_ieee_assignment')
        # An empty value is an ambiguous assignment and blocks shorter-prefix fallback.
        result[prefix] = '' if prefix in result and result[prefix] != vendor else vendor
    if not result:
        raise ValueError('empty_ieee_csv')
    return result


def refresh(path=CACHE, runner=subprocess.run):
    prefixes, sources = {}, []
    for url, width in SOURCES:
        result = runner(['/usr/bin/curl', '--fail', '--silent', '--show-error', '--location',
            '--proto', '=https', '--proto-redir', '=https', '--max-time', '30', '--max-filesize', '16000000', url],
            capture_output=True, check=True, timeout=35)
        records = parse_csv(result.stdout, width)
        for key, vendor in records.items():
            prefixes[key] = '' if key in prefixes and prefixes[key] != vendor else vendor
        sources.append(dict(url=url, records=len(records), sha256=hashlib.sha256(result.stdout).hexdigest()))
    value = dict(schema_version=1, fetched_at=time.time(), prefixes=prefixes, sources=sources)
    from controller import write
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write(path, value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', required=True)
    parser.parse_args()
    data = refresh()
    print(json.dumps(dict(prefixes=len(data['prefixes']), fetched_at=data['fetched_at'], sources=data['sources'])))
