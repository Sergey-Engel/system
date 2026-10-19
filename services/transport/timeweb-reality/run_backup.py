"""Configuration backup with explicit coverage, drift and offline restore checks."""
import argparse
import datetime as dt
import hashlib
import gzip
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
PRIVATE = Path(os.environ.get("SYSTEM_PRIVATE_ROOT", str(REPOSITORY / ".local"))).resolve()
STORAGE = PRIVATE / "backups"
HOSTS = {
    "timeweb": ("root@94.241.171.65", "codex_timeweb_audit_20260628"),
    "fornex": ("root@103.75.126.143", "codex_fornex_audit_20260628"),
    "cenuta": ("ubuntu@89.252.153.129", "codex_cenuta_audit_20260628"),
}
MAX_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 20000
S2S_REQUIRED = [
    "etc/wireguard/wg-s2s.conf",
    "etc/wireguard/s2s-pilot/guard.nft",
    "etc/wireguard/s2s-pilot/guard.py",
    "etc/wireguard/s2s-pilot/manifest.json",
    "etc/systemd/system/s2s-pilot-guard.service",
    "etc/systemd/system/wg-quick@wg-s2s.service.d/pilot.conf",
]
S2S_CONSOLE_REQUIRED = [
    "opt/vpn-s2s/" + name for name in ("controller.py", "managed.py", "router.py", "egress.py", "lan.py")
] + ["etc/vpn-s2s/" + name for name in ("config.json", "ssh_config", "known_hosts", "id_fethiye", "id_nakhimova")] + [
    "var/lib/vpn-s2s/state.json", "usr/local/sbin/timeweb-s2s",
    "etc/systemd/system/vpn-uplink-console.service", "etc/tmpfiles.d/timeweb-console-locks.conf",
]


def pilot_required(host, files):
    if host != "timeweb" or not set(S2S_REQUIRED).intersection(files):
        return []
    if any(not files.get(name) for name in S2S_REQUIRED):
        raise ValueError("Incomplete S2S pilot backup coverage")
    return S2S_REQUIRED


def s2s_console_required(host, files):
    if host != "timeweb" or not any(name.startswith(("opt/vpn-s2s/", "etc/vpn-s2s/", "var/lib/vpn-s2s/")) for name in files):
        return []
    if any(not files.get(name) for name in S2S_CONSOLE_REQUIRED):
        raise ValueError("Incomplete S2S console backup coverage")
    return S2S_CONSOLE_REQUIRED


