"""Resource audit and explicit seven-day retention deployment. No VPN mutations."""
import io
import json
import subprocess
import tarfile
from deploy import ROOT, SSH, remote

out=ROOT.parents[2]/'.local/evidence/20260911-retention-7d'
out.mkdir(exist_ok=True)
audit=r'''
import json, os, pathlib, shutil, sqlite3, subprocess, time
p=pathlib.Path('/var/lib/vpn-uplink-pilot/history.sqlite')
with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:
    count,oldest,newest=db.execute('select count(*),min(slot),max(slot) from cycles').fetchone()
    pages=db.execute('pragma page_count').fetchone()[0]
    page_size=db.execute('pragma page_size').fetchone()[0]
    free_pages=db.execute('pragma freelist_count').fetchone()[0]
disk=shutil.disk_usage(p.parent)
mem={l.split(':')[0]:int(l.split()[1])*1024 for l in pathlib.Path('/proc/meminfo').read_text().splitlines()}
state={f.name:f.stat().st_size for f in p.parent.iterdir() if f.is_file()}
services=subprocess.check_output(['systemctl','show','vpn-uplink-pilot','vpn-uplink-exporter','-p','Id','-p','MemoryCurrent','-p','CPUUsageNSec','-p','ActiveState'],text=True)
config=json.loads(pathlib.Path('/opt/vpn-monitoring/pilot/config.json').read_text())
print(json.dumps(dict(time=time.time(),cycles=count,oldest=oldest,newest=newest,
    database_bytes=p.stat().st_size,allocated_pages_bytes=pages*page_size,free_pages_bytes=free_pages*page_size,
    state_files_bytes=state,disk_total=disk.total,disk_free=disk.free,
    mem_total=mem['MemTotal'],mem_available=mem['MemAvailable'],services=services,config=config)))
'''
def inspect():
    result=subprocess.run(SSH+['/opt/vpn-monitoring/pilot/.venv/bin/python -'],
                          input=audit,text=True,capture_output=True,check=True,timeout=20)
    return json.loads(result.stdout)
before=inspect()
(out/'server-before.json').write_text(json.dumps(before,indent=2)+'\n')
desired=json.loads((ROOT/'pilot/config.json').read_text())
old=before['config'].copy()
old['retention_days']=7
assert old==desired, 'Unexpected server config changes; refuse overwrite'
assert before['oldest'] is None or before['oldest']>before['time']-7*86400, 'Old data requires separate backup'
backup=subprocess.run(SSH+['tar -czf - -C /opt/vpn-monitoring/pilot collector config.json'],
                      capture_output=True,check=True,timeout=20).stdout
(out/'before-retention-code.tar.gz').write_bytes(backup)
remote('systemctl stop vpn-uplink-pilot\n',timeout=60)
payload=io.BytesIO()
with tarfile.open(fileobj=payload,mode='w') as tar:
    for name in ('daemon.py','storage.py'):
        tar.add(ROOT/'collector/uplink_monitor'/name,arcname='collector/uplink_monitor/'+name)
    tar.add(ROOT/'pilot/config.json',arcname='config.json')
subprocess.run(SSH+['umask 077; tar --no-same-owner --no-same-permissions -xf - -C /opt/vpn-monitoring/pilot'],
               input=payload.getvalue(),check=True,timeout=20)
remote('systemctl start vpn-uplink-pilot\nsystemctl is-active vpn-uplink-pilot vpn-uplink-exporter\n')
after=inspect()
assert after['config']['retention_days']==7
(out/'server-after.json').write_text(json.dumps(after,indent=2)+'\n')
print(json.dumps(after,indent=2))
