"""Read-only BTH preflight. Sensitive snapshots stay in protected System."""
import datetime
import json
import os
import shlex
import subprocess
from pathlib import Path
from stage8_cenuta import call, put
from run_backup import ROOT, ssh_args

os.umask(0o077)
dest = ROOT / ("stage9-audit-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
dest.mkdir(mode=0o700)
pid = int(call("timeweb", "docker inspect -f {{.State.Pid}} wg-relay").strip())
proxy = shlex.join(ssh_args("timeweb") + [f"nsenter -t {pid} -n nc -w 20 10.30.30.2 22"])
router = ["ssh", "-i", str(Path.home()/".ssh/codex_mikrotik_20260704"),
          "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
          "-o", "HostKeyAlias=192.168.88.1", "-o", "ConnectTimeout=8", "-o", "ProxyCommand="+proxy,
          "codex@10.30.30.2"]
for name, command in {
    "rules": "docker exec wg-relay ip rule show",
    "table300": "docker exec wg-relay ip route show table 300",
    "allowed": "docker exec wg-relay wg show wg-home allowed-ips",
    "wg-home.conf": "cat /opt/wg/config/wg_confs/wg-home.conf",
    "resources": "free -m",
    "listeners": "ss -lnut",
    "namespace": f"readlink /proc/{pid}/ns/net",
}.items():
    put(dest/name, call("timeweb", command))
result = subprocess.run(router+["/export terse"],capture_output=True,timeout=90)
if result.returncode or b"/interface" not in result.stdout or b"/ip firewall" not in result.stdout:
    raise RuntimeError("Router export failed; no changes made")
put(dest/"router.rsc",result.stdout)
summary = {"namespace_pid":pid,
           "candidate":"10.30.30.5/32",
           "candidate_absent_runtime": "10.30.30.5" not in (dest/"allowed").read_text(),
           "candidate_absent_config": "10.30.30.5" not in (dest/"wg-home.conf").read_text(),
           "configuration_changes":False,
           "router_export_is_not_binary_backup":True}
put(dest/"summary.json",json.dumps(summary,indent=2)+"\n")
print(dest)
print(json.dumps(summary))
