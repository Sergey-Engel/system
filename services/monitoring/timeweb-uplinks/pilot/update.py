"""Apply one reviewed, rollback-capable TimeWeb pilot update.

Only the files in FILES are eligible for this updater. In particular,
storage.py deliberately remains on its installed revision.
The updater never changes WireGuard, routes, firewall rules, guards or units;
an optional upstream failover module may invoke its reviewed endpoint controller.
"""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import tarfile

from deploy import ROOT, SSH


REMOTE_ROOT = PurePosixPath('/opt/vpn-monitoring/pilot')
FILES = (
    (Path('collector/uplink_monitor/daemon.py'), 0o600),
    (Path('collector/uplink_monitor/collector.py'), 0o600),
    (Path('collector/uplink_monitor/failover.py'), 0o600),
    (Path('collector/uplink_monitor/model.py'), 0o600),
    (Path('collector/uplink_monitor/exporter.py'), 0o600),
    (Path('candidate/batch_probe.sh'), 0o644),
    (Path('config.json'), 0o600),
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_path(relative):
    if relative == Path('config.json'):
        return ROOT / 'pilot' / relative
    return ROOT / relative


def remote(script, *, timeout=30):
    return subprocess.run(SSH + ['bash -se'], input=script, text=True,
                          check=True, timeout=timeout)


def remote_archive():
    command = 'tar -czf - -C / ' + ' '.join(
        shlex.quote(str((REMOTE_ROOT / path).relative_to('/'))) for path, _ in FILES)
    return subprocess.run(SSH + [command], check=True, capture_output=True,
                          timeout=30).stdout


def local_archive():
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as tar:
        for relative, _ in FILES:
            tar.add(source_path(relative), arcname=str(relative))
    return archive.getvalue()


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = ROOT.parents[2] / '.local/evidence' / f'{stamp}-pilot-stability-update'
    evidence.mkdir(mode=0o700)
    expected = {
        str(relative): dict(sha256=sha256(source_path(relative)), mode=f'{mode:04o}')
        for relative, mode in FILES
    }
    manifest = dict(timestamp_utc=stamp, scope='collector stability only', files=expected,
                    excluded=['collector/uplink_monitor/storage.py',
                              'systemd units', 'guards', 'routes', 'firewall', 'WireGuard'])
    (evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (evidence / 'manifest.json').chmod(0o600)

    backup = remote_archive()
    backup_path = evidence / 'pre-update.tar.gz'
    backup_path.write_bytes(backup)
    backup_path.chmod(0o600)
    expected_backup = {str((REMOTE_ROOT / relative).relative_to('/')) for relative, _ in FILES}
    with tarfile.open(backup_path) as tar:
        names = set(tar.getnames())
    if not expected_backup <= names:
        raise RuntimeError('remote_backup_inventory_incomplete')

    stage = f'{REMOTE_ROOT}/.update-{stamp.lower()}-{os.getpid()}'
    quoted_stage = shlex.quote(stage)
    remote(f'umask 077\ntest ! -e {quoted_stage}\nmkdir {quoted_stage}\n')
    applied = False
    try:
        subprocess.run(
            SSH + [f'umask 077; tar --no-same-owner --no-same-permissions -xf - -C {quoted_stage}'],
            input=local_archive(), check=True, timeout=30)

        checks = '\n'.join(
            f'test "$(sha256sum {shlex.quote(stage + "/" + relative)} | awk \'{{print $1}}\')" = "{value["sha256"]}"'
            for relative, value in expected.items())
        installs = '\n'.join(
            f'install -m {value["mode"]} {shlex.quote(stage + "/" + relative)} '
            f'{shlex.quote(str(REMOTE_ROOT / relative))}'
            for relative, value in expected.items())
        restore = '\n'.join(
            f'install -m {value["mode"]} {shlex.quote(stage + "/previous/" + relative)} '
            f'{shlex.quote(str(REMOTE_ROOT / relative))}'
            for relative, value in expected.items())
        backup_current = '\n'.join(
            f'install -D -m {value["mode"]} {shlex.quote(str(REMOTE_ROOT / relative))} '
            f'{shlex.quote(stage + "/previous/" + relative)}'
            for relative, value in expected.items())
        remote(f'''set -euo pipefail
stage={quoted_stage}
{checks}
mkdir -p "$stage/previous"
{backup_current}
restore() {{
{restore}
  systemctl start vpn-uplink-pilot.service || true
  systemctl restart vpn-uplink-exporter.service || true
}}
if ! systemctl stop vpn-uplink-pilot.service; then
  exit 1
fi
if ! ( {installs} ); then
  restore
  exit 1
fi
if ! systemctl start vpn-uplink-pilot.service; then
  restore
  exit 1
fi
if ! systemctl restart vpn-uplink-exporter.service; then
  restore
  exit 1
fi
sleep 2
if ! systemctl is-active --quiet vpn-uplink-pilot.service || ! systemctl is-active --quiet vpn-uplink-exporter.service; then
  restore
  exit 1
fi
systemctl is-active vpn-uplink-pilot.service vpn-uplink-exporter.service
''', timeout=90)
        applied = True
        print(f'UPDATED evidence={evidence} backup_sha256={hashlib.sha256(backup).hexdigest()}')
    finally:
        if applied:
            # The path was created by this process and contains only staged copies.
            remote(f'test -d {quoted_stage} && rm -rf {quoted_stage} || true\n')
        else:
            print(f'UPDATE_FAILED stage_retained={stage}')


if __name__ == '__main__':
    main()
