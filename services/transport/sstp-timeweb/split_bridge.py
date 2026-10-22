"""Owned namespace connector and bounded probes, not a failover controller."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import split_policy as p

CONFIG=Path('/etc/sstp-timeweb/split-config.json')
STATE=Path('/var/lib/sstp-timeweb/split-health.json')

def run(args,input_text=None,timeout=20):
    return subprocess.check_output(args,input=input_text,text=True,timeout=timeout).strip()

def server(*args,**kw):return run(['ip','netns','exec','sstp-timeweb',*args],**kw)

def relay(config):
    value=json.loads(run(['docker','inspect','wg-relay']))[0]
    if (value['Id']!=config['container_id'] or value['Image']!=config['image']
            or not value['State']['Running']):raise ValueError('relay_identity_changed')
    class Namespace:
        def __init__(self):self.fd=os.open('/proc/'+str(value['State']['Pid'])+'/ns/net',os.O_RDONLY)
        def __call__(self,*args,input_text=None,timeout=20):
            return subprocess.check_output(['nsenter','--net=/proc/self/fd/'+str(self.fd),*args],
                input=input_text,text=True,timeout=timeout,pass_fds=(self.fd,)).strip()
        def __del__(self):
            if getattr(self,'fd',None) is not None:os.close(self.fd)
    return value['State']['Pid'],Namespace()

def cenuta_rule():
    return ['priority','218','from',p.MODES['sstp_cenuta']['relay_source']+'/32',
            'iif',p.RELAY_LINK,'table','200','protocol','243']

def verify_files(config):
    if config.get('version')!=1 or config.get('automatic_fallback') is not False:
        raise ValueError('invalid_split_configuration')
    for name,digest in config['files'].items():
        target=Path(name)
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('split_persistent_file_drift')

def up(config):
    verify_files(config)
    pid,ns=relay(config)
    existing={r['ifname'] for r in json.loads(ns('ip','-j','link'))}
    if p.RELAY_LINK in existing:raise ValueError('split_connector_already_exists')
    if any(r['ifname']==p.LINK for r in json.loads(server('ip','-j','link'))):
        raise ValueError('split_namespace_link_collision')
    rules=json.loads(ns('ip','-j','rule'))
    if any(r['priority']==218 for r in rules):raise ValueError('split_priority_collision')
    names={r['ifname'] for r in json.loads(ns('ip','-j','address'))}
    if not {'wg1','wg-up-cenuta','wg-home'}<=names:raise ValueError('relay_not_started')
    # Creation stays inside the two pinned namespaces, never in the host namespace.
    server('ip','link','add',p.LINK,'type','veth','peer','name',p.RELAY_LINK)
    server('ip','link','set',p.RELAY_LINK,'netns',str(pid))
    server('ip','address','add',p.SERVER+'/30','dev',p.LINK)
    ns('ip','address','add',p.RELAY+'/30','dev',p.RELAY_LINK)
    for command,name in ((server,p.LINK),(ns,p.RELAY_LINK)):
        command('ip','link','set',name,'mtu','1400','up')
        command('sysctl','-qw','net.ipv6.conf.'+name+'.disable_ipv6=1')
    for item in p.MODES.values():
        ns('ip','route','add',item['relay_source']+'/32','via',p.SERVER,'dev',p.RELAY_LINK,'proto','243')
        server('ip','address','add',item['probe']+'/32','dev','lo')
    ns('ip','rule','add',*cenuta_rule())
    ns('nft','-f','-',input_text=Path('/etc/sstp-timeweb/split-relay.nft').read_text())
    server('ip','route','add','default','via',p.RELAY,'dev',p.LINK,'proto','243')
    server('sysctl','-qw','net.ipv4.ip_forward=1')
    # The original management rules remain in this generated, hash-pinned file.
    tables=json.loads(server('nft','-j','list','tables'))['nftables']
    extra='delete table ip sstp_split_nat\n' if any(r.get('table',{}).get('name')=='sstp_split_nat' for r in tables) else ''
    server('nft','-f','-',input_text='delete table inet sstp_timeweb\n'+extra+Path('/etc/sstp-timeweb/namespace.nft').read_text())

def down(config):
    """Explicit connector retirement; callers must first remove SSTP assignments."""
    verify_files(config);_,ns=relay(config)
    inspect(config,probe=False,check_health=False)
    ns('nft','delete','table','inet','sstp_split_relay')
    ns('ip','rule','del',*cenuta_rule())
    for item in p.MODES.values():
        ns('ip','route','del',item['relay_source']+'/32','via',p.SERVER,'dev',p.RELAY_LINK,'proto','243')
        server('ip','address','del',item['probe']+'/32','dev','lo')
    server('ip','route','del','default','via',p.RELAY,'dev',p.LINK,'proto','243')
    server('sysctl','-qw','net.ipv4.ip_forward=0')
    server('nft','-f','-',input_text='delete table inet sstp_timeweb\ndelete table ip sstp_split_nat\n'+Path('/etc/sstp-timeweb/namespace-base.nft').read_text())
    server('ip','link','delete',p.LINK)

def inspect(config,probe=False,check_health=True):
    verify_files(config);_,ns=relay(config)
    defaults=json.loads(server('ip','-j','route','show','default'))
    if (len(defaults)!=1 or defaults[0].get('gateway')!=p.RELAY or defaults[0].get('dev')!=p.LINK):
        raise ValueError('split_default_route_drift')
    actual=json.loads(ns('ip','-j','rule'))
    rule=[r for r in actual if r['priority']==218]
    if (len(rule)!=1 or rule[0].get('src')!=p.MODES['sstp_cenuta']['relay_source']
            or rule[0].get('iif')!=p.RELAY_LINK or str(rule[0].get('table'))!='200'
            or str(rule[0].get('protocol'))!='243'):
        raise ValueError('split_selector_drift')
    # Compare structural nft JSON, stripping only volatile counters/handles.
    for command,table,name in ((ns,'inet','sstp_split_relay'),(server,'inet','sstp_timeweb'),(server,'ip','sstp_split_nat')):
        observed=json.loads(command('nft','-j','list','table',table,name))
        if normalize_nft(observed)!=config['nft_expected'][name]:raise ValueError('split_guard_drift')
    channels={}
    old=json.loads(STATE.read_text()) if STATE.is_file() else {}
    for mode,item in p.MODES.items():
        route=json.loads(ns('ip','-j','route','get','1.1.1.1','from',item['relay_source'],'iif',p.RELAY_LINK))
        if len(route)!=1 or route[0].get('dev')!=item['uplink']:raise ValueError('split_egress_drift')
        if probe:
            command=['curl','-4','--noproxy','*','--interface',item['probe'],
                '--connect-timeout','5','--max-time','8','--fail','--silent','--show-error',
                '--resolve','api.ipify.org:443:104.26.12.205','https://api.ipify.org/']
            try:
                ip=server(*command,timeout=12).strip()
                ok=ip==config['expected_exit'][mode]
            except (OSError,subprocess.SubprocessError):ip=None;ok=False
            channels[mode]=dict(ready=ok,exit_ip=ip,checked_at=time.time())
        else:
            row=old.get('channels',{}).get(mode,{})
            ok=row.get('ready') is True and 0<=time.time()-row.get('checked_at',0)<=180
            channels[mode]=dict(row,ready=ok if check_health else True)
    return dict(release=p.RELEASE,automatic_fallback=False,checked_at=time.time(),channels=channels)

def normalize_nft(document):
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('handle','metainfo','packets','bytes')}
        if isinstance(value,list):return [clean(v) for v in value if not (isinstance(v,dict) and 'metainfo' in v)]
        return value
    return clean(document)

def save(value):
    fd,temp=tempfile.mkstemp(dir=STATE.parent,prefix='.split-health-')
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.chmod(temp,0o600);os.replace(temp,STATE)
    finally:
        if os.path.exists(temp):os.unlink(temp)

if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['up','down','status','probe'])
    action=parser.parse_args().action
    try:
        config=json.loads(CONFIG.read_text())
        if action in ('up','down'):
            (up if action=='up' else down)(config);print('SPLIT_CONNECTOR_'+action.upper())
        else:
            value=inspect(config,probe=action=='probe')
            if action=='probe':save(value)
            print(json.dumps(value))
            raise SystemExit(0 if all(c['ready'] for c in value['channels'].values()) else 1)
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print(json.dumps(dict(error='split_connector_unavailable',automatic_fallback=False,channels={})))
        raise SystemExit(1)
