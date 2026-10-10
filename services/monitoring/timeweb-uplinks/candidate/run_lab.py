"""Explicit isolated Linux lab. Never replaces the installed helper or routes."""

from pathlib import Path
import sys
import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SSH = ['/usr/bin/ssh', '-i', str(Path(__file__).resolve().parents[4] / '.local/ssh/codex_timeweb_audit_20260628'),
       '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UpdateHostKeys=no', '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
       '-o', 'ServerAliveCountMax=2', 'root@94.241.171.65']


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT.parents[2] / '.local/evidence'/f'{stamp}-batch-lab'
    out.mkdir(mode=0o700)
    stage = '/root/uplink-batch-candidate-' + stamp
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as tar:
        for name in ('guardctl-batch.sh', 'batch_probe.sh', 'batch_lab.sh'):
            tar.add(ROOT/'candidate'/name, arcname=name)
    subprocess.run(SSH + [f'umask 077; mkdir {stage} && tar -xf - -C {stage}'],
                   input=archive.getvalue(), check=True, timeout=20)
    script = f'''set -eu
before=$(sha256sum /opt/vpn-monitoring/guards/guardctl.sh)
pid=$(docker inspect -f '{{{{.State.Pid}}}}' wg-relay)
live_snapshot() {{
  nsenter -t "$pid" -n ip -j -4 rule show
  nsenter -t "$pid" -n ip -j -4 route show table all
  nsenter -t "$pid" -n iptables -S
  nsenter -t "$pid" -n iptables -t nat -S
  nsenter -t "$pid" -n iptables -t mangle -S
}}
live_before=$(live_snapshot | sha256sum)
set +e
timeout --kill-after=3s 150s unshare --net env CANCEL_ONLY={'yes' if os.environ.get('CANCEL_ONLY')=='yes' else 'no'} bash {stage}/batch_lab.sh
rc=$?
set -e
test "$before" = "$(sha256sum /opt/vpn-monitoring/guards/guardctl.sh)"
test "$pid" = "$(docker inspect -f '{{{{.State.Pid}}}}' wg-relay)"
test "$live_before" = "$(live_snapshot | sha256sum)"
printf 'LIVE_ROUTING_UNCHANGED %s\\n' "$live_before"
printf 'LIVE_HELPER_UNCHANGED %s\\n' "$before"
exit "$rc"
'''
    result = subprocess.run(SSH+['bash -s'], input=script, text=True,
                            capture_output=True, timeout=170)
    (out/'result.json').write_text(json.dumps(dict(returncode=result.returncode,
        stdout=result.stdout, stderr=result.stderr, stage=stage), indent=2)+'\n')
    print(out)
    for line in result.stdout.splitlines():
        if line.startswith(('PASS ', 'FAIL ', 'SUMMARY ', 'CLEANUP ', 'LIVE_', 'REFUSED ', 'START ')):
            print(line)
    if result.stderr:
        print(result.stderr[-2000:])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
