#!/usr/bin/env python3
"""Historical stage helpers. Never deploy a dated stage to the current fleet."""

from pathlib import Path
import sys
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

os.umask(0o077)
ROOT = Path(__file__).resolve().parent
STAMP = "20260911-guards"
EVIDENCE = ROOT.parents[2] / ".local/evidence" / STAMP
SSH = ["ssh", "-i", str(Path(__file__).resolve().parents[3] / '.local/ssh/codex_timeweb_audit_20260628'),
       "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
       "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
       "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=5",
       "-o", "ServerAliveCountMax=2", "root@94.241.171.65"]

def run(label, script, timeout=60):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / (label + ".json")
    if path.exists():
        raise RuntimeError(f"Refusing evidence overwrite: {path}")
    result = subprocess.run(SSH + ["bash -s"], input=script, text=True,
                            capture_output=True, timeout=timeout)
    record = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"{label}: exit {result.returncode}")
    return result.stdout

AUDIT = r'''set -Eeuo pipefail
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
ns() { nsenter -t "$pid" -n "$@"; }
jq -n \
  --arg time "$(date -u +%FT%TZ)" \
  --arg boot "$(cat /proc/sys/kernel/random/boot_id)" \
  --arg ns "$(readlink /proc/$pid/ns/net)" \
  --arg start "$(awk '{print $22}' /proc/$pid/stat)" \
  --argjson container "$(docker inspect wg-relay | jq '.[0] | {Id,State:{Pid:.State.Pid,StartedAt:.State.StartedAt,Running:.State.Running}}')" \
  --argjson rules "$(ns ip -j -4 rule show)" \
  --argjson routes "$(ns ip -j -4 route show table all)" \
  --argjson links "$(ns ip -j -4 address show | jq '[.[]|{ifindex,ifname,flags,mtu,addr_info:[.addr_info[]|{local,prefixlen}]}]')" \
  --argjson host_rules "$(ip -j -4 rule show)" \
  --argjson host_routes "$(ip -j -4 route show table all)" \
  --arg filter "$(ns iptables -S)" --arg nat "$(ns iptables -t nat -S)" \
  --arg mangle "$(ns iptables -t mangle -S)" \
  --arg sockets "$(ns ss -lntup)" \
  --arg peers_fornex "$(ns wg show wg1 allowed-ips)" \
  --arg peers_cenuta "$(ns wg show wg-up-cenuta allowed-ips)" \
  '{time:$time,target:{boot:$boot,namespace:$ns,start:$start,container:$container},
    rules:$rules,routes:$routes,links:$links,host_rules:$host_rules,host_routes:$host_routes,
    filter:$filter,nat:$nat,mangle:$mangle,sockets:$sockets,
    peers:{fornex:$peers_fornex,cenuta:$peers_cenuta}}'
'''

BACKUP = r'''set -Eeuo pipefail
umask 077
base=/root/vpn-guard-backups
mkdir -p "$base"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dir="$base/$stamp"
mkdir "$dir"
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
mkdir "$dir/runtime"
docker inspect wg-relay > "$dir/runtime/docker-inspect.json"
docker image inspect "$(docker inspect -f '{{.Image}}' wg-relay)" > "$dir/runtime/image-inspect.json"
nsenter -t "$pid" -n ip -4 rule save > "$dir/runtime/rules.save"
nsenter -t "$pid" -n ip -4 route save table all > "$dir/runtime/routes.save"
nsenter -t "$pid" -n ip -j -4 rule show > "$dir/runtime/rules.json"
nsenter -t "$pid" -n ip -j -4 route show table all > "$dir/runtime/routes.json"
nsenter -t "$pid" -n iptables-save > "$dir/runtime/iptables.save"
iptables-save > "$dir/runtime/host-iptables.save"
for interface in $(nsenter -t "$pid" -n wg show interfaces); do
    nsenter -t "$pid" -n wg showconf "$interface" > "$dir/runtime/$interface.conf"
done
paths=(opt/wg opt/wg-router etc/wireguard etc/systemd/system etc/cron.d etc/crontab usr/local/bin/wg-status)
for path in etc/docker var/spool/cron/crontabs etc/rc.local; do
    if test -e "/$path"; then paths+=("$path"); fi
done
cd /
find "${paths[@]}" -type f ! -path 'opt/wg-router/backups/*' ! -path 'opt/wg-router/logs/*' -print0 | sort -z | xargs -0 sha256sum > "$dir/files.before.sha256"
tar --acls --xattrs --numeric-owner --exclude='opt/wg-router/backups' --exclude='opt/wg-router/logs' -czf "$dir/config.tar.gz" "${paths[@]}"
sha256sum -c "$dir/files.before.sha256" > "$dir/source-check.txt"
mkdir "$dir/restore-test"
tar -xzf "$dir/config.tar.gz" -C "$dir/restore-test"
cd "$dir/restore-test"
sha256sum -c "$dir/files.before.sha256" > "$dir/restore-check.txt"
count=$(wc -l < "$dir/files.before.sha256")
cd "$dir"
tar -czf "$base/$stamp.tar.gz" config.tar.gz files.before.sha256 source-check.txt restore-check.txt runtime
sha256sum "$base/$stamp.tar.gz"
printf 'BACKUP=%s/%s.tar.gz FILES_VERIFIED=%s\n' "$base" "$stamp" "$count"
'''

if __name__ == "__main__":
    action = sys.argv[1]
    if action == "audit":
        run(sys.argv[2], AUDIT)
    elif action == "backup":
        output = run("backup", BACKUP, 90)
        remote = next(line.split()[0].split("=", 1)[1] for line in output.splitlines() if line.startswith("BACKUP="))
        expected = next(line.split()[0] for line in output.splitlines() if line.endswith(remote) and not line.startswith("BACKUP="))
        destination = Path(str(Path(__file__).resolve().parents[3] / '.local/backups')) / Path(remote).stem.replace(".tar", "")
        destination.mkdir(parents=True, exist_ok=False)
        archive = destination / "timeweb-pre-uplink-guards.tar.gz"
        with archive.open("xb") as stream:
            subprocess.run(SSH + [f"cat {remote}"], stdout=stream, check=True, timeout=60)
        actual = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
        assert actual == expected, (actual, expected)
        (destination / "SHA256SUMS").write_text(f"{actual}  {archive.name}\n")
        print(f"LOCAL_BACKUP={archive}\nSHA256={actual}")
    elif action == "script":
        run(sys.argv[2], Path(sys.argv[3]).read_text(), int(sys.argv[4]) if len(sys.argv)>4 else 90)
    else:
        raise SystemExit("audit <label> | backup | script <label> <file> [timeout]")