REQUIRED = {
    "timeweb": [
        "opt/wg/config/wg_confs/" + name + ".conf"
        for name in ("wg0", "wg1", "wg-clients", "wg-up-cenuta", "wg-home")
    ] + [
        "opt/wg-router/state/clients.tsv", "opt/wg-router/state/ru_bth_clients.tsv",
        "opt/timeweb-reality/config.json", "opt/timeweb-reality/xray",
        "opt/timeweb-reality/guard.nft", "opt/timeweb-reality/guard.expected", "opt/timeweb-reality/guard.sh",
        "opt/wg/docker-compose.yml", "opt/wg-router/commands.sh", "opt/wg-router/apply-ru-bth.sh",
        "etc/systemd/system/xray-timeweb-reality.service",
        "etc/systemd/system/bth-recovery.service", "etc/systemd/system/bth-recovery.timer",
        "etc/systemd/system/wstunnel-timeweb-fornex-wg-fallback.service",
        "etc/systemd/system/wstunnel-timeweb-cenuta-wg-fallback.service",
        "etc/wstunnel/timeweb-fornex-wg-fallback/ca.crt",
        "etc/wstunnel/timeweb-fornex-wg-fallback/client.crt",
        "etc/wstunnel/timeweb-fornex-wg-fallback/client.key",
        "usr/local/lib/wstunnel/wstunnel",
        "usr/local/sbin/wstunnel-timeweb-fornex-wg-fallback",
        "usr/local/sbin/timeweb-fornex-wg-transport",
        "etc/wstunnel/timeweb-cenuta-wg-fallback/ca.crt",
        "etc/wstunnel/timeweb-cenuta-wg-fallback/client.crt",
        "etc/wstunnel/timeweb-cenuta-wg-fallback/client.key",
        "usr/local/sbin/wstunnel-timeweb-cenuta-wg-fallback",
        "usr/local/sbin/timeweb-cenuta-wg-transport",
    ] + ["opt/timeweb-reality/bth-recovery/" + name for name in (
        "bth_recover.sh", "contract.json", "peer.public", "peer.psk", "relay.nft", "relay.expected",
        "rules.baseline", "routes.baseline", "allowed.baseline", "hostguard.baseline",
    )],
    "fornex": [
        "opt/fornex-awg31/awg0.conf", "opt/fornex-awg31/start.sh", "opt/wg/docker-compose.yml",
        "opt/wg/config/wg_confs/wg0.conf", "opt/wg/config/reality-f3/guard.sh",
        "opt/wg/config/reality-f3/expected.rules", "opt/wg/config/reality-f3/filter.restore",
        "opt/wg/config/reality-f3/peer.psk",
        "etc/systemd/system/wstunnel-fornex-wg-fallback.service",
        "etc/wstunnel/fornex-wg-fallback/ca.crt",
        "etc/wstunnel/fornex-wg-fallback/server.crt",
        "etc/wstunnel/fornex-wg-fallback/server.key",
        "usr/local/lib/wstunnel/wstunnel",
    ],
    "cenuta": [
        "etc/wireguard/wg-cenuta.conf", "etc/nftables.conf",
        "etc/reality-c3/guard.sh", "etc/reality-c3/guard.nft", "etc/reality-c3/guard.expected",
        "etc/systemd/system/wstunnel-cenuta-wg-fallback.service",
        "etc/wstunnel/cenuta-wg-fallback/ca.crt",
        "etc/wstunnel/cenuta-wg-fallback/server.crt",
        "etc/wstunnel/cenuta-wg-fallback/server.key",
        "usr/local/lib/wstunnel/wstunnel",
    ],
}
EXPECTED_CONTAINERS = {
    "timeweb": {"wg-relay"},
    "fornex": {"wg-exit", "fornex-awg31", "amnezia-xray", "amnezia-wireguard",
               "amnezia-dns", "amnezia-openvpn", "amnezia-ipsec"},
}
REQUIRED_CONTAINER = {
    "fornex-awg31": ["opt/fornex-awg31/awg0.conf", "opt/fornex-awg31/start.sh", "opt/amnezia/start.sh"],
    "amnezia-xray": ["opt/amnezia/start.sh"] + ["opt/amnezia/xray/" + name for name in (
        "server.json", "xray_uuid.key", "xray_private.key", "xray_public.key", "xray_short_id.key", "clientsTable")],
    "amnezia-wireguard": ["opt/amnezia/start.sh"] + ["opt/amnezia/wireguard/" + name for name in (
        "wg0.conf", "wireguard_server_private_key.key", "wireguard_server_public_key.key", "wireguard_psk.key", "clientsTable")],
    "amnezia-openvpn": ["opt/amnezia/start.sh"] + ["opt/amnezia/openvpn/" + name for name in (
        "server.conf", "ca.crt", "AmneziaReq.crt", "AmneziaReq.key", "ta.key", "dh.pem", "crl.pem", "clientsTable",
        "pki/private/ca.key", "pki/index.txt", "pki/serial")],
    "amnezia-ipsec": ["etc/ipsec.conf", "etc/ipsec.secrets", "etc/ipsec.d/ikev2.conf", "etc/ipsec.d/passwd",
                      "etc/ipsec.d/key4.db", "etc/ipsec.d/cert9.db", "etc/ipsec.d/ca_cert_base64.p12",
                      "etc/xl2tpd/xl2tpd.conf", "etc/ppp/chap-secrets", "etc/ppp/options.xl2tpd"],
    "amnezia-dns": ["opt/unbound/etc/unbound/" + name for name in (
        "unbound.conf", "forward-records.conf", "a-records.conf", "srv-records.conf", "var/root.key")],
}


