#!/usr/bin/env python3
"""Seal the reviewed live Xray and host guard while allowing only known uplink endpoints."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path("/opt/timeweb-reality/bth-recovery")
CONFIG = Path("/opt/timeweb-reality/config.json")
ENDPOINTS = {
    "wg-fornex": {
        "native": "103.75.126.143:51821",
        "backup": "127.0.0.1:51923",
    },
    "wg-cenuta": {
        "native": "89.252.153.129:51840",
        "backup": "127.0.0.1:51924",
    },
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flex-rules", action="store_true")
    parser.add_argument("--macmini-flex-rules", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    for tag, allowed in ENDPOINTS.items():
        matches = [out for out in config["outbounds"] if out.get("tag") == tag]
        if len(matches) != 1 or len(matches[0]["settings"]["peers"]) != 1:
            raise SystemExit(f"Unexpected outbound/peer count for {tag}")
        peer = matches[0]["settings"]["peers"][0]
        if peer["endpoint"] not in allowed.values():
            raise SystemExit(f"Unexpected endpoint for {tag}")
        peer["endpoint"] = f"<{tag.removeprefix('wg-')}-endpoint>"
    jq_normalized = subprocess.check_output(
        ["jq", "-S", "(.outbounds[] | select(.tag == \"wg-fornex\") | .settings.peers[0].endpoint) = \"<fornex-endpoint>\" | (.outbounds[] | select(.tag == \"wg-cenuta\") | .settings.peers[0].endpoint) = \"<cenuta-endpoint>\"", str(CONFIG)]
    )
    contract_path = ROOT / "contract.json"
    contract = json.loads(contract_path.read_text())
    hostguard = subprocess.check_output(["nft", "-s", "list", "table", "inet", "reality_fornex"])
    expected = Path("/opt/timeweb-reality/guard.expected").read_bytes()
    if hostguard != expected:
        raise SystemExit("Live host guard differs from guard.expected")
    contract["xray_endpoints"] = ENDPOINTS
    contract["hashes"]["xray_normalized"] = digest(jq_normalized)
    contract["hashes"]["hostguard"] = digest(hostguard)
    if args.flex_rules or args.macmini_flex_rules:
        pid = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.Pid}}", "wg-relay"], text=True).strip()
        actual = json.loads(subprocess.check_output(
            ["nsenter", "-t", pid, "-n", "ip", "-j", "rule", "show"]))
        new_priorities = ({184, 185, 243, 244} if args.macmini_flex_rules
                          else {186, 187, 241, 242})
        new_rules = [rule for rule in actual if rule.get("priority") in new_priorities]
        if len(new_rules) != 4 or {rule["priority"] for rule in new_rules} != new_priorities:
            raise SystemExit("Incomplete new FLEX policy rules")
        for name, key in (("rules.baseline", "rules"),
                          ("rules.monitoring.baseline", "rules_with_monitoring")):
            path = ROOT / name
            old = json.loads(path.read_text())
            without_new = [rule for rule in actual if rule.get("priority") not in new_priorities]
            if name == "rules.baseline":
                without_new = [rule for rule in without_new if not 31000 <= rule.get("priority", 0) <= 31021]
            if without_new != old:
                raise SystemExit("Unreviewed RPDB drift")
            updated = sorted(old + new_rules, key=lambda rule: rule["priority"])
            contents = subprocess.check_output(["jq", "-S", "."],
                                               input=json.dumps(updated).encode())
            path.write_bytes(contents)
            contract["hashes"][key] = digest(contents)
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print("Refreshed BTH contract for reviewed Xray and host guard")


if __name__ == "__main__":
    main()
