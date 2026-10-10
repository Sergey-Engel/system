"""Verify current deployed bytes against the local master and record evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from stage56 import DEST, ROOT, ssh

os.umask(0o077)
sha = lambda data: hashlib.sha256(data).hexdigest()
for local, remote in (
    ("public.json", "/opt/timeweb-reality/config.json"),
    ("guard.nft", "/opt/timeweb-reality/guard.nft"),
    ("guard.sh", "/opt/timeweb-reality/guard.sh"),
    ("xray-timeweb-reality.service", "/etc/systemd/system/xray-timeweb-reality.service"),
):
    observed = ssh("sha256sum " + remote).decode().split()[0]
    assert observed == sha((DEST / local).read_bytes()), local + " runtime drift"
(DEST / "guard.expected").write_bytes(ssh("cat /opt/timeweb-reality/guard.expected"))
(DEST / "runtime-status.txt").write_bytes(ssh("systemctl show xray-timeweb-reality.service -p ActiveState -p MainPID -p MemoryCurrent -p CPUUsageNSec -p UnitFileState; ss -4 -lnt 'sport = :443'; ss -6 -lnt 'sport = :443'; nft list table inet reality_fornex; date -u"))
for name in ("loopback-checks.json", "public-checks.json"):
    assert all(json.loads((DEST / name).read_text()).values())
assert all(item["passed"] for item in json.loads((DEST / "external-tests.json").read_text()).values())
assert json.loads((DEST / "auth-test.json").read_text())["unknown_uuid_refused"]
m = json.loads((DEST / "manifest.json").read_text())
m["status"] = "public-cli-verified-amnezia-pending"
m["updated_utc"] = datetime.now(timezone.utc).isoformat()
m["runtime_matches_master"] = True
m["files"] = {p.name: sha(p.read_bytes()) for p in DEST.iterdir() if p.is_file() and p.name != "manifest.json"}
(DEST / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
main = json.loads((ROOT / "manifest.json").read_text())
main["updated_utc"] = m["updated_utc"]
(ROOT / "manifest.json").write_text(json.dumps(main, indent=2) + "\n")
print("RUNTIME_MATCHES_MASTER; regression/positive/negative/auth checks passed; Amnezia acceptance pending")
