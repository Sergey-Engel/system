#!/usr/bin/env python3
"""Create an exact, reviewable manifest from the saved read-only audit."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
audit = json.loads(json.loads((ROOT.parents[2] / ".local/evidence/20260911-guards/baseline.json").read_text())["stdout"])
rules = []

def add(tokens, reason):
    priority = 31000 + len(rules)
    rules.append(dict(priority=priority, reason=reason,
                      argv=["priority", str(priority), "protocol", "242", "iif", "lo"] + tokens))

add(["oif", "wg1", "to", "10.20.0.2/32", "lookup", "main", "suppress_prefixlength", "0"], "permit connected gateway validation when table 100 is rebuilt")
add(["oif", "wg1", "to", "10.20.0.2/32", "prohibit"], "no WAN fallback for gateway validation")
for interface, source, table in [("wg1", "10.20.0.1", "100"), ("wg-up-cenuta", "10.40.40.2", "200")]:
    add(["oif", interface, "lookup", table], "bound local sockets")
    add(["oif", interface, "prohibit"], "no table fallthrough for local oif")
for source in ["10.20.0.1", "10.40.40.2"]:
    for subnet in ["10.20.0.0/24", "10.30.30.0/24", "172.19.0.0/16"]:
        add(["from", source + "/32", "to", subnet, "lookup", "main", "suppress_prefixlength", "0"], "preserve connected service replies")
        add(["from", source + "/32", "to", subnet, "prohibit"], "do not turn a missing service route into WAN traffic")
for source, table in [("10.20.0.1", "100"), ("10.40.40.2", "200")]:
    add(["from", source + "/32", "lookup", table], "unbound kernel replies with WG source")
    add(["from", source + "/32", "prohibit"], "no main fallback for WG source")
assert len(rules) == 22
assert not ({r["priority"] for r in audit["rules"]} & {r["priority"] for r in rules})
manifest = dict(version=1, name="timeweb-uplink-guards", target={"kind": "production", **audit["target"]},
                baseline={k:audit[k] for k in ["rules", "routes", "links", "peers", "filter", "nat", "mangle"]},
                rules=rules, expected_rules=[],
                uplinks={"fornex":{"interface":"wg1", "source":"10.20.0.1", "table":100},
                         "cenuta":{"interface":"wg-up-cenuta", "source":"10.40.40.2", "table":200}})
(ROOT / "guard-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Prepared 22 exact rules; expected_rules must be populated by isolated kernel normalization before apply.")
