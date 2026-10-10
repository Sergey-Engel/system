"""Install only the reviewed legacy WG-helper safety gate, never network changes."""
import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import subprocess

import run_backup as backup

D = backup.ROOT / "maintenance-wg"
TARGET = "opt/wg-router/commands.sh"


def payload(before, after, content, run):
    # Values are generated locally; only SHA256 and a validated backup run enter shell syntax.
    encoded = base64.b64encode(content).decode()
    return f'''set -euo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
exec 8>/var/backups/timeweb-reality/.backup.lock
flock -n 8
target=/{TARGET}
test -f "$target" && test ! -L "$target"
actual=$(sha256sum "$target" | cut -d ' ' -f 1)
if [ "$actual" = {after} ]; then echo ALREADY_APPLIED; exit 0; fi
test "$actual" = {before}
bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check >/dev/null
dest=/var/backups/timeweb-reality/{run}-maintenance-helper
mkdir -m700 "$dest"
cp -a "$target" "$dest/commands.before.sh"
candidate=$(mktemp /opt/wg-router/.commands.XXXXXXXX)
trap 'rm -f -- "$candidate"' EXIT
printf '%s' '{encoded}' | base64 -d > "$candidate"
test "$(sha256sum "$candidate" | cut -d ' ' -f 1)" = {after}
bash -n "$candidate"
chmod --reference="$target" "$candidate"
chown --reference="$target" "$candidate"
test "$(sha256sum "$target" | cut -d ' ' -f 1)" = {before}
mv -T "$candidate" "$target"
if ! bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check >/dev/null; then
    cp -a "$dest/commands.before.sh" "$candidate"
    mv -T "$candidate" "$target"
    echo HELPER_ROLLED_BACK >&2
    exit 1
fi
test "$(sha256sum "$target" | cut -d ' ' -f 1)" = {after}
echo HELPER_PATCHED_NO_NETWORK_CHANGES
'''.encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backup-run", required=True)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    import re
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}Z_current-config", args.backup_run):
        p.error("Invalid backup run")
    os.umask(0o077)
    folder = backup.STORAGE / "timeweb" / args.backup_run
    backup.verify("timeweb", args.backup_run, folder)
    outer = backup.checked_tar((folder / "backup.tar.gz").read_bytes())
    original = backup.checked_tar(outer[args.backup_run + "/host-files.tar"])[TARGET]
    current = (D / "commands.sh").read_bytes()
    before, after = backup.digest(original), backup.digest(current)
    report = {"target": "/" + TARGET, "before_sha256": before, "after_sha256": after,
              "backup_run": args.backup_run, "network_mutations": False, "status": "PLAN"}
    if args.apply:
        result = subprocess.run(backup.ssh_args("timeweb") + ["timeout 90 bash -s"],
                                input=payload(before, after, current, args.backup_run),
                                capture_output=True, timeout=110)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (D / (stamp + ".stderr")).write_bytes(result.stderr)
        report["status"] = "APPLIED" if result.returncode == 0 and result.stdout.strip() in (
            b"ALREADY_APPLIED", b"HELPER_PATCHED_NO_NETWORK_CHANGES") else "FAILED"
        report["returncode"] = result.returncode
        (D / (stamp + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if report["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
