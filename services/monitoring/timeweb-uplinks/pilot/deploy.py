"""Explicit approved pilot installation; never applies or rolls back route guards."""

from pathlib import Path
import sys
import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SSH = ['ssh', '-i', str(Path(__file__).resolve().parents[4] / '.local/ssh/codex_timeweb_audit_20260628'),
       '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UpdateHostKeys=no', '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
       '-o', 'ServerAliveCountMax=2', 'root@94.241.171.65']


def remote(script, timeout=30):
    return subprocess.run(SSH+['bash -se'], input=script.encode(), check=True, timeout=timeout)


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = ROOT.parents[2] / '.local/evidence'/f'{stamp}-pilot-deployment'
    evidence.mkdir(mode=0o700)
    backup = subprocess.run(SSH+['tar -czf - -C / opt/vpn-monitoring var/lib/vpn-uplink-guards'],
                            check=True, capture_output=True, timeout=30).stdout
    path = evidence/'pre-install.tar.gz'
    path.write_bytes(backup)
    path.chmod(0o600)
    with tarfile.open(path) as tar:
        assert 'opt/vpn-monitoring/guards/guard-manifest.json' in tar.getnames()
    print(f'BACKUP {path} SHA256 {hashlib.sha256(backup).hexdigest()}', flush=True)
    remote('test ! -e /opt/vpn-monitoring/pilot\ntest ! -e /etc/systemd/system/vpn-uplink-pilot.service\n')
    # venv bootstrap is the sole system-Python operation. All application/pip calls use .venv.
    remote((ROOT/'pilot/bootstrap.sh').read_text(), timeout=210)
    config = json.loads((ROOT/'collector/config.candidate.json').read_text())
    config.update(helper='/opt/vpn-monitoring/pilot/candidate/guardctl-batch.sh',
                  allow_snapshot_scope=True, deployment_mode='pilot')
    (ROOT/'pilot/config.json').write_text(json.dumps(config, indent=2)+'\n')
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as tar:
        for directory in ('collector/uplink_monitor', 'candidate'):
            for source in sorted((ROOT/directory).glob('*')):
                if source.suffix in ('.py', '.sh'):
                    tar.add(source, arcname=str(source.relative_to(ROOT)))
        tar.add(ROOT/'collector/requirements.txt', arcname='collector/requirements.txt')
        tar.add(ROOT/'pilot/config.json', arcname='config.json')
    subprocess.run(SSH+['umask 077; tar --no-same-owner --no-same-permissions -xf - -C /opt/vpn-monitoring/pilot'],
                   input=archive.getvalue(), check=True, timeout=30)
    remote('/opt/vpn-monitoring/pilot/.venv/bin/pip install --timeout 15 --retries 1 '
           '-r /opt/vpn-monitoring/pilot/collector/requirements.txt\n', timeout=90)
    for name in ('vpn-uplink-pilot.service', 'vpn-uplink-exporter.service'):
        subprocess.run(SSH+[f'install -m 644 /dev/stdin /etc/systemd/system/{name}'],
                       input=(ROOT/'pilot'/name).read_bytes(), check=True, timeout=15)
    remote('systemctl daemon-reload\nsystemctl enable --now vpn-uplink-pilot vpn-uplink-exporter\n'
           'systemctl is-active vpn-uplink-pilot vpn-uplink-exporter\n')
    print('DEPLOYED', evidence, flush=True)


if __name__ == '__main__':
    main()