def ssh_args(host):
    remote, key = HOSTS[host]
    args = ["ssh", "-i", str(PRIVATE / "ssh" / key)]
    for option in ("IdentitiesOnly=yes", "BatchMode=yes", "StrictHostKeyChecking=yes",
                   "UpdateHostKeys=no", "ConnectTimeout=8", "ServerAliveInterval=5",
                   "ServerAliveCountMax=2"):
        args.extend(["-o", option])
    trust = "known_hosts_cenuta" if host == "cenuta" else "known_hosts"
    args.extend(["-o", "UserKnownHostsFile=" + str(PRIVATE / "ssh" / trust)])
    return args + [remote]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_tar(data, metadata_nodes=None):
    """Read regular files without extracting links or executing archived content."""
    result, seen, links = {}, set(), {}
    total = 0
    if data.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as source:
            data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Archive exceeds uncompressed stream limit")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            name = str(path)
            if len(seen) >= MAX_MEMBERS or len(name) > 4096 or len(member.linkname) > 4096:
                raise ValueError("Archive metadata exceeds limit")
            if path.is_absolute() or ".." in path.parts or name in seen:
                raise ValueError("Unsafe or duplicate archive path")
            seen.add(name)
            if member.isfile():
                total += member.size
                if total > MAX_BYTES:
                    raise ValueError("Archive exceeds uncompressed limit")
                result[name] = archive.extractfile(member).read()
            elif member.islnk():
                target = PurePosixPath(member.linkname)
                if target.is_absolute() or ".." in target.parts:
                    raise ValueError("Unsafe hardlink")
                links[name] = str(target)
            elif member.ischr() and (metadata_nodes or {}).get(name) == (member.devmajor, member.devminor):
                # Unbound chroot device nodes remain metadata, never extracted.
                pass
            elif not (member.isdir() or member.issym()):
                raise ValueError("Unsupported special archive member")
    for name, target in links.items():
        if target not in result:
            raise ValueError("Unresolved archive hardlink")
        total += len(result[target])
        if total > MAX_BYTES:
            raise ValueError("Archive hardlinks exceed limit")
        result[name] = result[target]
    return result


def hash_records(data):
    records = {}
    for line in data.decode().splitlines():
        escaped = line.startswith("\\")
        if escaped:
            line = line[1:]
        expected, name = line.split("  ", 1)
        if escaped:
            name = re.sub(r"\\([\\nr])",
                          lambda m: {"\\": "\\", "n": "\n", "r": "\r"}[m[1]], name)
        path = PurePosixPath(name)
        name = str(path)
        if path.is_absolute() or ".." in path.parts or name in records:
            raise ValueError("Unsafe or duplicate checksum path")
        if not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError("Invalid checksum")
        records[name] = expected
    if not records:
        raise ValueError("Empty checksum manifest")
    return records


def verify_hashlist(data, contents, prefix=""):
    records = hash_records(data)
    for name, expected in records.items():
        if digest(contents[prefix + name]) != expected:
            raise ValueError("File checksum mismatch: " + prefix + name)
    return len(records)


def verify_metadata(data, source):
    expected = {}
    for record in source.decode().split("\0"):
        if not record:
            continue
        kind, mode, uid, gid, name, link = record.split("\t")
        name = str(PurePosixPath(name))
        if name in expected:
            raise ValueError("Duplicate metadata path")
        expected[name] = (kind, int(mode, 8), int(uid), int(gid), link)
    actual = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        for member in archive:
            kind = ("f" if member.isfile() or member.islnk() else "d" if member.isdir()
                    else "l" if member.issym() else "c" if member.ischr()
                    else "b" if member.isblk() else "p" if member.isfifo() else "?")
            actual[str(PurePosixPath(member.name))] = (
                kind, member.mode, member.uid, member.gid, member.linkname if member.issym() else "")
    if not expected or actual != expected:
        raise ValueError("Archive metadata differs from source metadata")


def normalized(value):
    if isinstance(value, list):
        return [normalized(x) for x in value
                if not (isinstance(x, dict) and "metainfo" in x)]
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()
                if k not in {"expires", "cache", "packets", "bytes"}}
    return value


def static_text(data, wg=False):
    lines = [x for x in data.splitlines() if not x.startswith(b"#")]
    if wg:
        lines = [x for x in lines if not x.startswith(b"Endpoint = ")]
    return b"\n".join(re.sub(rb"\[\d+:\d+\]", b"[0:0]", x) for x in lines)


def static_awg_config(data):
    """Normalize endpoint data and AWG's non-deterministic runtime serialization."""
    return b"\n".join(sorted(static_text(data, wg=True).splitlines()))


