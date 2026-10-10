"""Export current Fornex REALITY profiles, without touching existing WG profiles."""
raise SystemExit("RETIRED one-shot issue_stage56_clients.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import json
import os
from stage56 import ROOT, DEST

os.umask(0o077)
report = json.loads((DEST / "external-tests.json").read_text())
assert all(item["passed"] for item in report.values())
target = ROOT.parents[1] / "clients"
assert target.is_dir()
for device, label in (("macbook", "MacBook-Sergey"), ("iphone", "iPhone")):
    config = json.loads((ROOT / "staging/fornex" / ("client-" + device + ".json")).read_text())
    outbound = config["outbounds"][1]
    outbound["streamSettings"]["realitySettings"]["serverName"] = "www.apple.com"
    config["outbounds"] = [outbound]
    data = json.dumps(config, indent=2) + "\n"
    destination = target / ("TimeWeb-REALITY-Fornex-" + label + ".json")
    if destination.exists():
        assert destination.read_text() == data, "Existing profile differs; refusing overwrite"
    else:
        destination.write_text(data)
    destination.chmod(0o600)
    (DEST / destination.name).write_text(data)
    print(destination)
