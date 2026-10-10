"""Derive a non-applicable rollback manifest from verified configuration backups."""
if __name__ == "__main__":
    raise SystemExit("RETIRED one-shot prepare_rollback.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from run_backup import ROOT, STORAGE, checked_tar

RUNS = {"timeweb": "2026-09-12T1550Z_pre-reality",
        "fornex": "2026-09-12T1553Z_pre-reality",
        "cenuta": "2026-09-12T1550Z_pre-reality"}


def normalized(value):
    if isinstance(value, list):
        return [normalized(item) for item in value if not (isinstance(item, dict) and "metainfo" in item)]
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key in ("expires", "cache"):
                continue
            if key == "counter" and isinstance(child, dict):
                child = {k: v for k, v in child.items() if k not in ("packets", "bytes")}
            result[key] = normalized(child)
        return result
    return value


def wg_static(data):
    return re.sub(rb"^Endpoint = .*\n", b"", data, flags=re.M)


def iptables_static(data):
    lines = [line for line in data.splitlines() if not line.startswith(b"#")]
    return b"\n".join(re.sub(rb"\[\d+:\d+\]$", b"[0:0]", line)
                      if line.startswith(b":") else line for line in lines)


def main():
    os.umask(0o077)
    project = json.loads((ROOT / "manifest.json").read_text())
    report = {"schema_version": 1, "authorization": "backup-and-rollback-preparation-only",
              "runtime_apply_allowed": False, "rollback_apply_allowed": False,
              "changes_applied": [], "hosts": {}, "planned_changes": []}
    for host, run in RUNS.items():
        folder = STORAGE / host / run
        verified = json.loads((folder / "verification.json").read_text())
        raw = (folder / "backup.tar.gz").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == verified["sha256"]
        assert verified["capture_errors"] == 0
        members = checked_tar(raw)
        prefix = run + "/"
        files = checked_tar(members[prefix + "host-files.tar"])
        protected = {}
        # Restore individual future-change targets into a private temporary dir,
        # never onto their real absolute paths or into the running servers.
        with tempfile.TemporaryDirectory(prefix="restore-check-", dir=folder) as scratch:
            for name, old_hash in project["protected_persistent_file_sha256"][host].items():
                data = files[name.lstrip("/")]
                restored = Path(scratch) / name.lstrip("/")
                restored.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                restored.write_bytes(data)
                sha = hashlib.sha256(restored.read_bytes()).hexdigest()
                protected[name] = {"sha256": sha, "matches_step1": sha == old_hash,
                                   "temporary_file_restore_verified": True}
        checks = {}
        for key in ("host-routes4.json", "host-routes6.json", "host-rules4.json", "host-rules6.json",
                    "host-nft.json", "wg-routes4.json", "wg-routes6.json", "wg-rules4.json",
                    "wg-rules6.json", "wg-nft.json"):
            before, after = [prefix + state + "/" + key for state in ("state-before", "state-after")]
            if before in members:
                checks[key] = normalized(json.loads(members[before])) == normalized(json.loads(members[after]))
        for key in ("host-iptables.txt", "host-ip6tables.txt", "wg-iptables.txt", "wg-ip6tables.txt"):
            before, after = [prefix + state + "/" + key for state in ("state-before", "state-after")]
            if before in members:
                checks[key] = iptables_static(members[before]) == iptables_static(members[after])
        checks["wg-keys-peers-allowedips-listenport"] = wg_static(members[prefix + "state-before/wg-runtime.conf"]) == wg_static(members[prefix + "state-after/wg-runtime.conf"])
        if host != "cenuta":
            before, after = [json.loads(members[prefix + state + "/docker-inspect.json"]) for state in ("state-before", "state-after")]
            stable = lambda rows: {r["Name"]: {"Id": r["Id"], "Image": r["Image"],
                "Pid": r["State"]["Pid"], "StartedAt": r["State"]["StartedAt"],
                "Running": r["State"]["Running"], "HostConfig": r["HostConfig"], "Config": r["Config"]} for r in rows}
            checks["docker-identities-config-pid-start-time"] = stable(before) == stable(after)
            checks["wg-netns-identity"] = members[prefix + "state-before/wg-netns.txt"] == members[prefix + "state-after/wg-netns.txt"]
        else:
            checks["wg-and-nft-unit-active-time"] = members[prefix + "state-before/wg-unit.txt"] == members[prefix + "state-after/wg-unit.txt"]
        evidence_paths = {key: prefix + "state-before/" + key for key in ("host-nft.json", "host-iptables.txt", "host-routes4.json", "host-rules4.json", "wg-runtime.conf")}
        report["hosts"][host] = {"backup": verified, "protected_files": protected,
                                  "before_after_checks": checks, "archive_evidence": evidence_paths}
    for item in project["address_reservations"]:
        report["planned_changes"].append({
            "id": "peer-" + item["profile"], "host": item["server"],
            "container": item.get("server_container"), "interface": item["server_interface"],
            "persistent_file": item["persistent_path"], "new_allowed_ip": item["address"],
            "new_peer_public_key": None, "server_public_key_is_not_new_peer_key": True,
            "after_sha256": None, "applied": False, "approved": False,
            "rollback": "Remove only the future new public key; restore only its recorded persistent block. Reject unknown drift."})
    report["planned_changes"].extend([
        {"id": "timeweb-reality-processes", "host": "timeweb", "applied": False, "approved": False,
         "units": ["xray-timeweb-reality.service", "xray-timeweb-bth.service"],
         "uid_main": None, "uid_bth": None, "owned_files": [],
         "rollback": "Stop only deployed project units before removing their protections. Never restart old WG/Amnezia."},
        {"id": "scoped-firewall", "hosts": ["timeweb", "fornex", "cenuta"], "applied": False, "approved": False,
         "owned_rules": [], "runtime_generation": None,
         "rollback": "Record namespace, family, table, chain, exact expression, comment and live handle; remove only matching owned rules, never restore a whole ruleset."}])
    report["limitations"] = [
        "Configuration backup, not an OS/Docker-image/monitoring-database backup.",
        "Selected files were restored only into a temporary local directory; no live restore or full client regression.",
        "Counters/timestamps/cache and learned WireGuard Endpoint changes are excluded from static comparisons.",
        "No new peer keys, UUID, rules, UID or config exist yet. Exact applied-object rollback must be completed during a separately approved deployment.",
        "Provider console and provider firewall not verified. MikroTik backup must precede any later router mutation.",
        "Recheck current file hashes and namespace generation immediately before each later write."]
    report["baseline_checks_passed"] = all(all(h["before_after_checks"].values()) and all(p["matches_step1"] for p in h["protected_files"].values()) for h in report["hosts"].values())
    (ROOT / "rollback_manifest_20260912.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"baseline_checks_passed": report["baseline_checks_passed"], "hosts": {
        k: {"checks": v["before_after_checks"], "protected_files": len(v["protected_files"])} for k, v in report["hosts"].items()}}, indent=2))
    if not report["baseline_checks_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
