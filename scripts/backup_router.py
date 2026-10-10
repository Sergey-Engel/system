#!/usr/bin/env python3
"""Fresh RouterOS exports and an encrypted backup; no routing or user changes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

from private_store import ROOT, local_root, load, write_private


def run(host, command, timeout=40, stdin=None):
    return subprocess.run(['ssh', '-F', str(local_root() / 'ssh/config'), '-T', host, command],
                          input=stdin, capture_output=True, timeout=timeout)


def backup(host):
    alias = 'mikrotik-' + host
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest = local_root() / 'backups' / host / stamp
    dest.mkdir(parents=True, mode=0o700)
    report = dict(host=host, timestamp_utc=stamp, status='BLOCKED', scope='RouterOS configuration, not disk image')
    try:
        identity = run(alias, '/system identity print; /system resource print; /system routerboard print')
        write_private(dest / 'identity.txt', identity.stdout + identity.stderr)
        text = identity.stdout.decode(errors='replace')
        expected = 'hAP ax3' if host == 'nakhimova' else 'hEX'
        serial = 'HKM0BDXYG74' if host == 'nakhimova' else '8AFF0A501C19'
        if identity.returncode or expected not in text.replace('^', '') or serial not in text:
            report['reason'] = 'Unreachable or expected router identity not confirmed'
            return report
        result = run(alias, '/export terse show-sensitive' if host == 'nakhimova' else '/export terse')
        write_private(dest / 'export.stderr', result.stderr)
        export = result.stdout
        if result.returncode or b'RouterOS' not in export or not re.search(rb'^/(interface|ip|system)\b', export, re.M):
            report['reason'] = 'Fresh export failed'
            return report
        write_private(dest / 'router-export.rsc', export)
        report.update(status='PARTIAL', export_sha256=hashlib.sha256(export).hexdigest(), export_bytes=len(export))
        if host == 'orekhovo':
            report['reason'] = 'Existing audit account is read-only; no permission escalation for binary backup'
            return report
        name = 'system-migration-' + stamp
        password = secrets.token_urlsafe(32)
        store = load()
        store['records'].append(dict(id='backup:' + host + ':' + stamp, type='router_backup_password', host=host,
                                     provenance='.local/backups/' + host + '/' + stamp, value=password))
        write_private(local_root() / 'secrets.json', (json.dumps(store, ensure_ascii=False, indent=2)+'\n').encode())
        # The password travels over encrypted SSH stdin, not local process arguments.
        command = f'/system backup save name="{name}" encryption=aes-sha256 password="{password}"\n'
        result = run(alias, '', stdin=command.encode())
        write_private(dest / 'save.log', result.stdout + result.stderr)
        if result.returncode or any(token in result.stdout.lower() for token in (b'failure:', b'syntax error', b'not enough permissions')):
            report['reason'] = 'Encrypted binary backup creation failed'
            return report
        target = dest / 'router.backup'
        batch = f'get {name}.backup {target}\n'
        transfer = subprocess.run(['sftp', '-F', str(local_root() / 'ssh/config'), '-b', '-', alias],
                                  input=batch.encode(), capture_output=True, timeout=45)
        write_private(dest / 'transfer.log', transfer.stdout + transfer.stderr)
        if transfer.returncode or not target.is_file() or target.stat().st_size < 100:
            report['reason'] = 'Encrypted binary backup exists remotely; local transfer failed'
            report['remote_file'] = name + '.backup'
            return report
        target.chmod(0o600)
        second = dest / 'router-second-download.backup'
        transfer = subprocess.run(['sftp', '-F', str(local_root() / 'ssh/config'), '-b', '-', alias],
                                  input=f'get {name}.backup {second}\n'.encode(), capture_output=True, timeout=45)
        if transfer.returncode or second.read_bytes() != target.read_bytes():
            report['reason'] = 'Independent binary transfer verification failed'
            return report
        second.unlink()
        report.update(status='VERIFIED_TRANSFER', binary_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                      binary_bytes=target.stat().st_size, password_record='backup:' + host + ':' + stamp,
                      limitation='Encrypted bytes downloaded twice; live restore was not executed', remote_file=name + '.backup')
    except (OSError, subprocess.TimeoutExpired):
        report['reason'] = 'Connection or transfer timeout'
    finally:
        write_private(dest / 'verification.json', (json.dumps(report, indent=2)+'\n').encode())
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', choices=['nakhimova', 'orekhovo'])
    args = parser.parse_args()
    os.umask(0o077)
    result = backup(args.host)
    print(json.dumps(result))
    sys.exit(0 if result['status'] == 'VERIFIED_TRANSFER' else 2)
