"""Build a protected declarative BTH recovery contract from fresh runtime state."""
raise SystemExit("RETIRED one-shot prepare_bth_recovery.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import io
import json
import os
import tarfile
from stage8_cenuta import call, put, sha
from run_backup import ROOT

os.umask(0o077)
d=ROOT/"bth-recovery-release"
d.mkdir(mode=0o700)
pid=int(call("timeweb","docker inspect -f {{.State.Pid}} wg-relay"))
prefix=f"nsenter -t {pid} -n "
peer=(ROOT/"stage9-bth/peer.public").read_text().strip()
for f in ("peer.public","peer.psk","relay.nft","relay.expected"):
    put(d/f,(ROOT/"stage9-bth"/f).read_bytes())
for f in ("bth_recover.sh","bth-recovery.service","bth-recovery.timer"):
    put(d/f,(ROOT/f).read_bytes())
contract={"image":call("timeweb","docker inspect -f {{.Image}} wg-relay").decode().strip(),
          "wg_public":call("timeweb",prefix+"wg show wg-home public-key").decode().strip(),"hashes":{}}
commands={"wg":"cat /opt/wg/config/wg_confs/wg-home.conf", "xray":"cat /opt/timeweb-reality/config.json",
          "rules":prefix+"ip -j rule show | jq -S .", "routes":prefix+"ip -j route show table 300 | jq -S .",
          "allowed":prefix+"wg show wg-home allowed-ips | awk -v k='"+peer+"' '$1 != k' | LC_ALL=C sort",
          "hostguard":"nft -s list table inet reality_fornex"}
for name,cmd in commands.items():
    data=call("timeweb",cmd); put(d/(name+".baseline"),data); contract["hashes"][name]=sha(data)
for name,f in (("guard","relay.nft"),("expected","relay.expected"),("public","peer.public"),("psk","peer.psk")):
    contract["hashes"][name]=sha((d/f).read_bytes())
put(d/"contract.json",json.dumps(contract,indent=2)+"\n")
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode="w") as t:
    for f in d.iterdir(): t.add(f,arcname=f.name)
call("timeweb","bash -c 'umask 077; mkdir /opt/timeweb-reality/bth-recovery && tar -xf - -C /opt/timeweb-reality/bth-recovery'",buf.getvalue())
print("Recovery files staged; timer NOT installed/enabled")
