#!/usr/bin/env python3
import ipaddress
import json
import subprocess
import sys
import time
from admin_stage import ROOT, EVIDENCE, SSH

record = json.loads((EVIDENCE / (sys.argv[1] + ".json")).read_text())
assert record["returncode"] == 0 and "SUMMARY failures=0" in record["stdout"]
expected = json.loads(next(line.split("=", 1)[1] for line in record["stdout"].splitlines() if line.startswith("EXPECTED_RULES=")))
path = ROOT / "guard-manifest.json"
manifest = json.loads(path.read_text())
assert len(expected) == len(manifest["rules"]) == 22
assert [r["priority"] for r in expected] == list(range(31000, 31022))
manifest["expected_rules"] = expected
manifest["lab_evidence"] = sys.argv[1]
path.write_text(json.dumps(manifest, indent=2) + "\n")
targets = {}
for name, host, suffix in [("gstatic", "www.gstatic.com", "/generate_204"),
                            ("cloudflare", "www.cloudflare.com", "/cdn-cgi/trace"),
                            ("ipify", "api.ipify.org", "/")]:
    output = subprocess.check_output(SSH + [f"timeout 5 getent ahostsv4 {host}"], text=True, timeout=15)
    address = output.split()[0]
    assert ipaddress.ip_address(address).is_global
    targets[name] = dict(url=f"https://{host}{suffix}", host=host, ip=address, port=443)
now = int(time.time())
(ROOT / "probe-targets.json").write_text(json.dumps(dict(resolved_unix=now, expires_unix=now+3600, targets=targets), indent=2) + "\n")
print("Validated 22 kernel-normalized rules. Targets:", json.dumps(targets))
