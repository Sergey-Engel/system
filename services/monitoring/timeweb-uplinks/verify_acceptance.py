#!/usr/bin/env python3
import json
from admin_stage import EVIDENCE, ROOT

def output(name):
    record = json.loads((EVIDENCE / (name+".json")).read_text())
    assert record["returncode"] == 0, name
    return record["stdout"]

baseline = json.loads(output("baseline"))
after = json.loads(output("production-after"))
final = json.loads(output("final-audit"))
rollback = json.loads(output("after-canary-rollback"))
manifest = json.loads((ROOT / "guard-manifest.json").read_text())
stable = ["target", "routes", "links", "host_rules", "host_routes", "filter", "nat", "mangle", "peers"]
for key in stable:
    assert baseline[key] == after[key] == rollback[key] == final[key], key
assert final["rules"] == after["rules"]
assert rollback["rules"] == baseline["rules"]
new = [r for r in after["rules"] if 31000 <= r["priority"] <= 31021]
old = [r for r in after["rules"] if not 31000 <= r["priority"] <= 31021]
assert new == manifest["expected_rules"] and old == baseline["rules"]
matrices = [output(name).split("MATRIX_BEGIN\n")[1].split("MATRIX_END")[0] for name in ["regression-before", "regression-after"]]
assert matrices[0] == matrices[1]
capture = output("production-captures")
assert "PROBE_WAN_DIRECT_COUNT=0\n" in capture
assert capture.count("0 packets dropped by kernel") == 2
assert capture.count("VALID_OBSERVATION") == 6
lab = output("guard-lab-v4")
assert "SUMMARY failures=0" in lab
supplements = {name: output(name) for name in ("guard-lab-v6", "guard-lab-v7")}
for name, evidence in supplements.items():
    assert "SUMMARY failures=0" in evidence, name
    assert "packets direct_out=0 direct_rst=0 wg_rst=8" in evidence, name
    assert "UNKNOWN reason=generation_or_manifest_changed result_discarded" in evidence, name
result = dict(guard_layer="passed_bounded_checks", owned_rules=len(new),
              exact_rollback_verified=True, unchanged_fields=stable,
              route_lookups_identical=len(matrices[0].splitlines())//2,
              lab_assertions_passed=sum(line.startswith("PASS ") for line in lab.splitlines()),
              supplemental_lab_passes={name: sum(line.startswith("PASS ") for line in evidence.splitlines()) for name, evidence in supplements.items()},
              final_audit_time=final["time"],
              captures_no_direct_probe_tcp=True, captures_kernel_drops=0,
              fornex_https_success=3, cenuta_existing_tcp_timeouts=3,
              client_application_regression="incomplete: capture had selector SYNs only, no healthy bidirectional client TCP; real-client test still required",
              runtime_restart_autoreapply=False, collector_installed=False,
              server_venv_installed=False, prometheus_installed=False)
(EVIDENCE / "acceptance-summary-final.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
