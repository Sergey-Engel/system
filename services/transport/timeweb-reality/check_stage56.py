"""Capture protected regression evidence without printing configuration keys."""
import json
import os
import sys
from stage56 import DEST, ssh

os.umask(0o077)
phase = sys.argv[1]
assert phase in ("before", "loopback", "public")
commands = {
    "containers": "docker ps -q | xargs docker inspect -f '{{.Name}} {{.State.Pid}} {{.State.StartedAt}} {{.State.Status}}'",
    "host_routes": "ip -4 route show table all",
    "host_rules": "ip -4 rule",
    "host_links": "ip -o link show | sed 's/ valid_lft.*//'",
    "host_iptables": "iptables -S",
    "host_nat": "iptables -t nat -S",
    "relay_routes": "docker exec wg-relay ip -4 route show table all",
    "relay_rules": "docker exec wg-relay ip -4 rule",
    "relay_filter": "docker exec wg-relay iptables -S",
    "persistent_wg": "sha256sum /opt/wg/config/wg_confs/*.conf",
}
payload = "set -e\n" + "\n".join("printf '\\n__CHECK_" + k + "__\\n'\n" + v for k,v in commands.items())
out = ssh("bash -s", payload.encode()).decode()
data = {k: out.split("__CHECK_"+k+"__\n")[1].split("\n__CHECK_")[0].strip() for k in commands}
(DEST / (phase + "-regression.json")).write_text(json.dumps(data, indent=2) + "\n")
if phase != "before":
    before = json.loads((DEST / "before-regression.json").read_text())
    checks = {k: data[k] == before[k] for k in data}
    (DEST / (phase + "-checks.json")).write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))
    assert all(checks.values())
else:
    print("BEFORE_SAVED")