def verify_runtime(host, members, prefix, s2s=False):
    before, after = prefix + "state-before/", prefix + "state-after/"
    checks = {}
    def compare(name, transform=lambda x: x):
        checks[name] = transform(members[before + name]) == transform(members[after + name])
    compare("boot-id.txt")
    for name in ("host-routes4.json", "host-routes6.json", "host-rules4.json", "host-rules6.json",
                 "host-nft.json"):
        compare(name, lambda x: normalized(json.loads(x)))
    for name in ("host-iptables.txt", "host-ip6tables.txt"):
        compare(name, static_text)
    compare("wg-runtime.conf", lambda x: static_text(x, wg=True))
    if s2s:
        if any(state + name not in members for state in (before, after)
               for name in ("host-s2s-runtime.conf", "host-s2s-guard.txt")):
            raise ValueError("Missing S2S runtime/guard capture")
        compare("host-s2s-runtime.conf", static_awg_config)
        checks["s2s-guard-valid"] = all(
            members[state + "host-s2s-guard.txt"].strip() == b"S2S_GUARD_VERIFIED"
            for state in (before, after))
    if host == "cenuta":
        compare("wg-unit.txt")
    else:
        compare("wg-netns.txt")
        for name in ("wg-routes4.json", "wg-routes6.json", "wg-rules4.json", "wg-rules6.json", "wg-nft.json"):
            compare(name, lambda x: normalized(json.loads(x)))
        for name in ("wg-iptables.txt", "wg-ip6tables.txt"):
            compare(name, static_text)
        def stable_docker(data):
            return {x["Name"]: {"Id": x["Id"], "Image": x["Image"],
                               "Config": x["Config"], "HostConfig": x["HostConfig"],
                               "State": {k: x["State"][k] for k in ("Pid", "Running", "StartedAt")},
                               "Mounts": sorted(x["Mounts"], key=lambda m: m["Destination"]),
                               "Networks": x["NetworkSettings"]["Networks"]}
                    for x in json.loads(data)}
        compare("docker-inspect.json", stable_docker)
        compare("docker-networks.json", lambda x: sorted(json.loads(x), key=lambda n: n["Id"]))
        if host == "timeweb":
            compare("xray-unit.txt")
            checks["bth-contract-valid"] = all(
                members[state + "bth-contract.txt"].strip() == b"BTH_CONTRACT_VALID"
                for state in (before, after))
        else:
            compare("awg-runtime.conf", static_awg_config)
            compare("awg-firewall.txt", static_text)
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError("Runtime drift: " + ", ".join(failed))
    return checks


