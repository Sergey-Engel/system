"""Secret-safe before/after evidence for the narrowly scoped Fornex change."""
import json
import os
import sys

from stage4_fornex import DEST, remote

COMMANDS = {
    "containers": "docker ps -q | xargs docker inspect -f '{{.Name}} {{.State.Pid}} {{.State.StartedAt}} {{.State.Status}}'",
    "filter": "docker exec wg-exit iptables -S",
    "nat": "docker exec wg-exit iptables -t nat -S",
    "routes": "docker exec wg-exit ip -4 route show table all",
    "rules": "docker exec wg-exit ip -4 rule",
    "wgconf": "docker exec wg-exit wg showconf wg0",
    "wg": "docker exec wg-exit wg show",
    "config": "sha256sum /opt/wg/config/wg_confs/wg0.conf",
}
os.umask(0o077)
phase = sys.argv[1]
assert phase in ("before", "after", "rollback", "final")
script = "set -e\n" + "\n".join("printf '\\n__STAGE4_" + key + "__\\n'\n" + value for key, value in COMMANDS.items())
output = remote("bash -s", script.encode()).decode()
snapshot = {}
for key in COMMANDS:
    snapshot[key] = output.split("__STAGE4_" + key + "__\n", 1)[1].split("\n__STAGE4_", 1)[0].strip()
path = DEST / (phase + ".json")
assert not path.exists(), "Do not overwrite evidence"
path.write_text(json.dumps(snapshot, indent=2) + "\n")
if phase == "before":
    print("BEFORE evidence saved, private configuration not printed")
    sys.exit()
before = json.loads((DEST / "before.json").read_text())
checks = {key: before[key] == snapshot[key] for key in ("containers", "nat", "routes", "rules")}
filtered = "\n".join(line for line in snapshot["filter"].splitlines() if "REALITY_F3" not in line and "reality-f3" not in line)
checks["old_filter_unchanged"] = filtered == before["filter"]
manifest = json.loads((DEST / "manifest.json").read_text())
newpub = manifest["peer_public"]
parts = snapshot["wgconf"].split("[Peer]")
oldconf = "[Peer]".join([parts[0]] + [part for part in parts[1:] if newpub not in part]).strip()
checks["old_wg_configuration_unchanged"] = oldconf == before["wgconf"]
checks["new_peer_expected_presence"] = (newpub in snapshot["wgconf"]) == (phase != "rollback")
checks["persistent_hash"] = snapshot["config"].split()[0] == manifest["before_sha256" if phase == "rollback" else "after_sha256"]
if phase == "rollback":
    checks["filter_exactly_restored"] = snapshot["filter"] == before["filter"]
(DEST / (phase + "-checks.json")).write_text(json.dumps(checks, indent=2) + "\n")
print(json.dumps(checks, indent=2))
assert all(checks.values()), "Verification failed; inspect protected evidence"
