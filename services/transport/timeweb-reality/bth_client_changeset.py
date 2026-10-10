"""Prepare and apply one guarded persistent WireGuard BTH client addition.

The legacy TimeWeb WG writer is intentionally retired.  This tool is limited to
adding one BTH client peer: it validates a fresh verified backup, preserves the
existing BTH recovery peer, and advances the pinned recovery contract through
explicitly allowed intermediate states.  It never prints client credentials.
"""

import argparse
import base64
import copy
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tarfile

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

import run_backup as backup


ROOT = Path(__file__).resolve().parent
CLIENTS = ROOT.parents[2] / ".local/clients"
STAGING = ROOT.parents[2] / ".local/config/changesets"
REMOTE_ROOT = "/var/backups/timeweb-reality/changesets"
WG_CONF = "/opt/wg/config/wg_confs/wg-home.conf"
RECOVERY = "/opt/timeweb-reality/bth-recovery"
CLIENT_NAME = "WG-TW-BTH-S-MacBook.conf"
CLIENT_PATH = CLIENTS / "Sergey" / "MacBook" / CLIENT_NAME
ADDRESS = "10.30.30.6/32"
ADDRESS_V6 = "fd00:30:30::6/128"
ENDPOINT = "94.241.171.65:51830"
DNS = "192.168.88.1"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_private(path: Path, value: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(value)
    path.chmod(0o600)


def keypair() -> tuple[str, str]:
    key = X25519PrivateKey.generate()
    private = base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    public = base64.b64encode(
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    return private, public


def ssh(command: str, *, input_data: bytes | None = None, timeout: int = 100) -> bytes:
    result = subprocess.run(
        backup.ssh_args("timeweb") + [command],
        input=input_data,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("TimeWeb command failed without diagnostic output")
    return result.stdout


def backup_files(run: str) -> dict[str, bytes]:
    folder = backup.STORAGE / "timeweb" / run
    backup.verify("timeweb", run, folder)
    outer = backup.checked_tar((folder / "backup.tar.gz").read_bytes())
    return backup.checked_tar(outer[run + "/host-files.tar"])


def remote_hashes() -> dict[str, str]:
    names = {
        "wg": WG_CONF,
        "recovery_script": RECOVERY + "/bth_recover.sh",
        "recovery_wg": RECOVERY + "/wg.baseline",
        "contract": RECOVERY + "/contract.json",
        "allowed": RECOVERY + "/allowed.baseline",
        "peer_public": RECOVERY + "/peer.public",
        "peer_psk": RECOVERY + "/peer.psk",
    }
    command = "set -euo pipefail; sha256sum " + " ".join(shlex.quote(path) for path in names.values())
    received = ssh(command).decode().splitlines()
    by_path: dict[str, str] = {}
    for line in received:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise RuntimeError("Unexpected TimeWeb checksum response")
        by_path[match.group(2)] = match.group(1)
    return {name: by_path[path] for name, path in names.items()}


def remote_allowed() -> bytes:
    command = (
        "set -euo pipefail; pid=$(docker inspect -f '{{.State.Pid}}' wg-relay); "
        "nsenter -t \"$pid\" -n wg show wg-home allowed-ips | LC_ALL=C sort"
    )
    return ssh(command)


def remote_server_public() -> str:
    command = (
        "set -euo pipefail; pid=$(docker inspect -f '{{.State.Pid}}' wg-relay); "
        "nsenter -t \"$pid\" -n wg show wg-home public-key"
    )
    value = ssh(command).decode().strip()
    if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", value):
        raise RuntimeError("Unexpected WireGuard server public key")
    return value


def build_client(private: str, server_public: str, psk: str) -> bytes:
    return (
        "[Interface]\n"
        f"PrivateKey = {private}\n"
        f"Address = {ADDRESS}, {ADDRESS_V6}\n"
        f"DNS = {DNS}\n\n"
        "[Peer]\n"
        f"PublicKey = {server_public}\n"
        f"PresharedKey = {psk}\n"
        f"Endpoint = {ENDPOINT}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        "PersistentKeepalive = 25\n"
    ).encode()


def build_wg_after(before: bytes, public: str, psk: str) -> bytes:
    text = before.decode()
    for address in (ADDRESS, ADDRESS_V6):
        if address in text:
            raise RuntimeError("Requested BTH address is already persistent")
    return (
        text.rstrip()
        + "\n\n[Peer]\n"
        + f"PublicKey = {public}\n"
        + f"PresharedKey = {psk}\n"
        + f"AllowedIPs = {ADDRESS}, {ADDRESS_V6}\n"
    ).encode()


def with_new_allowed(before: bytes, public: str) -> bytes:
    # `wg show allowed-ips` renders multiple prefixes as separate whitespace
    # fields, while a WireGuard config file uses a comma-separated value.
    line = f"{public}\t{ADDRESS} {ADDRESS_V6}\n".encode()
    if ADDRESS.encode() in before or ADDRESS_V6.encode() in before:
        raise RuntimeError("Requested BTH address is already active")
    return b"".join(sorted(before.splitlines(keepends=True) + [line]))


def transition_contract(old: dict, wg_before: bytes, allowed_before: bytes, wg_after: bytes, allowed_after: bytes) -> tuple[bytes, bytes]:
    if not isinstance(old.get("hashes"), dict):
        raise RuntimeError("BTH contract has no hash map")
    initial_wg = digest(wg_before)
    initial_allowed = digest(allowed_before)
    if old["hashes"].get("wg") != initial_wg or old["hashes"].get("allowed") != initial_allowed:
        raise RuntimeError("Backup BTH contract does not match its captured state")
    states = [
        {"wg": initial_wg, "allowed": initial_allowed},
        {"wg": initial_wg, "allowed": digest(allowed_after)},
        {"wg": digest(wg_after), "allowed": digest(allowed_after)},
    ]
    transition = copy.deepcopy(old)
    transition["wg_allowed_states"] = states
    final = copy.deepcopy(old)
    final["hashes"]["wg"] = digest(wg_after)
    final["hashes"]["allowed"] = digest(allowed_after)
    final.pop("wg_allowed_states", None)
    return (
        (json.dumps(transition, indent=2, sort_keys=True) + "\n").encode(),
        (json.dumps(final, indent=2, sort_keys=True) + "\n").encode(),
    )


def write_manifest(stage: Path, values: dict[str, str]) -> None:
    public = {
        "address": ADDRESS,
        "client": str(CLIENT_PATH),
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files": {path.name: digest(path.read_bytes()) for path in stage.iterdir() if path.is_file()},
        "remote_hashes_before": values,
        "status": "PREPARED",
    }
    write_private(stage / "manifest.json", (json.dumps(public, indent=2, sort_keys=True) + "\n").encode())


def prepare(run: str) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}Z_current-config", run):
        raise ValueError("Invalid verified backup run")
    files = backup_files(run)
    required = [
        "opt/wg/config/wg_confs/wg-home.conf",
        "opt/timeweb-reality/bth-recovery/bth_recover.sh",
        "opt/timeweb-reality/bth-recovery/wg.baseline",
        "opt/timeweb-reality/bth-recovery/contract.json",
        "opt/timeweb-reality/bth-recovery/allowed.baseline",
        "opt/timeweb-reality/bth-recovery/peer.public",
        "opt/timeweb-reality/bth-recovery/peer.psk",
    ]
    if any(path not in files for path in required):
        raise RuntimeError("Verified backup does not contain required BTH artifacts")
    live = remote_hashes()
    expected = {
        "wg": digest(files[required[0]]),
        "recovery_script": digest(files[required[1]]),
        "recovery_wg": digest(files[required[2]]),
        "contract": digest(files[required[3]]),
        "allowed": digest(files[required[4]]),
        "peer_public": digest(files[required[5]]),
        "peer_psk": digest(files[required[6]]),
    }
    if live != expected:
        raise RuntimeError("Live BTH state differs from the verified backup")
    ssh("timeout 35 bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check >/dev/null")
    allowed_before = remote_allowed()
    protected = files[required[5]].strip()
    allowed_without_protected = b"\n".join(
        line for line in allowed_before.splitlines() if not line.startswith(protected + b"\t")
    ) + b"\n"
    contract = json.loads(files[required[3]])
    if digest(allowed_without_protected) != contract["hashes"].get("allowed"):
        raise RuntimeError("Live BTH peer inventory differs from its contract")
    private, public = keypair()
    psk = base64.b64encode(secrets.token_bytes(32)).decode()
    wg_before = files[required[0]]
    wg_after = build_wg_after(wg_before, public, psk)
    allowed_after = with_new_allowed(allowed_without_protected, public)
    contract_transition, contract_after = transition_contract(
        contract, wg_before, allowed_without_protected, wg_after, allowed_after
    )
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stage = STAGING / (stamp + "-macbook-wg-tw-bth")
    stage.mkdir(mode=0o700, parents=True)
    server_public = remote_server_public()
    write_private(stage / "wg.before", wg_before)
    write_private(stage / "wg.after", wg_after)
    write_private(stage / "allowed.before", allowed_without_protected)
    write_private(stage / "allowed.after", allowed_after)
    write_private(stage / "recovery.before.sh", files[required[1]])
    write_private(stage / "recovery.wg.before", files[required[2]])
    write_private(stage / "recovery.after.sh", (ROOT / "bth_recover.sh").read_bytes())
    write_private(stage / "contract.before.json", files[required[3]])
    write_private(stage / "contract.transition.json", contract_transition)
    write_private(stage / "contract.after.json", contract_after)
    write_private(stage / "peer.public", (public + "\n").encode())
    write_private(stage / "peer.psk", (psk + "\n").encode())
    write_private(stage / "client.conf", build_client(private, server_public, psk))
    subprocess.run(["bash", "-n", str(stage / "recovery.after.sh")], check=True, capture_output=True)
    write_manifest(stage, live)
    return stage


def control_script(stage: Path) -> bytes:
    values = {path.name: digest(path.read_bytes()) for path in stage.iterdir() if path.is_file()}
    remote = REMOTE_ROOT + "/" + stage.name
    return f'''#!/bin/bash
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
base={shlex.quote(remote)}
wg_conf={shlex.quote(WG_CONF)}
recovery={shlex.quote(RECOVERY)}
exec 9>/run/lock/reality-stage9.lock
hash() {{ sha256sum "$1" | cut -d ' ' -f 1; }}
need() {{ test "$(hash "$1")" = "$2"; }}
pid=$(docker inspect -f '{{{{.State.Pid}}}}' wg-relay)
ns() {{ nsenter -t "$pid" -n -- "$@"; }}
timeout 35 bash "$recovery/bth_recover.sh" --check >/dev/null
flock -w 20 9
old_timer=false
if systemctl is-active --quiet bth-recovery.timer; then old_timer=true; fi
phase=initial
rollback() {{
  set +e
  systemctl stop bth-recovery.timer
  ns wg set wg-home peer "$(cat "$base/peer.public")" remove 2>/dev/null
  install -m600 "$base/wg.before" "$wg_conf"
  install -m700 "$base/recovery.before.sh" "$recovery/bth_recover.sh"
  install -m600 "$base/recovery.wg.before" "$recovery/wg.baseline"
  install -m600 "$base/allowed.before" "$recovery/allowed.baseline"
  install -m600 "$base/contract.before.json" "$recovery/contract.json"
  flock -u 9
  timeout 35 bash "$recovery/bth_recover.sh" --check >/dev/null
  if [ "$old_timer" = true ]; then systemctl start bth-recovery.timer; fi
}}
on_error() {{ rc=$?; trap - ERR; rollback || true; exit "$rc"; }}
trap on_error ERR
need "$wg_conf" {values['wg.before']}
need "$recovery/bth_recover.sh" {values['recovery.before.sh']}
need "$recovery/wg.baseline" {values['recovery.wg.before']}
need "$recovery/contract.json" {values['contract.before.json']}
need "$recovery/allowed.baseline" {values['allowed.before']}
test ! -e "$wg_conf.new"
systemctl stop bth-recovery.timer
install -m700 "$base/recovery.after.sh" "$recovery/bth_recover.sh"
install -m600 "$base/contract.transition.json" "$recovery/contract.json"
phase=transition
BTH_RECOVERY_LOCK_HELD=1 timeout 35 bash "$recovery/bth_recover.sh" --check >/dev/null
ns wg set wg-home peer "$(cat "$base/peer.public")" preshared-key "$base/peer.psk" allowed-ips {ADDRESS},{ADDRESS_V6}
phase=runtime
BTH_RECOVERY_LOCK_HELD=1 timeout 35 bash "$recovery/bth_recover.sh" --check >/dev/null
install -m600 "$base/wg.after" "$wg_conf"
install -m600 "$base/wg.after" "$recovery/wg.baseline"
phase=persistent
BTH_RECOVERY_LOCK_HELD=1 timeout 35 bash "$recovery/bth_recover.sh" --check >/dev/null
install -m600 "$base/allowed.after" "$recovery/allowed.baseline"
install -m600 "$base/contract.after.json" "$recovery/contract.json"
phase=final
BTH_RECOVERY_LOCK_HELD=1 timeout 35 bash "$recovery/bth_recover.sh" --check >/dev/null
if [ "$old_timer" = true ]; then systemctl start bth-recovery.timer; fi
systemctl is-active --quiet bth-recovery.timer
trap - ERR
echo APPLIED_BTH_CLIENT
'''.encode()


def upload(stage: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for path in stage.iterdir():
            if path.is_file() and path.name != "manifest.json":
                archive.add(path, arcname=path.name)
        control = control_script(stage)
        info = tarfile.TarInfo("control.sh")
        info.mode = 0o700
        info.size = len(control)
        archive.addfile(info, io.BytesIO(control))
    command = (
        "set -euo pipefail; umask 077; mkdir -p " + shlex.quote(REMOTE_ROOT)
        + "; mkdir " + shlex.quote(REMOTE_ROOT + "/" + stage.name)
        + "; tar -xf - -C " + shlex.quote(REMOTE_ROOT + "/" + stage.name)
    )
    ssh(command, input_data=buffer.getvalue())


def apply(stage: Path) -> None:
    upload(stage)
    remote = REMOTE_ROOT + "/" + stage.name
    result = ssh("timeout 150 bash " + shlex.quote(remote + "/control.sh"), timeout=170).decode().strip()
    if result != "APPLIED_BTH_CLIENT":
        raise RuntimeError("BTH client changeset did not confirm completion")
    finalize(stage)


def final_expected(stage: Path) -> dict[str, str]:
    required = ("wg.after", "allowed.after", "recovery.after.sh", "contract.after.json", "peer.public", "client.conf")
    if not stage.is_dir() or any(not (stage / name).is_file() for name in required):
        raise RuntimeError("Changeset does not contain the required artifacts")
    return {
        WG_CONF: digest((stage / "wg.after").read_bytes()),
        RECOVERY + "/wg.baseline": digest((stage / "wg.after").read_bytes()),
        RECOVERY + "/allowed.baseline": digest((stage / "allowed.after").read_bytes()),
        RECOVERY + "/bth_recover.sh": digest((stage / "recovery.after.sh").read_bytes()),
        RECOVERY + "/contract.json": digest((stage / "contract.after.json").read_bytes()),
    }


def finalize(stage: Path) -> None:
    expected = final_expected(stage)
    command = "set -euo pipefail; sha256sum " + " ".join(shlex.quote(path) for path in expected)
    actual = {}
    for line in ssh(command).decode().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise RuntimeError("Unexpected TimeWeb checksum response")
        actual[match.group(2)] = match.group(1)
    if actual != expected:
        raise RuntimeError("Applied BTH changeset does not match its expected persistent state")
    public = (stage / "peer.public").read_text().strip()
    peer_check = (
        "set -euo pipefail; pid=$(docker inspect -f '{{.State.Pid}}' wg-relay); "
        "nsenter -t \"$pid\" -n wg show wg-home allowed-ips | "
        "awk -v k=" + shlex.quote(public) + " '$1 == k && $2 == \"10.30.30.6/32\" && $3 == \"fd00:30:30::6/128\" {found=1} END {exit !found}'; "
        "timeout 35 bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check >/dev/null; "
        "systemctl is-active --quiet bth-recovery.timer"
    )
    ssh(peer_check)
    CLIENT_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_private(CLIENT_PATH, (stage / "client.conf").read_bytes())
    manifest = json.loads((stage / "manifest.json").read_text())
    manifest["status"] = "APPLIED"
    write_private(stage / "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-run", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--finalize", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    if args.finalize:
        stage = args.finalize.resolve()
        finalize(stage)
    else:
        stage = prepare(args.backup_run)
    if args.apply:
        apply(stage)
    print(json.dumps({
        "status": "APPLIED" if args.apply or args.finalize else "PREPARED",
        "address": ADDRESS,
        "client": str(CLIENT_PATH),
        "changeset": str(stage),
    }, indent=2))


if __name__ == "__main__":
    main()