def verify(host, run, dest):
    archive = dest / "backup.tar.gz"
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError("Compressed archive too large")
    data = archive.read_bytes()
    remote_sha = (dest / "remote-sha256.txt").read_text().strip()
    if digest(data) != remote_sha:
        raise ValueError("Archive transfer checksum mismatch")
    members = checked_tar(data)
    prefix = run + "/"
    if members[prefix + "schema-version.txt"].strip() != b"3":
        raise ValueError("Not a current schema-3 backup; collect again with current script")
    if members[prefix + "host.txt"].strip().decode() != host:
        raise ValueError("Wrong backup host")
    outer_records = hash_records(members[prefix + "SHA256SUMS"])
    if {prefix + x for x in outer_records} != set(members) - {prefix + "SHA256SUMS"}:
        raise ValueError("Unlisted bundle members")
    outer_count = verify_hashlist(members[prefix + "SHA256SUMS"], members, prefix)
    files = checked_tar(members[prefix + "host-files.tar"])
    host_records = hash_records(members[prefix + "host-source-before.sha256"])
    if set(host_records) != set(files):
        raise ValueError("Host archive and checksum inventory differ")
    file_count = verify_hashlist(members[prefix + "host-source-before.sha256"], files)
    for when in ("after", "final"):
        if members[prefix + "host-source-before.sha256"] != members[prefix + "host-source-" + when + ".sha256"]:
            raise ValueError("Host source content changed during backup")
        if members[prefix + "host-metadata-before.nul"] != members[prefix + "host-metadata-" + when + ".nul"]:
            raise ValueError("Host source metadata changed during backup")
    verify_metadata(members[prefix + "host-files.tar"], members[prefix + "host-metadata-before.nul"])
    required = list(REQUIRED[host]) + pilot_required(host, files) + s2s_console_required(host, files)
    if host == "timeweb":
        contract_path = "opt/timeweb-reality/bth-recovery/contract.json"
        contract = json.loads(files.get(contract_path, b"{}"))
        optional = contract.get("hashes", {}).get("rules_with_monitoring")
        if optional is not None:
            name = "opt/timeweb-reality/bth-recovery/rules.monitoring.baseline"
            if name not in files or digest(files[name]) != optional:
                raise ValueError("Monitoring rules contract mismatch")
            required.append(name)
        if "etc/systemd/system/timeweb-runtime-recovery.service" in files:
            required.extend([
                "opt/vpn-runtime-recovery/runtime_recovery.py",
                "opt/vpn-runtime-recovery/rebind_after_reboot.py",
                "opt/vpn-runtime-recovery/policy.json",
                "var/lib/vpn-runtime-recovery/state.json",
                "etc/systemd/system/timeweb-runtime-recovery.timer",
                "etc/tmpfiles.d/timeweb-console-locks.conf",
                "usr/local/sbin/timeweb-flex-macbook",
                "usr/local/sbin/timeweb-flex-fleet",
                "opt/vpn-monitoring/guards/guard-manifest.json",
                "var/lib/vpn-uplink-guards/state.json",
                "opt/vpn-monitoring/pilot/candidate/guardctl-batch.sh",
                "var/lib/vpn-uplink-pilot/transport-state.json",
                "opt/vpn-monitoring/pilot/collector/uplink_monitor/console.py",
            ])
    missing = [x for x in required if not files.get(x)]
    if missing:
        raise ValueError("Missing required configuration files: " + ", ".join(missing))
    container_counts = {}
    for name, content in members.items():
        if "/containers/" in name and name.endswith(".tar"):
            stem = name[:-4]
            for when in ("after", "final"):
                if members[stem + ".before.sha256"] != members[stem + "." + when + ".sha256"]:
                    raise ValueError("Container configuration changed")
                if members[stem + ".metadata-before.nul"] != members[stem + ".metadata-" + when + ".nul"]:
                    raise ValueError("Container metadata changed")
            nodes = {"opt/unbound/etc/unbound/dev/" + name: (1, minor)
                     for name, minor in (("null", 3), ("random", 8), ("urandom", 9))}
            contents = checked_tar(content, nodes if PurePosixPath(stem).name == "amnezia-dns" else None)
            verify_metadata(content, members[stem + ".metadata-before.nul"])
            container = PurePosixPath(stem).name
            missing = [x for x in REQUIRED_CONTAINER.get(container, []) if x not in contents]
            if container not in REQUIRED_CONTAINER or missing:
                raise ValueError("Missing required container configuration: " + container)
            if container == "fornex-awg31":
                for path in contents:
                    if path.startswith("opt/fornex-awg31/") and (path not in files or files[path] != contents[path]):
                        raise ValueError("Bind-mounted configuration differs between archives")
            records = hash_records(members[stem + ".before.sha256"])
            if set(records) != set(contents):
                raise ValueError("Container inventory mismatch")
            container_counts[PurePosixPath(stem).name] = verify_hashlist(
                members[stem + ".before.sha256"], contents)
    if host != "cenuta":
        inventory = set(members[prefix + "container-inventory.txt"].decode().splitlines())
        inspected = {x["Name"].lstrip("/") for x in json.loads(members[prefix + "state-before/docker-inspect.json"])}
        if inventory != inspected or inventory != EXPECTED_CONTAINERS[host]:
            raise ValueError("Container inventory drift; review expected coverage")
        if set(container_counts) != inventory - {"wg-relay", "wg-exit"}:
            raise ValueError("Container configuration coverage incomplete")
    capture_errors = int(members[prefix + "capture-errors.txt"])
    for state in ("state-before", "state-after"):
        rows = members[prefix + state + "/commands.tsv"].decode().splitlines()
        if not rows or any(line.rsplit("\t", 1)[1] != "0" for line in rows):
            raise ValueError("Runtime capture command failed")
    if capture_errors:
        raise ValueError("Runtime capture errors")
    checks = verify_runtime(host, members, prefix, s2s=bool(pilot_required(host, files)))
    # Rehearse restoring required regular files to a private temporary directory.
    # Never extract symlinks or run restored scripts; never restore onto a live host.
    with tempfile.TemporaryDirectory(prefix="restore-check-", dir=dest) as tmp:
        for name in required:
            path = Path(tmp) / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(files[name])
            path.chmod(0o600)
            if digest(path.read_bytes()) != digest(files[name]):
                raise ValueError("Temporary restore checksum mismatch")
    report = {
        "schema_version": 3, "host": host, "run": run,
        "verified_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "remote_archive": "/var/backups/timeweb-reality/" + run + ".tar.gz",
        "local_archive": str(archive), "size_bytes": len(data), "sha256": remote_sha,
        "verified_bundle_files": outer_count, "verified_host_files": file_count,
        "verified_container_files": container_counts, "capture_errors": capture_errors,
        "required_files": required, "temporary_restore_files": len(required),
        "transfer_sha256_match": True, "source_hashes_match_before_after": True,
        "runtime_before_after": checks, "status": "VERIFIED",
        "verification": "Coverage, content integrity and isolated file restore; not full-machine restore",
        "scope": "Configuration and runtime evidence; excludes OS disk, Docker images and monitoring DB",
        "ephemeral_io": "BTH --check uses its existing /run scratch and advisory lock; no peer or rule changes",
    }
    (dest / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    (dest / "SHA256SUMS").write_text(remote_sha + "  backup.tar.gz\n")
    return report


def collect(host, run, dest):
    dest.mkdir(mode=0o700, parents=True, exist_ok=False)
    sudo = "sudo -n " if host == "cenuta" else ""
    remote = "/var/backups/timeweb-reality/" + run + ".tar.gz"
    cmd = sudo + "timeout 360 bash -s -- " + shlex.quote(host) + " " + shlex.quote(run)
    print(host + ": collecting configuration (no service changes)", flush=True)
    result = subprocess.run(ssh_args(host) + [cmd], input=(ROOT / "backup_readonly.sh").read_bytes(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=390)
    (dest / "execution.stdout").write_bytes(result.stdout)
    (dest / "execution.stderr").write_bytes(result.stderr)
    if result.returncode not in (0, 3):
        raise RuntimeError("Remote backup failed rc=" + str(result.returncode) + "; protected logs: " + str(dest))
    size = subprocess.run(ssh_args(host) + [sudo + "stat -c %s " + shlex.quote(remote)],
                          capture_output=True, check=True, timeout=20)
    if not 0 < int(size.stdout) <= MAX_BYTES:
        raise ValueError("Remote archive exceeds limit")
    with (dest / "backup.tar.gz").open("xb") as output, (dest / "transfer.stderr").open("xb") as errors:
        subprocess.run(ssh_args(host) + [sudo + "cat " + shlex.quote(remote)],
                       stdout=output, stderr=errors, timeout=180, check=True)
    remote_sha = subprocess.run(ssh_args(host) + [sudo + "sha256sum " + shlex.quote(remote)],
                                capture_output=True, check=True, timeout=20).stdout.decode().split()[0]
    (dest / "remote-sha256.txt").write_text(remote_sha + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=[*HOSTS, "all"])
    parser.add_argument("run", nargs="?", help="Run ID; defaults to a new run, or latest run for --verify-only")
    parser.add_argument("--verify-only", action="store_true", help="Offline verification; no SSH")
    args = parser.parse_args()
    if args.run and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}Z_current-config", args.run):
        raise ValueError("Invalid run ID; expected YYYY-MM-DDTHHMMSSZ_current-config")
    os.umask(0o077)
    hosts = list(HOSTS) if args.host == "all" else [args.host]
    failures = []
    for host in hosts:
        if args.run:
            run = args.run
        elif args.verify_only:
            candidates = sorted((STORAGE / host).glob("*_current-config"))
            if not candidates:
                raise ValueError(f"No local backup exists for {host}")
            run = candidates[-1].name
        else:
            run = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ_current-config")
        dest = STORAGE / host / run
        try:
            if not args.verify_only:
                collect(host, run, dest)
            report = verify(host, run, dest)
            print(json.dumps({k: report[k] for k in (
                "host", "run", "size_bytes", "verified_host_files", "verified_container_files",
                "temporary_restore_files", "sha256", "status", "local_archive")}), flush=True)
        except Exception as error:
            # Error messages do not include captured configuration or stderr.
            print(host + ": FAILED: " + str(error), flush=True)
            failures.append(host)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
