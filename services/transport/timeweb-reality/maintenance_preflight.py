#!/usr/bin/env python3
"""Check-only TimeWeb maintenance evidence; NEVER authorization for WG changes.

Only run_backup.ROOT/ssh_args are reused, not deployment/contract generators.
The remote helper is invoked with bash and --check after byte-level verification.
Its existing check path uses a temporary /run directory and a lock, but does not
change peers, firewall, units, persistent files, or the recovery contract. This
snapshot is not a lifecycle lock or a full RPDB update plan. Contract renewal,
signing, restarts, WG changes and automatic remediation are deliberately absent.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import run_backup


ROOT = run_backup.PRIVATE / "config/maintenance-reference"
REMOTE = "/opt/timeweb-reality"
RECOVERY = REMOTE + "/bth-recovery"
WARNING = (
    "CHECK ONLY; not authorization for WG changes. The full RPDB recovery "
    "contract requires a separately planned update; never renew/sign drift."
)
CONTRACT_FILES = {
    "wg": "wg.baseline", "xray": "xray.baseline", "rules": "rules.baseline",
    "routes": "routes.baseline", "allowed": "allowed.baseline",
    "hostguard": "hostguard.baseline", "rules_with_monitoring": "rules.monitoring.baseline", "guard": "relay.nft",
    "expected": "relay.expected", "public": "peer.public", "psk": "peer.psk",
}
# These were staged with the contract. Later local reports and deployment/test
# scripts in bth-recovery-release are history, not required runtime files.
RELEASE_FILES = (
    "bth_recover.sh", "bth-recovery.service", "bth-recovery.timer", "contract.json",
    *CONTRACT_FILES.values(),
)
UNITS = (
    "xray-timeweb-reality.service", "bth-recovery.service", "bth-recovery.timer",
)
FILE_TARGETS = {
    "xray_config": ("stage9-bth/config.after", REMOTE + "/config.json"),
    "host_guard": ("stage9-bth/guard.nft.after", REMOTE + "/guard.nft"),
    "host_guard_expected": (
        "stage9-bth/guard.expected.after", REMOTE + "/guard.expected"),
    "xray_unit": (
        "stage56-timeweb/xray-timeweb-reality.service",
        "/etc/systemd/system/xray-timeweb-reality.service"),
    **{ "recovery/" + name: ("bth-recovery-release/" + name, RECOVERY + "/" + name)
        for name in RELEASE_FILES },
    **{ "installed/" + name: (
            "bth-recovery-release/" + name, "/etc/systemd/system/" + name)
        for name in UNITS[1:] },
}
REMOTE_CHECKS = (
    "namespace_pinned", "namespace_before_helper", "bth_helper_check",
    "namespace_after_helper", "namespace_final", "unit_generation_stable",
    *(phase + ":" + name for phase in ("before", "after") for name in FILE_TARGETS),
    *(phase + ":" + unit for phase in ("before", "after") for unit in UNITS),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_reference(root):
    """Read only the fixed master inventory; never expose file contents/errors."""
    contents = {}
    for local, _ in FILE_TARGETS.values():
        path = root / local
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 1048576:
            raise ValueError("Invalid local reference")
        contents[local] = path.read_bytes()
    release = "bth-recovery-release/"
    contract = json.loads(contents[release + "contract.json"])
    if not isinstance(contract, dict) or not isinstance(contract.get("hashes"), dict):
        raise ValueError("Invalid contract")
    for key, name in CONTRACT_FILES.items():
        if contract["hashes"].get(key) != sha256(contents[release + name]):
            raise ValueError("Local contract mismatch")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", contract.get("image", "")):
        raise ValueError("Invalid image identity")
    config = contents["stage9-bth/config.after"]
    if not isinstance(json.loads(config), dict) or config != contents[release + "xray.baseline"]:
        raise ValueError("Local master mismatch")
    if contents["stage9-bth/guard.expected.after"] != contents[release + "hostguard.baseline"]:
        raise ValueError("Local host guard mismatch")
    if (root / "bth_recover.sh").read_bytes() != contents[release + "bth_recover.sh"]:
        raise ValueError("Local helper mismatch")
    return {name: sha256(contents[local]) for name, (local, _) in FILE_TARGETS.items()}


# No remote file capture or raw command output is returned. All evidence crossing
# SSH is a fixed check ID and an enum, parsed again against a strict allowlist.
REMOTE_SCRIPT = r'''set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C SYSTEMD_COLORS=0
unset BASH_ENV ENV CDPATH
exec 2>/dev/null
failed=0
emit() { printf '%s\t%s\n' "$1" "$2"; if [ "$2" != PASSED ]; then failed=1; fi; }
hash_matches() {
    [ -f "$2" ] && [ ! -L "$2" ] || return 1
    local actual
    actual=$(sha256sum -- "$2") || return 1
    [ "${actual%% *}" = "$1" ]
}
files() {
    local phase=$1 name expected path
    while IFS=$'\t' read -r name expected path; do
        if hash_matches "$expected" "$path"; then emit "$phase:$name" PASSED
        else emit "$phase:$name" FAILED; fi
    done <<'PREFLIGHT_FILES'
@FILES@
PREFLIGHT_FILES
}
identity() {
    docker inspect --type container wg-relay | jq -er '
      .[0] | select(.State.Running == true and .State.Pid > 1) |
      [.Id, .State.Pid, .State.StartedAt, .Image] | @tsv'
}
pin_namespace() {
    original=$(identity) || return 1
    local cid started image
    IFS=$'\t' read -r cid pid started image <<<"$original"
    [[ "$cid" =~ ^[0-9a-f]{64}$ && "$pid" =~ ^[0-9]+$ && "$pid" -gt 1 ]] || return 1
    [[ "$image" =~ ^sha256:[0-9a-f]{64}$ && -n "$started" ]] || return 1
    exec 3<"/proc/$pid/ns/net" || return 1
    ns_path="/proc/$$/fd/3"
    inode=$(readlink "$ns_path") || return 1
    [[ "$inode" =~ ^net:\[[0-9]+\]$ ]] || return 1
    fresh_namespace
}
fresh_namespace() {
    [ "$(identity)" = "$original" ] || return 1
    [ "$(readlink "/proc/$pid/ns/net")" = "$inode" ] || return 1
    [ "$(readlink "$ns_path")" = "$inode" ] || return 1
    nsenter --net="$ns_path" -- ip -j link show dev wg-home >/dev/null || return 1
}
property() {
    local key value
    while IFS='=' read -r key value; do
        if [ "$key" = "$1" ]; then printf '%s' "$value"; return 0; fi
    done <<<"$unit_state"
    return 1
}
unit_check() {
    local unit=$1 active=$2 sub=$3 enabled=$4 type=$5
    [ "$(property LoadState)" = loaded ] &&
    [ "$(property ActiveState)" = "$active" ] &&
    [ "$(property SubState)" = "$sub" ] &&
    [ "$(property UnitFileState)" = "$enabled" ] &&
    [ "$(property FragmentPath)" = "/etc/systemd/system/$unit" ] &&
    [ "$(property DropInPaths)" = '' ] &&
    [ "$(property NeedDaemonReload)" = no ] || return 1
    if [ "$type" != timer ]; then
        [ "$(property Type)" = "$type" ] &&
        [ "$(property Result)" = success ] &&
        [ "$(property ExecMainStatus)" = 0 ] || return 1
    fi
    if [ "$type" = simple ]; then
        local mainpid
        mainpid=$(property MainPID) || return 1
        [[ "$mainpid" =~ ^[0-9]+$ && "$mainpid" -gt 1 ]] || return 1
    fi
}
units() {
    local phase=$1 unit active sub enabled type
    while read -r unit active sub enabled type; do
        if unit_state=$(systemctl show --no-pager \
          --property=LoadState,ActiveState,SubState,UnitFileState,FragmentPath,DropInPaths,NeedDaemonReload,Type,Result,ExecMainStatus,MainPID,ExecMainStartTimestampMonotonic,NRestarts "$unit") &&
          unit_check "$unit" "$active" "$sub" "$enabled" "$type"; then
            emit "$phase:$unit" PASSED
        else emit "$phase:$unit" FAILED; fi
        if [ "$type" = simple ]; then
            generation="$(property MainPID):$(property ExecMainStartTimestampMonotonic):$(property NRestarts)"
            if [ "$phase" = before ]; then unit_generation=$generation
            elif [ "$generation" = "$unit_generation" ]; then emit unit_generation_stable PASSED
            else emit unit_generation_stable FAILED; fi
        fi
    done <<'PREFLIGHT_UNITS'
xray-timeweb-reality.service active running enabled simple
bth-recovery.service inactive dead static oneshot
bth-recovery.timer active waiting enabled timer
PREFLIGHT_UNITS
}
files before
units before
original= pid= ns_path= inode= unit_generation=${unit_generation:-}
if pin_namespace; then emit namespace_pinned PASSED
else emit namespace_pinned FAILED; fi
if [ "$failed" = 0 ] && fresh_namespace; then emit namespace_before_helper PASSED
else emit namespace_before_helper FAILED; fi
# Never execute a drifted helper or pass a mode that can restore/remove a peer.
if [ "$failed" = 0 ]; then
    if result=$(timeout --signal=TERM --kill-after=2s 35s bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check) &&
       [ "$result" = BTH_CONTRACT_VALID ]; then emit bth_helper_check PASSED
    else emit bth_helper_check FAILED; fi
else emit bth_helper_check SKIPPED; fi
if [ -n "$ns_path" ] && fresh_namespace; then emit namespace_after_helper PASSED
else emit namespace_after_helper FAILED; fi
files after
units after
if [ -n "$ns_path" ] && fresh_namespace; then emit namespace_final PASSED
else emit namespace_final FAILED; fi
exit "$failed"
'''


def remote_script(hashes):
    rows = []
    for name, (_, remote) in FILE_TARGETS.items():
        digest = hashes[name]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid reference digest")
        rows.append("\t".join((name, digest, remote)))
    return REMOTE_SCRIPT.replace("@FILES@", "\n".join(rows)).encode("ascii")


def parse_checks(output):
    """Reject banners, duplicates, omissions and arbitrary remote error text."""
    if not isinstance(output, bytes) or len(output) > 32768:
        raise ValueError("Invalid remote evidence")
    checks = {}
    for line in output.decode("ascii").splitlines():
        name, status = line.split("\t")
        if name not in REMOTE_CHECKS or name in checks or status not in {"PASSED", "FAILED", "SKIPPED"}:
            raise ValueError("Invalid remote evidence")
        checks[name] = status
    if set(checks) != set(REMOTE_CHECKS):
        raise ValueError("Incomplete remote evidence")
    return checks


def preflight(root=ROOT, timeout=90):
    report = {
        "schema_version": 1, "status": "FAILED", "host": "timeweb",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "check-only", "wg_changes_authorized": False,
        "contract_update_authorized": False, "warning": WARNING,
        "scope": "stage9-bth master, recovery release, system units, fresh pinned namespace and BTH --check",
        "limits": "point-in-time evidence; no lifecycle lock, full restore drill or client acceptance",
        "helper_ephemeral_io": "existing --check uses /run temporary files and lock only",
        "checks": {},
    }
    checks = report["checks"]
    if type(timeout) is not int or not 15 <= timeout <= 120:
        checks["timeout_bound"] = "FAILED"
        return report
    try:
        hashes = load_reference(Path(root))
        payload = remote_script(hashes)
    except (OSError, ValueError, TypeError, KeyError):
        checks["local_reference"] = "FAILED"
        return report
    checks["local_reference"] = "PASSED"
    report["reference"] = {
        "xray_config_sha256": hashes["xray_config"],
        "recovery_contract_sha256": hashes["recovery/contract.json"],
        "inventory_sha256": sha256(json.dumps(hashes, sort_keys=True).encode("ascii")),
    }
    try:
        command = f"timeout --signal=TERM --kill-after=3s {timeout - 5}s bash --noprofile --norc -s"
        result = subprocess.run(run_backup.ssh_args("timeweb") + [command],
                                input=payload, capture_output=True, timeout=timeout,
                                check=False)
    except subprocess.TimeoutExpired:
        checks["ssh_timeout"] = "FAILED"
        return report
    except (OSError, ValueError, subprocess.SubprocessError):
        checks["ssh_execution"] = "FAILED"
        return report
    checks["ssh_exit"] = "PASSED" if result.returncode == 0 else "FAILED"
    try:
        checks.update(parse_checks(result.stdout))
        checks["evidence_complete"] = "PASSED"
    except (ValueError, UnicodeError):
        checks["evidence_complete"] = "FAILED"
    try:
        checks["local_reference_stable"] = "PASSED" if load_reference(Path(root)) == hashes else "FAILED"
    except (OSError, ValueError, TypeError, KeyError):
        checks["local_reference_stable"] = "FAILED"
    if all(value == "PASSED" for value in checks.values()):
        report["status"] = "PASSED"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=WARNING)
    parser.add_argument("--check", action="store_true", required=True,
                        help="Only inspect; never authorize or perform maintenance")
    parser.add_argument("--timeout", type=int, default=90, choices=range(15, 121),
                        metavar="15..120", help="Total SSH timeout in seconds (default: 90)")
    parser.add_argument("--output", type=Path, help="New sanitized JSON artifact; existing files are never overwritten")
    args = parser.parse_args(argv)
    output = args.output or run_backup.PRIVATE / "evidence" / (
        "maintenance-preflight-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid.uuid4().hex[:8] + ".json")
    # Reserve output before SSH, refuse symlinks/overwrites, and never chmod inputs.
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print("FAILED: cannot create new JSON artifact. " + WARNING, file=sys.stderr)
        return 1
    report = preflight(timeout=args.timeout)
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    try:
        with os.fdopen(fd, "w", encoding="ascii") as artifact:
            artifact.write(data)
    except OSError:
        print("FAILED: cannot write JSON artifact. " + WARNING, file=sys.stderr)
        return 1
    print(data, end="")
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
