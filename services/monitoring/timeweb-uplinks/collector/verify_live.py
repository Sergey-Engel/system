"""One-shot Mac-side verification; no deployment and no working config changes."""

from pathlib import Path
import sys
import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

from uplink_monitor.collector import POLICIES
from uplink_monitor.model import parse_helper, assess

ROOT = Path(__file__).resolve().parents[1]
SSH = ['/usr/bin/ssh', '-i', str(Path(__file__).resolve().parents[4] / '.local/ssh/codex_timeweb_audit_20260628'),
       '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UpdateHostKeys=no', '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
       '-o', 'ServerAliveCountMax=2', 'root@94.241.171.65', 'bash -s']


def run(script, timeout=60):
    result = subprocess.run(SSH, input=script, text=True, capture_output=True, timeout=timeout)
    return dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def main():
    os.umask(0o077)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT.parents[2] / '.local/evidence'/f'{stamp}-collector-live-verification'
    out.mkdir(exist_ok=False)
    dns=run("set -e\ndate -u +%s\n" + '\n'.join(
        f"printf 'TARGET {name}\\n'\ndig +time=2 +tries=1 +noall +answer +comments {p['host']} A"
        for name,p in POLICIES.items()),20)
    (out/'dns.json').write_text(json.dumps(dns,indent=2)+'\n')
    if dns['returncode']:
        raise RuntimeError('dns_command_failed')
    resolved=int(dns['stdout'].splitlines()[0])
    blocks=re.split(r'^TARGET (\w+)\n',dns['stdout'],flags=re.M)
    targets={}
    ttls=[]
    for i in range(1,len(blocks),2):
        name, answer=blocks[i:i+2]
        policy=POLICIES[name]
        if 'status: NOERROR' not in answer:
            raise RuntimeError('dns_error')
        records=[line.split() for line in answer.splitlines() if line and not line.startswith(';')]
        # This one-shot verifier deliberately refuses CNAME chains. The collector
        # resolver must use dnspython for complete DNS answer/expiry semantics.
        if not records or any(len(r)!=5 or r[0]!=policy['host']+'.' or r[2:4]!=['IN','A'] for r in records):
            raise RuntimeError('unsupported_dns_answer')
        ips=[]
        for r in records:
            ttl=int(r[1])
            if not 30 <= ttl <= 86400 or not ipaddress.IPv4Address(r[4]).is_global:
                raise RuntimeError('unsafe_dns_answer')
            ips.append(r[4]); ttls.append(ttl)
        targets[name]=dict(url=policy['url'],host=policy['host'],ip=sorted(ips)[0],port=443)
    if set(targets)!=set(POLICIES):
        raise RuntimeError('missing_target')
    snapshot=dict(resolved_unix=resolved,expires_unix=resolved+min(ttls+[3600]),targets=targets)
    (out/'targets.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    print(f'DNS TTL snapshot ready; evidence: {out}',flush=True)
    script=r'''set -Eeuo pipefail
umask 077
dir=$(mktemp -d /root/vpn-monitoring-verification-XXXXXXXX)
printf '%s\n' TARGET_JSON > "$dir/targets.json"
helper=/opt/vpn-monitoring/guards/guardctl.sh
manifest=/opt/vpn-monitoring/guards/guard-manifest.json
printf 'REMOTE_EVIDENCE=%s\n' "$dir"
"$helper" "$manifest" check
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
for up in fornex cenuta; do
  if test "$up" = fornex; then dev=wg1; peer=10.20.0.2; else dev=wg-up-cenuta; peer=10.40.40.1; fi
  printf 'DIAGNOSTIC upstream=%s time=%s\n' "$up" "$(date -u +%FT%TZ)"
  nsenter -t "$pid" -n wg show "$dev" latest-handshakes
  nsenter -t "$pid" -n ping -n -I "$dev" -c 2 -W 1 "$peer" || true
  for target in gstatic cloudflare; do
    printf 'PROBE upstream=%s target=%s time=%s\n' "$up" "$target" "$(date -u +%FT%TZ)"
    set +e
    "$helper" "$manifest" probe "$up" "$dir/targets.json" "$target"
    rc=$?
    set -e
    printf 'HELPER_EXIT=%s END_TIME=%s\n' "$rc" "$(date -u +%FT%TZ)"
  done
done
"$helper" "$manifest" check
'''.replace('TARGET_JSON',shlex.quote(json.dumps(snapshot)))
    observed=run(script)
    (out/'observations.json').write_text(json.dumps(observed,indent=2)+'\n')
    print(observed['stdout'],flush=True)
    print(observed['stderr'],flush=True)
    if observed['returncode']:
        raise RuntimeError('verification_incomplete')
    text=observed['stdout']
    guards=re.findall(r'^VALID generation=(\d+)$',text,re.M)
    if len(guards)!=2 or guards[0]!=guards[1]:
        raise RuntimeError('generation_changed')
    generation=int(guards[0])
    probes={'cenuta':[],'fornex':[]}
    for match in re.finditer(r'^PROBE upstream=(\w+) target=(\w+) time=([^\n]+)\n(.*?)^HELPER_EXIT=(\d+) END_TIME=([^\n]+)$',text,re.M|re.S):
        up,name,started,raw,rc,ended=match.groups()
        ended_ts=datetime.datetime.fromisoformat(ended.replace('Z','+00:00')).timestamp()
        if ended_ts >= snapshot['expires_unix']:
            raise RuntimeError('expired_during_verification')
        probes[up].append(parse_helper(raw,returncode=int(rc),generation=generation,
            source='10.20.0.1' if up=='fornex' else '10.40.40.2',pinned_ip=targets[name]['ip'],
            expected_http=POLICIES[name]['expected_http'],target=name,family=POLICIES[name]['family']))
    from dataclasses import asdict
    summary={up:dict(assessment=asdict(assess(p,path_verified=True)),probes=[asdict(x) for x in p]) for up,p in probes.items()}
    summary['limitations']='Sequential one-shot probes, not a 10-second scheduler baseline or client application regression.'
    (out/'classification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
