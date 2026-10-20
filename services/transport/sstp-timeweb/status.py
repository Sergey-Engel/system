"""Read-only status for the isolated transport. Never repairs or selects routes."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import subprocess
import sys

UNITS=('sstp-timeweb-netns.service','sstp-timeweb-server.service',
       'sstp-timeweb-probe.service','sstp-timeweb-proxy.socket')


def run(argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=10)
    if result.returncode:
        raise RuntimeError('status_command_failed')
    return result.stdout


def valid_peer(peer):
    return (peer.get('link_type')=='ppp' and 'UP' in peer.get('flags',[])
            and peer.get('mtu')==1400
            and any(r.get('family')=='inet' and r.get('local')=='10.60.65.1'
                    and r.get('address')=='10.60.65.2' and r.get('prefixlen')==32
                    for r in peer.get('addr_info',[])))


def inspect():
    manifest=json.loads(Path('/etc/sstp-timeweb/manifest.json').read_text())
    files_ok=all(Path(name).is_file() and not Path(name).is_symlink()
                 and hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
                 for name,digest in manifest['files'].items())
    states={name:run(['systemctl','is-active',name]).strip() for name in UNITS}
    links=json.loads(run(['ip','-n','sstp-timeweb','-j','-s','address']))
    peers=[r for r in links if r['ifname']=='sstptw0']
    peer=peers[0] if len(peers)==1 else {}
    address_ok=valid_peer(peer)
    routes=json.loads(run(['ip','-n','sstp-timeweb','-j','route']))
    isolated=not any(r.get('dst')=='default' for r in routes)
    expiry=run(['openssl','x509','-in','/etc/sstp-timeweb/server.pem','-noout','-enddate']).strip()
    expires=datetime.strptime(expiry.removeprefix('notAfter='),'%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
    remaining=(expires-datetime.now(timezone.utc)).total_seconds()
    ready=files_ok and all(s=='active' for s in states.values()) and address_ok and isolated and remaining>0
    return dict(ready=ready,transport='SSTP',endpoint=manifest['endpoint'],port=manifest['port'],namespace='sstp-timeweb',
                persistent_files_valid=files_ok,units=states,peer_address_valid=address_ok,
                no_namespace_default_route=isolated,mtu=peer.get('mtu'),counters=peer.get('stats64',{}),
                certificate_expires_at=expires.isoformat(),certificate_days_remaining=max(0,int(remaining//86400)),
                certificate_warning=remaining<30*86400,
                automatic_fallback=False,production_routing_enabled=False)


if __name__=='__main__':
    try:
        report=inspect()
    except (OSError,ValueError,KeyError,RuntimeError,subprocess.SubprocessError):
        report=dict(ready=False,error='transport_status_unavailable',automatic_fallback=False)
    print(json.dumps(report,sort_keys=True))
    sys.exit(0 if report['ready'] else 1)
