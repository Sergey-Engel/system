#!/usr/bin/env python3
"""Back up local System configuration masters, never deploy or restore runtime.

Default: one fresh read-only RouterOS text-export attempt, bounded to 30 seconds
including TimeWeb identity checks. --skip-router explicitly produces PARTIAL.
No remote files, binary backups, contract changes, restarts or remediation.
Existing Mikrotik/current files are dated supplemental evidence, NOT fresh.
Archives contain secrets. Keep the entire output private; permissions are not
encryption. Verification restores inert regular-file bytes in a temporary local
directory; it never executes scripts or uses tar.extract/extractall.
"""

import argparse
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

import run_backup


SYSTEM = run_backup.REPOSITORY
MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 50000
MAX_ROUTER_BYTES = 16 * 1024 * 1024
SCOPES = ("services", "config", "scripts", "docs", ".agents", "README.md", "AGENTS.md",
          "requirements.txt", "pytest.ini", ".gitignore", ".local/clients", ".local/config", ".local/ssh", ".local/secrets.json")
CACHES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache"}
REQUIRED = (
    "config/inventory/clients.json", ".local/secrets.json",
    "services/transport/timeweb-reality/backup_readonly.sh",
    "services/monitoring/vpn-connectivity/compose.yaml",
)


class BackupError(Exception):
    """Only fixed, non-secret reason codes may be placed in reports."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def metadata(info):
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns,
            "ctime_ns": info.st_ctime_ns, "source_mode": stat.S_IMODE(info.st_mode),
            "device": info.st_dev, "inode": info.st_ino}


def open_directory(path, create=False):
    """Walk every ancestor using directory FDs; never follow a symlink."""
    path = Path(path).absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if part in {".", ".."}:
                raise BackupError("unsafe_path")
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, 0o700, dir_fd=fd)
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def open_source(system, relative):
    parts = PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or ".." in parts:
        raise BackupError("unsafe_source_path")
    fd = open_directory(Path(system).joinpath(*parts[:-1]))
    try:
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)
    with os.fdopen(file_fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise BackupError("non_regular_source")
        yield stream


def hash_stream(stream, limit):
    hasher, total = hashlib.sha256(), 0
    while chunk := stream.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise BackupError("size_limit")
        hasher.update(chunk)
    return hasher.hexdigest(), total


def exclusion(relative, info):
    path = PurePosixPath(relative)
    if path.name in CACHES or path.name == ".DS_Store" or path.suffix in {".pyc", ".pyo"}:
        return "cache"
    if relative in {"services/transport/timeweb-reality/vendor/" + arch + "/xray"
                    for arch in ("amd64", "arm64", "macos-arm64")}:
        return "vendor_binary"
    if (relative.startswith("services/transport/") and info.st_size > 1024 * 1024
            and path.suffix in {".log", ".pcap", ".pcapng", ".body"}):
        return "large_captured_log_or_payload"
    return None


def archive_name(relative):
    name = "supplemental/" + relative if relative.startswith("Mikrotik/current/") else relative
    return name.replace("%", "%25").replace("\\", "%5C")


def snapshot(system, max_bytes=MAX_BYTES):
    """Inventory/hash all selected files, refusing links, devices and drift."""
    if not all((Path(system) / name).is_file() for name in REQUIRED):
        raise BackupError("missing_required_master")
    files, excluded = {}, []
    total, nodes = 0, 0

    def visit(fd, relative):
        nonlocal total, nodes
        for name in sorted(os.listdir(fd)):
            nodes += 1
            if nodes > MAX_FILES:
                raise BackupError("file_count_limit")
            escaped_unit = (relative.startswith(".local/config/hosts/") and
                            relative.endswith("/host/etc/systemd/system") and
                            re.fullmatch(r"[\w@.-]+(?:\\x[0-9a-fA-F]{2}[\w@.-]*)+\.(?:mount|service)", name))
            if ("\\" in name and not escaped_unit) or any(ord(char) < 32 for char in name):
                raise BackupError("unsafe_filename")
            source = relative + "/" + name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise BackupError("symlink_or_special_source")
            reason = exclusion(source, info)
            if reason:
                excluded.append({"source": source, "reason": reason, "size": info.st_size})
                continue
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    visit(child, source)
                finally:
                    os.close(child)
                continue
            total += info.st_size
            if total > max_bytes:
                raise BackupError("size_limit")
            with open_source(system, source) as stream:
                before = metadata(os.fstat(stream.fileno()))
                if before != metadata(info):
                    raise BackupError("source_changed")
                checksum, size = hash_stream(stream, info.st_size)
                if size != info.st_size or metadata(os.fstat(stream.fileno())) != before:
                    raise BackupError("source_changed")
            files[archive_name(source)] = {
                "source": source, "sha256": checksum, **before,
                "role": "dated_supplemental_not_fresh" if source.startswith("Mikrotik/") else "local_master_tree",
                "source_mtime_utc": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
            }

    for scope in SCOPES:
        if (Path(system) / scope).is_file():
            with open_source(system, scope) as stream:
                before = metadata(os.fstat(stream.fileno()))
                checksum, size = hash_stream(stream, max_bytes)
                if metadata(os.fstat(stream.fileno())) != before:
                    raise BackupError("source_changed")
            total += size
            if total > max_bytes:
                raise BackupError("size_limit")
            files[scope] = {"source": scope, "sha256": checksum, **before, "role": "local_master_tree"}
            continue
        fd = open_directory(Path(system) / scope)
        count = len(files)
        try:
            visit(fd, scope)
        finally:
            os.close(fd)
        if len(files) == count:
            raise BackupError("empty_scope")
    if not set(REQUIRED).issubset(files):
        raise BackupError("missing_required_master")
    inventory = json.loads((Path(system) / "config/inventory/clients.json").read_text())
    expected = {".local/clients/" + entry["path"] for entry in inventory["profiles"]}
    if len(expected) != len(inventory["profiles"]):
        raise BackupError("duplicate_client_inventory")
    actual = {record["source"] for record in files.values()
              if record["source"].startswith(".local/clients/") and
              PurePosixPath(record["source"]).suffix in {".conf", ".json"}}
    if actual != expected:
        raise BackupError("client_inventory_mismatch")
    clients = len(actual)
    return {"files": files, "excluded": excluded, "bytes": total, "client_configs": clients}


def create_run(system, run):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}(?:\d{6})?Z_current-config", run):
        raise BackupError("invalid_run_id")
    parent = Path(system) / ".local/backups/local"
    fd = open_directory(parent, create=True)
    try:
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o700:
            raise BackupError("backup_parent_not_private")
        os.mkdir(run, 0o700, dir_fd=fd)
    finally:
        os.close(fd)
    return parent / run


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def write_json(path, value):
    private_write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def write_archive(path, system, files, router_export=None):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output, tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, record in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.mode, info.size = 0o600, record["size"]
            if record["role"] == "fresh_router_export":
                archive.addfile(info, io.BytesIO(router_export))
                continue
            with open_source(system, record["source"]) as stream:
                before = metadata(os.fstat(stream.fileno()))
                if any(before[key] != record[key] for key in before):
                    raise BackupError("source_changed")
                archive.addfile(info, stream)
                if metadata(os.fstat(stream.fileno())) != before:
                    raise BackupError("source_changed")


def verify_restore(archive_path, files, max_bytes=MAX_BYTES):
    """Materialize only allowlisted regular members, then hash their disk bytes."""
    total, seen = 0, set()
    with tempfile.TemporaryDirectory(prefix=".restore-verify-", dir=archive_path.parent) as temporary:
        root = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive:
                name = member.name
                path = PurePosixPath(name)
                if (not member.isreg() or member.issparse() or path.is_absolute()
                        or ".." in path.parts or str(path) != name or name in {"", "."}
                        or "\\" in name or any(ord(char) < 32 for char in name)
                        or name in seen or name not in files):
                    raise BackupError("unsafe_archive_member")
                seen.add(name)
                total += member.size
                if total > max_bytes or len(seen) > MAX_FILES or member.size != files[name]["size"]:
                    raise BackupError("archive_limit_or_size_mismatch")
                target = root.joinpath(*path.parts)
                fd = open_directory(target.parent, create=True)
                os.close(fd)
                target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(target_fd, "wb") as out, archive.extractfile(member) as source:
                    remaining = member.size
                    while remaining:
                        chunk = source.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise BackupError("truncated_archive_member")
                        out.write(chunk)
                        remaining -= len(chunk)
                with target.open("rb") as restored:
                    checksum, size = hash_stream(restored, member.size)
                if checksum != files[name]["sha256"] or size != member.size:
                    raise BackupError("restore_checksum_mismatch")
        if seen != set(files):
            raise BackupError("restore_inventory_mismatch")
    return len(seen)


IDENTITY_SCRIPT = r'''set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C
state=$(docker inspect --type container wg-relay | jq -ce '.[0] |
  select(.State.Running == true and .State.Pid > 1) |
  {id:.Id,pid:.State.Pid,started:.State.StartedAt,image:.Image}')
pid=$(printf '%s' "$state" | jq -er .pid)
exec 3<"/proc/$pid/ns/net"
inode=$(readlink "/proc/$$/fd/3")
[ "$(readlink "/proc/$pid/ns/net")" = "$inode" ]
printf '%s' "$state" | jq -c --arg namespace "$inode" '. + {namespace:$namespace}'
'''


def fresh_timeweb_args():
    base = run_backup.ssh_args("timeweb")
    return [base[0], "-T", "-o", "ControlMaster=no", "-o", "ControlPath=none",
            "-o", "ConnectionAttempts=1", "-o", "ConnectTimeout=5",
            "-o", "ClearAllForwardings=yes"] + base[1:]


def bounded_read(args, deadline, cap, max_bytes):
    """Bound bytes/time and kill only our own SSH/proxy process group on exit."""
    end = min(deadline, time.monotonic() + cap)
    if end <= time.monotonic():
        raise BackupError("router_timeout")
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise BackupError("router_timeout")
                if not selector.select(remaining):
                    raise BackupError("router_timeout")
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise BackupError("router_output_limit")
            if process.wait(timeout=max(0.001, end - time.monotonic())) != 0:
                raise BackupError("router_ssh_failed")
        return bytes(data)
    finally:
        try:
            with suppress(ProcessLookupError):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except PermissionError:
                    # macOS can reject signaling a group after its child exited.
                    if process.poll() is None:
                        raise
        finally:
            process.stdout.close()
            process.wait(timeout=1)


def read_identity(deadline):
    command = "timeout --kill-after=1s 6s bash -c " + shlex.quote(IDENTITY_SCRIPT)
    data = bounded_read(fresh_timeweb_args() + [command], deadline, 7, 4096)
    identity = json.loads(data)
    if (not isinstance(identity, dict) or set(identity) != {"id", "pid", "started", "image", "namespace"}
            or type(identity["pid"]) is not int or identity["pid"] <= 1
            or not re.fullmatch(r"[0-9a-f]{64}", identity["id"])
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity["image"])
            or not re.fullmatch(r"net:\[[0-9]+\]", identity["namespace"])
            or not re.fullmatch(r"[0-9T:.Z+-]{10,64}", identity["started"])):
        raise BackupError("router_identity_invalid")
    return identity


def router_args(identity, seconds):
    expected = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    # Rediscover identity INSIDE the proxy, pin its FD, compare all fields against
    # the fresh audit, and only then open nc. No historical manifest is read.
    proxy_script = IDENTITY_SCRIPT.replace(
        "printf '%s' \"$state\" | jq -c --arg namespace \"$inode\" '. + {namespace:$namespace}'",
        "current=$(printf '%s' \"$state\" | jq -Sc --arg namespace \"$inode\" '. + {namespace:$namespace}')\n"
        + "[ \"$current\" = " + shlex.quote(expected) + " ]\n"
        + "exec nsenter --net=\"/proc/$$/fd/3\" -- nc -w " + str(seconds) + " 10.30.30.2 22")
    proxy = shlex.join(fresh_timeweb_args() + [
        f"timeout --kill-after=1s {seconds}s bash -c " + shlex.quote(proxy_script)])
    # OpenSSH expands percent tokens in ProxyCommand before invoking the shell.
    proxy = proxy.replace("%", "%%")
    args = ["ssh", "-T", "-i", str(run_backup.PRIVATE / "ssh/codex_mikrotik_20260704"),
            "-o", "UserKnownHostsFile=" + str(run_backup.PRIVATE / "ssh/known_hosts")]
    for option in ("IdentitiesOnly=yes", "BatchMode=yes", "StrictHostKeyChecking=yes",
                   "UpdateHostKeys=no", "HostKeyAlias=192.168.88.1", "ConnectTimeout=5",
                   "ConnectionAttempts=1", "ControlMaster=no", "ControlPath=none",
                   "ClearAllForwardings=yes", "ProxyCommand=" + proxy):
        args.extend(["-o", option])
    return args + ["codex@10.30.30.2", "/export terse show-sensitive"]


def fresh_router_export():
    # Reserve up to one second for subprocess cleanup: the whole attempt <=30s.
    deadline = time.monotonic() + 29
    try:
        before = read_identity(deadline)
        seconds = min(18, int(deadline - time.monotonic() - 4))
        if seconds < 1:
            raise BackupError("router_timeout")
        data = bounded_read(router_args(before, seconds), deadline, seconds, MAX_ROUTER_BYTES)
        text = data.decode("utf-8")
        if ("RouterOS" not in text or not re.search(r"^/(?:interface|ip|system)\b", text, re.MULTILINE)
                or re.search(r"^\s*#\s*(?:error|interrupted|timeout)\b", text, re.IGNORECASE | re.MULTILINE)
                or any(token in text.lower() for token in ("failure:", "syntax error", "not enough permissions"))):
            raise BackupError("router_export_invalid")
        if read_identity(deadline) != before:
            raise BackupError("router_namespace_changed")
        return {"status": "FRESH_READONLY_EXPORT", "collected_at_utc": utc_now(),
                "identity": before, "sha256": digest(data), "size": len(data)}, data
    except BackupError as error:
        reason = str(error)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        reason = "router_connection_or_export_failed"
    return {"status": "FAILED", "reason": reason, "old_export_is_not_fresh": True}, None


def backup(system=SYSTEM, *, run=None, router=True, max_bytes=MAX_BYTES):
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_BYTES:
        raise BackupError("invalid_size_limit")
    run = run or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S%fZ_current-config")
    destination = create_run(system, run)
    report = {"schema_version": 1, "run": run, "created_at_utc": utc_now(),
              "status": "FAILED", "scope": "local configuration masters only; not live VPS backup or full-machine restore",
              "byte_limit": max_bytes, "expected_client_configs": "config/inventory/clients.json",
              "supplemental": "Old exports and backups are excluded from the migrated repository",
              "local_router_exports": "all pre-existing exports in local trees are historical, not fresh",
              "router": {"status": "NOT_ATTEMPTED"}, "local_backup": "FAILED"}
    try:
        before = snapshot(system, max_bytes)
        write_json(destination / "hashes-before.json", {k: v["sha256"] for k, v in before["files"].items()})
        report.update(client_configs=before["client_configs"], source_files=len(before["files"]),
                      source_bytes=before["bytes"])
        if router:
            router_report, export = fresh_router_export()
        else:
            router_report, export = {"status": "NOT_REQUESTED", "old_export_is_not_fresh": True}, None
        report["router"] = router_report
        files = dict(before["files"])
        if export is not None:
            if before["bytes"] + len(export) > max_bytes:
                raise BackupError("size_limit")
            files["fresh-router/router-export.rsc"] = {
                "role": "fresh_router_export", "size": len(export), "sha256": digest(export),
                "collected_at_utc": router_report["collected_at_utc"],
            }
        archive = destination / "current-config.tar.gz"
        write_archive(archive, system, files, export)
        after = snapshot(system, max_bytes)
        write_json(destination / "hashes-after.json", {k: v["sha256"] for k, v in after["files"].items()})
        write_json(destination / "inventory.json", {
            "files": files, "excluded_before": before["excluded"], "excluded_after": after["excluded"],
            "policy": "Keep all masters, credentials, source, tests and fixtures; exclude caches, known vendor Xray binaries and captured log/pcap/body files >1MiB",
        })
        if before["files"] != after["files"]:
            raise BackupError("source_changed")
        restored = verify_restore(archive, files, max_bytes)
        with archive.open("rb") as stream:
            checksum, archive_size = hash_stream(stream, max_bytes + MAX_FILES * 2048)
        report.update(local_backup="VERIFIED", source_hashes_before_after_match=True,
                      temporary_restore_files=restored, archive_sha256=checksum,
                      archive_bytes=archive_size, included_files=len(files),
                      included_bytes=sum(record["size"] for record in files.values()))
        report["status"] = "VERIFIED" if router_report["status"] == "FRESH_READONLY_EXPORT" else "PARTIAL"
    except BackupError as error:
        report["reason"] = str(error)
    except (OSError, ValueError, TypeError, tarfile.TarError):
        report["reason"] = "local_io_or_archive_failure"
    write_json(destination / "verification.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-router", action="store_true", help="Local files only; marks the result PARTIAL, not current router backup")
    args = parser.parse_args(argv)
    try:
        report = backup(router=not args.skip_router)
    except (BackupError, OSError, ValueError):
        print('FAILED: cannot create a new private local backup; existing files unchanged.', file=sys.stderr)
        return 1
    summary = {key: report[key] for key in (
        "status", "run", "local_backup", "router", "supplemental", "scope")}
    for key in ("reason", "client_configs", "source_files", "included_bytes", "temporary_restore_files"):
        if key in report:
            summary[key] = report[key]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return {"VERIFIED": 0, "PARTIAL": 2, "FAILED": 1}[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
