"""Approved TimeWeb REALITY deployment. All generated secrets stay in System."""
if __name__ == "__main__":
    raise SystemExit("RETIRED one-shot stage56.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from run_backup import ROOT, ssh_args

DEST = ROOT / "stage56-timeweb"
REMOTE = "/var/backups/timeweb-reality/stage56"


def ssh(command, data=None, timeout=90):
    result = subprocess.run(ssh_args("timeweb") + [command], input=data,
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode() + result.stdout.decode())
    return result.stdout


def prepare():
    DEST.mkdir(mode=0o700, exist_ok=False)
    config = json.loads((ROOT / "staging/fornex/server.loopback.json").read_text())
    assert config["inbounds"][0]["streamSettings"]["realitySettings"]["target"] == "23.12.158.97:443"
    config["inbounds"][0]["streamSettings"]["realitySettings"].update(target="23.12.156.37:443", serverNames=["www.apple.com"])
    (DEST / "loopback.json").write_text(json.dumps(config, indent=2) + "\n")
    config["inbounds"][0]["listen"] = "94.241.171.65"
    (DEST / "public.json").write_text(json.dumps(config, indent=2) + "\n")
    client = json.loads((ROOT / "staging/fornex/client-macbook.json").read_text())
    client["inbounds"][0]["port"] = 10843
    client["outbounds"][1]["settings"]["vnext"][0]["address"] = "127.0.0.1"
    client["outbounds"][1]["streamSettings"]["realitySettings"]["serverName"] = "www.apple.com"
    (DEST / "test-client.json").write_text(json.dumps(client, indent=2) + "\n")
    firewall = '''table inet reality_fornex {
 chain guard {
  ip daddr 103.75.126.143 udp dport 51821 counter accept
  ip daddr 23.12.156.37 tcp dport 443 counter accept
  tcp sport 443 ct state established ct direction reply counter accept
  counter drop
 }
 chain output {
  type filter hook output priority 0; policy accept;
  meta skuid 10001 jump guard
 }
}
'''
    (DEST / "guard.nft").write_text(firewall)
    (DEST / "guard.sh").write_text('''#!/bin/bash
set -euo pipefail
if nft list table inet reality_fornex >/dev/null 2>&1; then
 diff -u /opt/timeweb-reality/guard.expected <(nft -s list table inet reality_fornex)
else
 nft -f /opt/timeweb-reality/guard.nft
 diff -u /opt/timeweb-reality/guard.expected <(nft -s list table inet reality_fornex)
fi
''')
    unit = '''[Unit]
Description=TimeWeb REALITY Fornex isolated transport
After=network-online.target nftables.service
Wants=network-online.target

[Service]
Type=simple
User=reality-fornex
Group=reality-fornex
ExecStartPre=+/bin/bash /opt/timeweb-reality/guard.sh
ExecStart=/opt/timeweb-reality/xray run -config /opt/timeweb-reality/config.json
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
MemoryMax=256M
CPUQuota=50%
TasksMax=64
LimitNOFILE=8192
StandardOutput=journal
StandardError=journal
LogRateLimitIntervalSec=30s
LogRateLimitBurst=20

[Install]
WantedBy=multi-user.target
'''
    (DEST / "xray-timeweb-reality.service").write_text(unit)
    install = '''#!/bin/bash
set -euo pipefail
umask 077
cd /var/backups/timeweb-reality/stage56
test ! -e /opt/timeweb-reality
test ! -e /etc/systemd/system/xray-timeweb-reality.service
! getent passwd 10001
! getent passwd reality-fornex
! getent group 10001
! nft list table inet reality_fornex >/dev/null 2>&1
test -z "$(ss -H -lnt 'sport = :443')"
nft -c -f guard.nft
systemd-analyze verify ./xray-timeweb-reality.service
groupadd -g 10001 reality-fornex
useradd -u 10001 -g reality-fornex -M -d /nonexistent -s /usr/sbin/nologin reality-fornex
install -d -m 750 -o root -g reality-fornex /opt/timeweb-reality
install -m 755 xray /opt/timeweb-reality/xray
install -m 600 guard.sh guard.nft /opt/timeweb-reality/
install -m 640 -o root -g reality-fornex loopback.json /opt/timeweb-reality/config.json
nft -f guard.nft
nft -s list table inet reality_fornex > /opt/timeweb-reality/guard.expected
install -m 644 xray-timeweb-reality.service /etc/systemd/system/xray-timeweb-reality.service
systemctl daemon-reload
runuser -u reality-fornex -- /opt/timeweb-reality/xray run -test -config /opt/timeweb-reality/config.json
systemctl start xray-timeweb-reality.service
systemctl is-active xray-timeweb-reality.service
'''
    # systemd-analyze verify checks that ExecStart exists, so do it after staging.
    install = install.replace('systemd-analyze verify ./xray-timeweb-reality.service\n', '')
    install = install.replace('systemctl daemon-reload', 'systemd-analyze verify /etc/systemd/system/xray-timeweb-reality.service\nsystemctl daemon-reload')
    (DEST / "install.sh").write_text(install)
    rollback = '''#!/bin/bash
set -euo pipefail
systemctl disable --now xray-timeweb-reality.service || true
if systemctl is-active --quiet xray-timeweb-reality.service; then exit 1; fi
if pgrep -u 10001 >/dev/null; then echo "UID still has processes; refusing guard removal"; exit 1; fi
if nft list table inet reality_fornex >/dev/null 2>&1; then nft delete table inet reality_fornex; fi
echo "Transport stopped; owned files and reserved UID retained for audit. No old service changed."
'''
    (DEST / "rollback.sh").write_text(rollback)
    binary = ROOT / "vendor/amd64/xray"
    expected = json.loads((ROOT / "vendor/artifacts.json").read_text())["amd64"]["binary_sha256"]
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == expected
    manifest = {"scope": "TimeWeb host new UID10001/service/inet reality_fornex only",
                "backup": "2026-09-12T1736Z_pre-reality", "binary_sha256": expected,
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.iterdir()},
                "rollback": "rollback.sh stops only new service before removing only owned table; UID/files retained"}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PREPARED")


def upload():
    manifest = json.loads((DEST / "manifest.json").read_text())
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, expected in manifest["files"].items():
            assert hashlib.sha256((DEST / name).read_bytes()).hexdigest() == expected
            archive.add(DEST / name, arcname=name)
        archive.add(ROOT / "vendor/amd64/xray", arcname="xray")
    ssh("set -e; umask 077; mkdir " + REMOTE + "; tar -xf - -C " + REMOTE, stream.getvalue())
    print("UPLOADED")


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "upload", "install", "rollback", "public"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "upload":
        upload()
    elif args.action in ("install", "rollback"):
        try:
            print(ssh("bash " + REMOTE + "/" + args.action + ".sh").decode())
        except Exception:
            if args.action == "install":
                print(ssh("bash " + REMOTE + "/rollback.sh").decode())
            raise
    else:
        print(ssh("set -e; install -m 640 -o root -g reality-fornex " + REMOTE + "/public.json /opt/timeweb-reality/config.json; systemctl restart xray-timeweb-reality.service; systemctl is-active xray-timeweb-reality.service").decode())
