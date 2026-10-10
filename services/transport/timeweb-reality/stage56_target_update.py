"""Apply the tested target delta while only the new service is stopped."""
raise SystemExit("RETIRED one-shot stage56_target_update.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import json
import os
from stage56 import DEST, ssh

os.umask(0o077)
for name in ("loopback.json", "public.json"):
    path = DEST / name
    data = json.loads(path.read_text())
    data["inbounds"][0]["streamSettings"]["realitySettings"].update(
        target="23.12.156.37:443", serverNames=["www.apple.com"])
    path.write_text(json.dumps(data, indent=2) + "\n")
path = DEST / "test-client.json"
data = json.loads(path.read_text())
data["outbounds"][1]["streamSettings"]["realitySettings"]["serverName"] = "www.apple.com"
path.write_text(json.dumps(data, indent=2) + "\n")
path = DEST / "guard.nft"
path.write_text(path.read_text().replace("23.12.158.97", "23.12.156.37"))
ssh("systemctl stop xray-timeweb-reality.service; systemctl stop reality-loopback-test.service 2>/dev/null || true")
for name in ("loopback.json", "public.json", "test-client.json", "guard.nft"):
    ssh("dd of=/var/backups/timeweb-reality/stage56/" + name + " status=none", (DEST / name).read_bytes())
print(ssh('''set -e
! pgrep -u 10001
cd /var/backups/timeweb-reality/stage56
install -m 600 guard.nft /opt/timeweb-reality/guard.nft
nft delete table inet reality_fornex
nft -f guard.nft
umask 077
nft -s list table inet reality_fornex > /opt/timeweb-reality/guard.expected
install -m 640 -o root -g reality-fornex loopback.json /opt/timeweb-reality/config.json
systemctl start xray-timeweb-reality
systemd-run --unit=reality-loopback-test --collect --property=RuntimeMaxSec=180 /opt/timeweb-reality/xray run -config /var/backups/timeweb-reality/stage56/test-client.json
sleep 7
curl -fsS --max-time 20 --proxy socks5h://127.0.0.1:10843 https://api.ipify.org
''').decode())
