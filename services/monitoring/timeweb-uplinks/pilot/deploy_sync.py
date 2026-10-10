"""Back up the running pilot, update its API, and start the Mac mirror."""

from pathlib import Path
import sys
import datetime
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tarfile
from deploy import ROOT, SSH


def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence=ROOT.parents[2] / '.local/evidence'/f'{stamp}-history-sync'
    evidence.mkdir(mode=0o700)
    script='''import sqlite3,io,tarfile,sys
source=sqlite3.connect('file:/var/lib/vpn-uplink-pilot/history.sqlite?mode=ro',uri=True)
target=sqlite3.connect(':memory:')
source.backup(target)
assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
blob=target.serialize()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
    info=tarfile.TarInfo('history.sqlite'); info.size=len(blob); info.mode=0o600
    tar.addfile(info,io.BytesIO(blob))
    for path in ('/opt/vpn-monitoring/pilot/collector','/opt/vpn-monitoring/pilot/config.json',
                 '/etc/systemd/system/vpn-uplink-exporter.service'):
        tar.add(path,arcname=path.lstrip('/'))
'''
    backup=subprocess.run(SSH+['/opt/vpn-monitoring/pilot/.venv/bin/python -'],input=script.encode(),
                          capture_output=True,timeout=40)
    if backup.returncode:
        raise RuntimeError('Backup failed; deployment not started: '+backup.stderr.decode(errors='replace'))
    path=evidence/'before-sync.tar.gz'; path.write_bytes(backup.stdout); path.chmod(0o600)
    with tarfile.open(path) as tar:
        assert 'history.sqlite' in tar.getnames()
    subprocess.run([sys.executable,str(ROOT/'pilot/update.py')],check=True,timeout=120)
    home=Path.home()
    data=home/'Library/Application Support/timeweb-uplinks'
    data.mkdir(mode=0o700,parents=True,exist_ok=True)
    config=dict(Label='com.sergey.timeweb-uplink-history',
        ProgramArguments=[sys.executable,'-m','uplink_monitor.sync_daemon',
                          '--database',str(data/'history.sqlite')],
        WorkingDirectory=str(ROOT/'collector'),RunAtLoad=True,KeepAlive=True,ThrottleInterval=30,
        StandardOutPath=str(data/'sync.log'),StandardErrorPath=str(data/'sync-error.log'))
    encoded=plistlib.dumps(config)
    (ROOT/'pilot/com.sergey.timeweb-uplink-history.plist').write_bytes(encoded)
    plist=home/'Library/LaunchAgents/com.sergey.timeweb-uplink-history.plist'
    plist.write_bytes(encoded)
    domain=f'gui/{os.getuid()}'
    subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True,timeout=10)
    print(json.dumps(dict(evidence=str(evidence),database=str(data/'history.sqlite'))),flush=True)


if __name__=='__main__':
    main()
