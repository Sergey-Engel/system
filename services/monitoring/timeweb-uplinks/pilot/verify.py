"""Read-only pilot evidence; no synthetic data is inserted into the live DB."""
import datetime
import hashlib
import json
import subprocess
import urllib.parse
import urllib.request
from deploy import ROOT, SSH
from update import FILES, REMOTE_ROOT, sha256, source_path

stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out=ROOT.parents[2] / '.local/evidence'/f'{stamp}-pilot-live'
out.mkdir(mode=0o700)
def get(url):
    with urllib.request.urlopen(url,timeout=8) as response:
        return json.load(response)
snapshot=get('http://127.0.0.1:19106/api/current')
assert all(v['fresh'] for v in snapshot.values()), snapshot
queries={}
for query in ('up{job="timeweb-uplink-pilot"}','vpn_uplink_state','vpn_uplink_handshake_age_seconds','vpn_uplink_pilot_info'):
    queries[query]=get('http://127.0.0.1:9090/api/v1/query?'+urllib.parse.urlencode({'query':query}))
assert queries['up{job="timeweb-uplink-pilot"}']['data']['result'][0]['value'][1]=='1'
script='''set -eu
bash /opt/vpn-monitoring/guards/guardctl.sh /opt/vpn-monitoring/guards/guard-manifest.json check
sha256sum /opt/vpn-monitoring/guards/guardctl.sh
systemctl show vpn-uplink-pilot vpn-uplink-exporter -p Id -p ActiveState -p MemoryCurrent -p CPUUsageNSec -p NRestarts
ss -ltnp 'sport = :19106'
PYTHONPATH=/opt/vpn-monitoring/pilot/collector /opt/vpn-monitoring/pilot/.venv/bin/python - <<'PY'
import sqlite3
with sqlite3.connect('file:/var/lib/vpn-uplink-pilot/history.sqlite?mode=ro',uri=True) as db:
    print('SQLITE_INTEGRITY',db.execute('pragma integrity_check').fetchall())
    print('CYCLE_ROWS',db.execute('select count(*) from cycles').fetchone())
PY
'''
result=subprocess.run(SSH+['bash -se'],input=script,text=True,capture_output=True,timeout=30)
assert result.returncode==0,dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
names=[str(path) for path, _ in FILES]
check=subprocess.run(SSH+['sha256sum '+' '.join(str(REMOTE_ROOT/path) for path, _ in FILES)],
                     text=True,capture_output=True,check=True,timeout=15)
remote={line.split()[1]:line.split()[0] for line in check.stdout.splitlines()}
hashes={name:sha256(source_path(path)) for name,(path,_) in zip(names,FILES)}
assert all(remote[str(REMOTE_ROOT/p)]==hashes[str(p)] for p,_ in FILES)
document=dict(at=stamp,current=snapshot,prometheus=queries,server=result.stdout,
              source_sha256=hashes,master_matches_server=True,pilot=True,
              full_acceptance=False,universal_generation=False)
(out/'verification.json').write_text(json.dumps(document,indent=2)+'\n')
print(out)
print(result.stdout)
print('CURRENT', {u:v['state'] for u,v in snapshot.items()})
print('MASTER_MATCHES_SERVER')
