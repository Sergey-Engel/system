"""Deploy the isolated loopback console with a backup of its prior state."""
import datetime
import hashlib
from pathlib import Path
import subprocess

from deploy import ROOT, SSH


FILES = {
    ROOT / 'collector/uplink_monitor/console.py': '/opt/vpn-monitoring/pilot/collector/uplink_monitor/console.py',
    ROOT / 'collector/uplink_monitor/failover.py': '/opt/vpn-monitoring/pilot/collector/uplink_monitor/failover.py',
    ROOT / 'pilot/config.json': '/opt/vpn-monitoring/pilot/config.json',
    ROOT / 'pilot/vpn-uplink-console.service': '/etc/systemd/system/vpn-uplink-console.service',
    ROOT / 'pilot/timeweb-console-locks.conf': '/etc/tmpfiles.d/timeweb-console-locks.conf',
}


def remote(script, timeout=30):
    return subprocess.run(SSH + ['bash -se'], input=script, text=True, check=True, timeout=timeout)


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = ROOT.parents[2] / '.local/evidence' / f'{stamp}-console-deployment'
    evidence.mkdir(mode=0o700)
    backup = subprocess.run(SSH + ['tar -czf - --ignore-failed-read -C / opt/vpn-monitoring/pilot/collector/uplink_monitor/console.py opt/vpn-monitoring/pilot/config.json etc/systemd/system/vpn-uplink-console.service etc/tmpfiles.d/timeweb-console-locks.conf'],
                            capture_output=True, check=True, timeout=30).stdout
    (evidence / 'pre-console-update.tar.gz').write_bytes(backup)
    (evidence / 'pre-console-update.tar.gz').chmod(0o600)
    for source, target in FILES.items():
        subprocess.run(SSH + [f'umask 077; install -D -m {"644" if target.startswith("/etc/") else "600"} /dev/stdin {target}'],
                       input=source.read_bytes(), check=True, timeout=30)
    remote('''systemd-tmpfiles --create /etc/tmpfiles.d/timeweb-console-locks.conf
systemctl daemon-reload
systemctl enable vpn-uplink-console.service
systemctl restart vpn-uplink-console.service
systemctl is-active vpn-uplink-console.service
for attempt in $(seq 1 10); do
  ss -ltnH | grep -q "127.0.0.1:19108" && exit 0
  sleep 1
done
exit 1
''')
    digest = hashlib.sha256((evidence / 'pre-console-update.tar.gz').read_bytes()).hexdigest()
    print(f'DEPLOYED evidence={evidence} backup_sha256={digest}')


if __name__ == '__main__':
    main()
