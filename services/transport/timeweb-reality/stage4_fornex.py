"""Prepare and deploy only the approved Fornex .3 peer; never restart containers."""
if __name__ == "__main__":
    raise SystemExit("RETIRED one-shot stage4_fornex.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from run_backup import ROOT, ssh_args
from prepare_stage3 import PRIVATE

DEST = ROOT / "stage4-fornex"
REMOTE = "/var/backups/timeweb-reality/stage4-fornex"
CONFIG = "/opt/wg/config/wg_confs/wg0.conf"
EXPECTED = "01fe3b6e4b13bb2416d40b45541b650b5ee688d326895e558996e5a810b45cab"
CHAIN = "REALITY_F3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def remote(command, data=None):
    result = subprocess.run(ssh_args("fornex") + [command], input=data,
                            capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode() + result.stdout.decode())
    return result.stdout


def prepare():
    DEST.mkdir(mode=0o700, exist_ok=False)
    original = remote("cat " + CONFIG)
    if sha(original) != EXPECTED:
        raise RuntimeError("Config drift: fresh audit required")
    fragment = (ROOT / "staging/fornex/new-peer.fragment.conf").read_text()
    fields = dict(line.split("=", 1) for line in fragment.splitlines()
                  if "=" in line and not line.lstrip().startswith("#"))
    fields = {k.strip(): v.strip() for k, v in fields.items()}
    assert fields["AllowedIPs"] == "10.20.0.3/32"
    public = fields["PublicKey"]
    hook = "PreUp = /bin/bash /config/reality-f3/guard.sh\n"
    modified = original.decode().replace("[Interface]\n", "[Interface]\n" + hook, 1)
    modified += "\n# BEGIN REALITY-F3 managed peer\n" + fragment.strip() + "\n# END REALITY-F3 managed peer\n"
    denied = [x for x in PRIVATE if ":" not in x] + [
        "94.241.171.65/32", "103.75.126.143/32", "89.252.153.129/32"]
    rules = [f"-A {CHAIN} -d {net} -j DROP" for net in denied]
    rules += [f"-A {CHAIN} -o eth0 -j ACCEPT", f"-A {CHAIN} -j DROP"]
    restore = "*filter\n:" + CHAIN + " - [0:0]\n" + "\n".join(rules) + "\nCOMMIT\n"
    guard = '''#!/bin/bash
set -euo pipefail
cd /config/reality-f3
if iptables -w 5 -S REALITY_F3 >/dev/null 2>&1; then
    diff -u expected.rules <(iptables -w 5 -S REALITY_F3)
else
    iptables-restore -w 5 --noflush < filter.restore
fi
iptables -w 5 -C INPUT -s 10.20.0.3/32 -m comment --comment reality-f3 -j DROP 2>/dev/null || iptables -w 5 -I INPUT 1 -s 10.20.0.3/32 -m comment --comment reality-f3 -j DROP
iptables -w 5 -C FORWARD -i wg0 -s 10.20.0.3/32 -m comment --comment reality-f3 -j REALITY_F3 2>/dev/null || iptables -w 5 -I FORWARD 1 -i wg0 -s 10.20.0.3/32 -m comment --comment reality-f3 -j REALITY_F3
'''
    files = {
        "before.conf": original, "after.conf": modified.encode(),
        "peer.psk": (fields["PresharedKey"] + "\n").encode(),
        "guard.sh": guard.encode(), "filter.restore": restore.encode(),
        "expected.rules": (f"-N {CHAIN}\n" + "\n".join(rules) + "\n").encode(),
    }
    control = '''#!/bin/bash
set -euo pipefail
umask 077
cd /var/backups/timeweb-reality/stage4-fornex
exec 9>/run/lock/reality-f3.lock
flock -n 9
config=/opt/wg/config/wg_confs/wg0.conf
dir=/opt/wg/config/reality-f3
before=BEFORE_HASH
after=AFTER_HASH
peer=PEER_PUBLIC
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
current=$(hash "$config")
case "$1" in
  apply)
    if [ "$current" = "$after" ]; then
      docker exec wg-exit bash /config/reality-f3/guard.sh
      docker exec wg-exit wg show wg0 allowed-ips | grep -F "$peer" | grep -Fx "$peer$(printf '\t')10.20.0.3/32" >/dev/null
      echo ALREADY_APPLIED
      exit 0
    fi
    [ "$current" = "$before" ]
    [ ! -e "$dir" ]
    ! docker exec wg-exit wg show wg0 peers | grep -Fx "$peer"
    ! docker exec wg-exit iptables -S REALITY_F3 >/dev/null 2>&1
    docker exec wg-exit ip route get 1.1.1.1 | grep 'dev eth0' >/dev/null
    cp -p "$config" before.live.conf
    trap 'echo APPLY_FAILED_ROLLING_BACK >&2; bash ./control.sh rollback-unlocked; exit 1' ERR
    mkdir -m 700 "$dir"
    install -m 600 guard.sh filter.restore expected.rules peer.psk "$dir/"
    docker exec wg-exit bash /config/reality-f3/guard.sh
    install -m 600 after.conf "$config.reality-f3-new"
    mv "$config.reality-f3-new" "$config"
    docker exec wg-exit wg set wg0 peer "$peer" preshared-key /config/reality-f3/peer.psk allowed-ips 10.20.0.3/32
    trap - ERR
    echo APPLIED
    ;;
  rollback|rollback-unlocked)
    [ "$current" = "$after" ] || [ "$current" = "$before" ]
    docker exec wg-exit wg set wg0 peer "$peer" remove
    if [ "$current" = "$after" ]; then
      cp -p before.live.conf "$config.reality-f3-old"
      mv "$config.reality-f3-old" "$config"
    fi
    if docker exec wg-exit iptables -C FORWARD -i wg0 -s 10.20.0.3/32 -m comment --comment reality-f3 -j REALITY_F3 2>/dev/null; then
      docker exec wg-exit iptables -w 5 -D FORWARD -i wg0 -s 10.20.0.3/32 -m comment --comment reality-f3 -j REALITY_F3
    fi
    if docker exec wg-exit iptables -C INPUT -s 10.20.0.3/32 -m comment --comment reality-f3 -j DROP 2>/dev/null; then
      docker exec wg-exit iptables -w 5 -D INPUT -s 10.20.0.3/32 -m comment --comment reality-f3 -j DROP
    fi
    if docker exec wg-exit iptables -S REALITY_F3 >/dev/null 2>&1; then
      docker exec wg-exit iptables -w 5 -F REALITY_F3
      docker exec wg-exit iptables -w 5 -X REALITY_F3
    fi
    if [ -d "$dir" ]; then
      rm -f "$dir/guard.sh" "$dir/filter.restore" "$dir/expected.rules" "$dir/peer.psk"
      rmdir "$dir"
    fi
    echo ROLLED_BACK
    ;;
  *) exit 2;;
esac
'''
    # A child rollback inherits the parent's flock descriptor; do not relock it.
    control = control.replace('exec 9>/run/lock/reality-f3.lock\nflock -n 9',
                              'if [ "$1" != rollback-unlocked ]; then\nexec 9>/run/lock/reality-f3.lock\nflock -n 9\nfi')
    control = control.replace("BEFORE_HASH", sha(original)).replace("AFTER_HASH", sha(files["after.conf"])).replace("PEER_PUBLIC", public)
    files["control.sh"] = control.encode()
    for name, content in files.items():
        (DEST / name).write_bytes(content)
    manifest = {"scope": "Fornex only; no restart", "before_sha256": sha(original),
                "after_sha256": sha(files["after.conf"]), "peer_public": public,
                "peer_address": "10.20.0.3/32", "files": {k: sha(v) for k, v in files.items()},
                "denied": denied, "runtime_objects": ["wg0 new peer", "REALITY_F3 chain", "source-specific INPUT and FORWARD jumps"],
                "rollback": "control.sh rollback; refuses unrelated config drift"}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PREPARED; secrets retained in protected System directory")


def upload():
    manifest = json.loads((DEST / "manifest.json").read_text())
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, expected in manifest["files"].items():
            assert sha((DEST / name).read_bytes()) == expected
            archive.add(DEST / name, arcname=name)
    remote("set -e; umask 077; mkdir " + REMOTE + "; tar -xf - -C " + REMOTE, stream.getvalue())
    print("UPLOADED; not applied")


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "upload", "apply", "rollback"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "upload":
        upload()
    else:
        output = remote("bash " + REMOTE + "/control.sh " + args.action)
        print(output.decode())
