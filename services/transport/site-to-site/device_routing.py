"""Exclusive per-device routing over existing transports; no transport writer."""
import fcntl
import ipaddress
import json
from pathlib import Path
import secrets
import subprocess
import time

import direct_access as access
import direct_controller as direct
import direct_names
import managed
import sstp_direct as policy
from controller import write

RELEASE='4.3.0'
LISTS={'cenuta':'CENUTA_Devices','fornex':'VPN_Devices',
       'sstp_cenuta':'SSTP_CENUTA_Devices','sstp_fornex':'SSTP_FORNEX_Devices'}
MODES={'nakhimova':('local','cenuta','fornex','sstp_cenuta','sstp_fornex','direct'),'fethiye':('local','direct')}
OWNER='device-routing-v1'
MEMBER_PATH='/ip firewall address-list'


def split_channels(refresh=False):
    """Read the pinned server's fresh data-plane proof; never repair it."""
    try:
        result=subprocess.run(['ssh','-F',str(access.ROOT/'.local/ssh/config'),'-o','BatchMode=yes',
            '-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=2',
            'timeweb','timeout 60 python3 -B /opt/sstp-timeweb/split_bridge.py '+('probe' if refresh else 'status')],
            capture_output=True,timeout=75)
        if result.returncode not in (0,1) or len(result.stdout)>20000:raise ValueError('split_status_failed')
        value=json.loads(result.stdout)
        if value.get('automatic_fallback') is not False or value.get('error'):
            return {mode:dict(ready=False,apply_allowed=False,detail='Server configuration verification failed')
                    for mode in ('sstp_cenuta','sstp_fornex')}
        return {mode:dict(channel,apply_allowed=True) for mode,channel in value['channels'].items()}
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        return {}


def selectable(channel):
    return channel.get('apply_allowed',channel.get('ready',False)) is True


def catalog(site,rows,wifi,bindings):
    if site not in MODES:
        raise ValueError('invalid_site')
    enabled=[r for r in rows if r.get('disabled') is False]
    subnet='192.168.88.0/24' if site=='nakhimova' else '192.168.89.0/24'
    parsed=managed.leases(enabled,'defconf',subnet)
    if site=='nakhimova':
        keys={r.get('mac-address') for r in enabled if r.get('dynamic') is False}
    else:
        keys={r.get('mac-address') for r in wifi if r.get('authorized') is True}
    result={}
    for key in sorted(keys):
        key=managed.mac(key)
        item=parsed.get(key)
        if site=='nakhimova' and item is None:
            continue
        item=dict(item or dict(mac=key,ip=None,lease=None,online=True),label=bindings.get(key,'Unknown device'),
                  permanent=site=='nakhimova',manageable=item is not None)
        if site=='fethiye':
            item['online']=True
        result[key]=item
    return result


def covers(address,ip):
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(address,strict=False)
    except (ValueError,TypeError):
        return False


def host_address(value):
    try:
        network=ipaddress.ip_network(value,strict=False)
        return str(network.network_address) if network.version==4 and network.prefixlen==32 else None
    except (ValueError,TypeError):
        return None


def observed_mode(ip,members,selected):
    active=[r for r in members if r.get('list') in LISTS.values() and r.get('disabled') is False and covers(r.get('address'),ip)]
    if any(host_address(r.get('address'))!=ip for r in active):
        return 'shared'
    if len(active)+bool(selected)>1:
        return 'conflict'
    if selected:
        return 'direct'
    return next((mode for mode,name in LISTS.items() if active and active[0]['list']==name),'local')


def exact_members(rows,ip):
    result=[]
    for row in rows:
        if row.get('list') not in LISTS.values() or not covers(row.get('address'),ip):
            continue
        if (host_address(row.get('address'))!=ip or row.get('dynamic') is not False
                or type(row.get('disabled')) is not bool or row.get('timeout') not in (None,'','none-static')):
            raise ValueError('shared_or_dynamic_membership_requires_review')
        managed.identity(row['.id'])
        result.append(row)
    return result


def outside_membership(export,ip):
    result=[]
    for line in managed.export_lines(export):
        if line.startswith(MEMBER_PATH+' add '):
            _,fields=managed.tokens(line)
            if fields.get('list') in LISTS.values() and host_address(fields.get('address'))==ip:
                continue
        result.append(line)
    return '\n'.join(result)


def member_fields(export,ip):
    result=[]
    for line in managed.export_lines(export):
        if not line.startswith(MEMBER_PATH+' add '):
            continue
        _,fields=managed.tokens(line)
        if fields.get('list') not in LISTS.values() or host_address(fields.get('address'))!=ip:
            continue
        if set(fields)-{'address','list','comment','disabled'}:
            raise ValueError('unsupported_membership_selector')
        if fields.get('disabled','no') not in ('yes','no'):
            raise ValueError('invalid_membership_flag')
        result.append(dict(address=ip,list=fields['list'],comment=fields.get('comment',''),disabled=fields.get('disabled','no')))
    return result


def expected_members(before,mode,key,ip):
    if mode not in LISTS:
        return []
    comment=before[0]['comment'] if len(before)==1 else OWNER+':'+managed.mac(key).replace(':','').lower()
    return [dict(address=ip,list=LISTS[mode],comment=comment,disabled='no')]


class RoutingController:
    def __init__(self,directory=access.PRIVATE,connector=access.connect):
        self.directory=Path(directory)
        self.connector=connector
        self.config=access.private_json(self.directory/'config.json')
        self.state=access.private_json(self.directory/'routing-state.json')
        if (self.config.get('routing_enabled') is not True or self.state.get('version')!=1
                or type(self.state.get('generation')) is not int or self.state['generation']<0):
            raise ValueError('invalid_routing_state')
        op=self.state.get('pending')
        if op is not None:
            if op['site'] not in MODES or op['target'] not in MODES[op['site']]:
                raise ValueError('invalid_pending_operation')
            managed.mac(op['device'])
            managed.address(op['ip'],'192.168.88.0/24' if op['site']=='nakhimova' else '192.168.89.0/24')
            if not isinstance(op['before_export'],str) or len(op['before_export'])>8_000_000:
                raise ValueError('invalid_pending_snapshot')

    def checkpoint(self,paths):
        if self.directory.resolve()==access.PRIVATE.resolve():
            from direct_private import checkpoint
            checkpoint(paths)

    def save(self):
        self.state['generation']+=1
        write(self.directory/'routing-state.json',self.state)
        self.checkpoint([self.directory/'routing-state.json'])

    def controller(self,site):
        if site not in MODES:
            raise ValueError('invalid_site')
        return direct.DirectController(self.directory/'reverse' if site=='nakhimova' else self.directory,
            connector=self.connector,direction='reverse' if site=='nakhimova' else 'forward')

    def read_leases(self,c):
        rows=access.rows(c,'/ip dhcp-server lease')
        for row in rows:
            if row.get('server')!='defconf':
                continue
            ident=managed.identity(row['.id'])
            for flag in ('disabled','dynamic'):
                if type(row.get(flag)) is not bool:
                    row[flag]=access.value(c,'/ip dhcp-server lease',ident,flag)
                if type(row[flag]) is not bool:
                    raise ValueError('unknown_lease_flag')
        return rows

    def read_wifi(self,c):
        rows=access.rows(c,'/interface wifi registration-table')
        for row in rows:
            if type(row.get('authorized')) is not bool:
                row['authorized']=access.value(c,'/interface wifi registration-table',managed.identity(row['.id']),'authorized')
            if type(row['authorized']) is not bool:
                raise ValueError('unknown_wifi_authorization')
        return rows

    def read_members(self,c):
        selector=' or '.join('list='+policy.quote(name) for name in LISTS.values())
        rows=access.get(c,'[/ip firewall address-list print as-value where '+selector+']')
        for row in rows:
            for flag in ('disabled','dynamic'):
                if type(row.get(flag)) is not bool:
                    row[flag]=access.value(c,MEMBER_PATH,managed.identity(row['.id']),flag)
        return rows

    def validate_pending(self,c,op,ctl,export):
        clients=list(ctl.state['clients'].values())
        before=outside_membership(op['before_export'],op['ip']) if op['site']=='nakhimova' else op['before_export']
        after=outside_membership(export,op['ip']) if op['site']=='nakhimova' else export
        if direct.configuration_hash(before,clients,ctl.owner)!=direct.configuration_hash(after,clients,ctl.owner):
            raise ValueError('pending_outside_scope_drift')
        if op['site']=='nakhimova':
            original=member_fields(op['before_export'],op['ip'])
            desired=op.get('restore_members',expected_members(original,op['target'],op['device'],op['ip']))
            allowed=original+desired
            actual=member_fields(export,op['ip'])
            if len(actual)>max(len(original),len(desired)) or any(item not in allowed for item in actual):
                raise ValueError('pending_membership_not_in_plan')
            exact_members(self.read_members(c),op['ip'])
        # Validate all owned per-device selectors, flags and ordering as usual.
        ctl.config['baseline_exports'][op['site']]=export
        ctl.inspect(c)

    def capture(self,site,refresh_split=False,progress=None):
        if progress:progress(0)
        ctl=self.controller(site)
        raw_direct=ctl.status()
        if progress:progress(1)
        c=self.connector(site)
        try:
            export=access.run(c,'/export terse').decode()
            if progress:progress(2)
            valid=False
            review=False
            try:
                ctl.inspect(c)
                valid=True
            except ValueError:
                op=self.state.get('pending')
                if not op or op['site']!=site:
                    raise
                self.validate_pending(c,op,ctl,export)
                review=True
            if progress:progress(3)
            rows=self.read_leases(c)
            wifi=self.read_wifi(c) if site=='fethiye' else []
            lookup=direct_names.DeviceNames()
            devices=catalog(site,rows,wifi,lookup.bindings)
            members=self.read_members(c) if site=='nakhimova' else []
            if progress:progress(4)
            if review:raw_direct=ctl.status()
            channels={'local':dict(ready=valid,state='ready' if valid else 'unknown'),
                      'direct':dict(ready=raw_direct['available'],state=raw_direct['tunnel']['state'],
                                    apply_allowed=valid and raw_direct.get('apply_allowed',raw_direct['available']),
                                    detail=raw_direct.get('error') or raw_direct['tunnel'].get('detail',''))}
            if site=='nakhimova':
                routes=access.get(c,'[/routing route print as-value where active=yes and dst-address=0.0.0.0/0]')
                for mode,table,iface in [('cenuta','CENUTA-Route','wg-cenuta'),('fornex','WG1-Route','wg1')]:
                    defaults=[r for r in routes if r.get('routing-table')==table]
                    running=access.value(c,'/interface wireguard','[find where name="'+iface+'"]','running') is True
                    ready=(valid or review) and running and len(defaults)==1 and defaults[0].get('gateway')==iface
                    channels[mode]=dict(ready=ready,apply_allowed=valid or review,state='route-ready' if ready else 'unavailable')
                proof=(split_channels(refresh=True) if refresh_split else split_channels()) if self.config.get('sstp_split_enabled') is True else {}
                for mode,table in [('sstp_cenuta','SSTP-CENUTA'),('sstp_fornex','SSTP-FORNEX')]:
                    defaults=[r for r in routes if r.get('routing-table')==table]
                    running=access.value(c,'/interface sstp-client','[find where name="sstp-timeweb"]','running') is True if proof else False
                    ready=(valid or review) and running and proof.get(mode,{}).get('ready') is True and len(defaults)==1 and defaults[0].get('gateway')=='sstp-timeweb'
                    channels[mode]=dict(ready=ready,state='verified-egress' if ready else 'unavailable',
                        apply_allowed=(valid or review) and self.config.get('sstp_split_enabled') is True and proof.get(mode,{}).get('apply_allowed',True),
                        detail=proof.get(mode,{}).get('exit_ip') or 'SSTP egress verification unavailable')
            return dict(site=site,ctl=ctl,export=export,devices=devices,members=members,channels=channels,
                        source_valid=valid,pending_review=review,direct=raw_direct)
        finally:
            c.close()

    def revision(self,site,item,raw):
        selected=raw['ctl'].state['clients'].get(item['mac'],{})
        members=member_fields(raw['export'],item['ip']) if site=='nakhimova' and item['ip'] else []
        return managed.digest(dict(site=site,mac=item['mac'],ip=item['ip'],lease=item['lease'],
            generation=self.state['generation'],direct_generation=raw['ctl'].state['generation'],
            baseline=self.config['baseline'],members=members,selected=selected.get('selected'),pending=selected.get('pending')))

    def view(self,site,raw=None,progress=None):
        raw=raw or (self.capture(site,progress=progress) if progress else self.capture(site))
        pending=self.state.get('pending')
        devices=[]
        for key,item in raw['devices'].items():
            saved=raw['ctl'].state['clients'].get(key,{})
            mode=observed_mode(item['ip'],raw['members'],bool(saved.get('selected')))
            is_pending=bool(saved.get('pending')) or bool(pending and pending['site']==site and pending['device']==key)
            same_pending=bool(pending and pending['site']==site and pending['device']==key and pending['ip']==item['ip']
                              and pending.get('lease')==item['lease'])
            allowed=['local'] if is_pending else list(MODES[site])
            manageable=item['manageable'] and mode!='shared' and (raw['source_valid'] or same_pending and raw['pending_review'])
            manageable=manageable and (not pending or same_pending)
            if site=='nakhimova' and item['ip']:
                try:
                    exact_members(raw['members'],item['ip'])
                except ValueError:
                    manageable=False
            devices.append(dict(id=key,label=item['label'],ip=item['ip'],online=item['online'],mode=mode,
                pending=is_pending,can_apply=bool(manageable),allowed_modes=allowed,revision=self.revision(site,item,raw)))
            history=(pending if same_pending else self.state.get('history',{}).get(site+'|'+key)) or {}
            rollback_mode=history.get('previous_mode')
            matched=history.get('ip')==item['ip'] and history.get('lease')==item['lease']
            matched=matched and (same_pending or history.get('after_mode')==mode)
            devices[-1]['rollback_mode']=rollback_mode if matched and rollback_mode in MODES[site] else None
            devices[-1]['can_rollback']=bool(manageable and matched and rollback_mode in MODES[site]
                and (rollback_mode=='local' or selectable(raw['channels'].get(rollback_mode,{}))))
        eligible_ips={v['ip'] for v in raw['devices'].values()}
        outsiders={r['address'] for r in raw['members'] if r.get('disabled') is False and host_address(r.get('address')) not in eligible_ips}
        outsiders.update(v['ip'] for key,v in raw['ctl'].state['clients'].items() if v['selected'] and key not in raw['devices'])
        errors=[]
        if not raw['source_valid']:
            errors.append('Pending operation requires explicit recovery to Standard' if raw['pending_review'] else 'Source configuration unavailable or changed')
        if pending:
            errors.append('Unconfirmed operation; use Standard or an available previous-route rollback for the affected device')
        if any(d['mode'] in ('shared','conflict') for d in devices):
            errors.append('Overlapping routing assignments require review')
        return dict(controller_release=RELEASE,site=site,checked_at=time.time(),devices=devices,channels=raw['channels'],
                    outside_assignments=len(outsiders),source_ready=raw['source_valid'],error='; '.join(errors) or None)

    def adopt_baseline(self,c,site,op,ctl):
        export=access.run(c,'/export terse').decode()
        self.validate_pending(c,op,ctl,export)
        config=access.private_json(self.directory/'config.json')
        config['baseline_exports'][site]=export
        config['baseline'][site]=direct.configuration_hash(export)
        write(self.directory/'config.json',config)
        self.checkpoint([self.directory/'config.json'])
        self.config=config

    def member_identity(self,c,row):
        ident=managed.identity(row['.id'])
        for field in ('list','address','comment','disabled','dynamic'):
            expected=row.get(field,'' if field=='comment' else None)
            actual=access.value(c,MEMBER_PATH,ident,field)
            if field=='address':
                same=host_address(actual)==host_address(expected)
            else:
                same=actual==expected
            if not same:
                raise ValueError('membership_identity_changed')
        return ident

    def change_members(self,c,ip,mode,key,restore=None):
        rows=exact_members(self.read_members(c),ip)
        before=member_fields(access.run(c,'/export terse').decode(),ip)
        expected=expected_members(before,mode,key,ip) if restore is None else restore
        if (len(expected)>8 or any(r.get('address')!=ip or r.get('list') not in LISTS.values()
                or r.get('disabled') not in ('yes','no') or set(r)!={'address','list','comment','disabled'} for r in expected)):
            raise ValueError('invalid_membership_restore')
        active=[r for r in expected if r['disabled']=='no']
        if (mode in LISTS and (len(active)!=1 or active[0]['list']!=LISTS[mode])
                or mode not in LISTS and active):
            raise ValueError('invalid_membership_restore_mode')
        if mode in LISTS and len(rows)==1 and len(expected)==1:
            ident=self.member_identity(c,rows[0])
            access.mutate(c,MEMBER_PATH+' set '+ident+' list='+policy.quote(LISTS[mode])+
                          ' disabled='+expected[0]['disabled']+' comment='+policy.quote(expected[0]['comment']))
        else:
            for row in rows:
                access.mutate(c,MEMBER_PATH+' remove '+self.member_identity(c,row))
            for fields in expected:
                access.mutate(c,MEMBER_PATH+' add address='+ip+' list='+policy.quote(fields['list'])+
                              ' disabled='+fields['disabled']+' comment='+policy.quote(fields['comment']))
        after=member_fields(access.run(c,'/export terse').decode(),ip)
        if after!=expected:
            raise RuntimeError('membership_readback_failed')

    def action(self,site,key,mode,revision):
        rollback=mode=='rollback'
        if site not in MODES or not rollback and mode not in MODES[site]:
            raise ValueError('invalid_route_mode')
        key=managed.mac(key)
        previous=self.state.get('pending') or self.state.get('history',{}).get(site+'|'+key) or {}
        refresh_split=mode in ('sstp_cenuta','sstp_fornex') or rollback and previous.get('previous_mode') in ('sstp_cenuta','sstp_fornex')
        raw=self.capture(site,refresh_split=refresh_split)
        view=self.view(site,raw)
        target=next((d for d in view['devices'] if d['id']==key),None)
        if not target or not isinstance(revision,str) or not secrets.compare_digest(revision,target['revision']):
            raise ValueError('device_changed_refresh')
        history=None
        if rollback:
            if not target.get('can_rollback'):raise ValueError('rollback_not_available')
            history=self.state.get('pending') or self.state.get('history',{}).get(site+'|'+key)
            mode=target['rollback_mode']
        if not target['can_apply'] or not rollback and mode not in target['allowed_modes']:
            raise ValueError('device_not_manageable')
        if mode!='local' and not selectable(raw['channels'][mode]):
            raise ValueError('selected_route_not_ready')
        if mode==target['mode'] and not target['pending']:
            return dict(view,success=True,operation_message='Assignment already confirmed')
        c=self.connector(site)
        try:
            ctl=self.controller(site)
            op=self.state.get('pending')
            if op:
                if (not rollback and mode!='local' or op['site']!=site or op['device']!=key or op['ip']!=target['ip']
                        or op.get('lease')!=raw['devices'][key]['lease']):
                    raise ValueError('pending_recovery_only')
                self.adopt_baseline(c,site,op,ctl)
                ctl=self.controller(site)
            leases,found=ctl.inspect(c)
            rows=self.read_leases(c)
            wifi=self.read_wifi(c) if site=='fethiye' else []
            fresh=catalog(site,rows,wifi,{})
            if key not in fresh or fresh[key]['ip']!=target['ip'] or fresh[key]['lease']!=raw['devices'][key]['lease']:
                raise ValueError('device_changed_refresh')
            export=access.run(c,'/export terse').decode()
            if not op and direct.configuration_hash(export,list(ctl.state['clients'].values()),ctl.owner)!=direct.configuration_hash(raw['export'],list(ctl.state['clients'].values()),ctl.owner):
                raise ValueError('device_changed_refresh')
            if site=='nakhimova':
                exact_members(self.read_members(c),target['ip'])
            op=dict(site=site,device=key,ip=target['ip'],lease=fresh[key]['lease'],target=mode,
                    before_export=export,phase='prepared',started=time.time(),previous_mode=target['mode'],
                    previous_members=member_fields(export,target['ip']) if site=='nakhimova' else [])
            if rollback:op['restore_members']=history.get('previous_members',[])
            self.state['pending']=op
            self.save()
            saved=ctl.state['clients'].get(key)
            if saved and saved['selected'] and (mode!='direct' or saved['pending']):
                op['phase']='remove_direct';self.save()
                ctl.change_selection(c,key,'remove',fresh[key],found,require_online=False)
            if site=='nakhimova':
                op['phase']='split_membership';self.save()
                self.change_members(c,target['ip'],mode,key,restore=op.get('restore_members'))
                self.adopt_baseline(c,site,op,ctl)
                ctl=self.controller(site)
            if mode=='direct':
                op['phase']='enable_direct';self.save()
                _,found=ctl.inspect(c)
                ctl.change_selection(c,key,'add',fresh[key],found,require_online=site=='fethiye')
            op['phase']='connections';self.save()
            direct.clear_device_connections(c,target['ip'],ctl.subnet)
            op['phase']='readback';self.save()
            self.adopt_baseline(c,site,op,ctl)
            ctl=self.controller(site)
            ctl.inspect(c)
            rows=self.read_members(c) if site=='nakhimova' else []
            selected=bool(ctl.state['clients'].get(key,{}).get('selected'))
            if observed_mode(target['ip'],rows,selected)!=mode or ctl.state['clients'].get(key,{}).get('pending'):
                raise RuntimeError('exclusive_assignment_readback_failed')
            if self.directory.resolve()==access.PRIVATE.resolve():
                master=access.ROOT/'.local/config/hosts'/site/'current/router-export.rsc'
                write_payload=access.run(c,'/export terse show-sensitive')
                # Revalidate after the sensitive snapshot, before replacing its canonical copy.
                ctl.inspect(c)
                from direct_private import store
                store.write_private(master,write_payload)
                self.checkpoint([master])
            histories=self.state.setdefault('history',{})
            if rollback:histories.pop(site+'|'+key,None)
            else:histories[site+'|'+key]={k:op[k] for k in ('previous_mode','previous_members','ip','lease')}|dict(after_mode=mode)
            self.state['pending']=None
            self.save()
        finally:
            c.close()
        result=self.view(site)
        message='Previous route restored' if rollback else 'Routing assignment confirmed'
        if mode!='local' and not result['channels'].get(mode,{}).get('ready'):
            message+='; tunnel availability not confirmed. Check connectivity or restore the previous route.'
        return dict(result,success=True,operation_message=message)


def execute(site='nakhimova',device=None,mode=None,revision=None,directory=access.PRIVATE,progress=None):
    if site not in MODES:
        raise ValueError('invalid_site')
    directory=Path(directory)
    with (directory/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        ctl=RoutingController(directory)
        try:
            if mode is None:
                result=ctl.view(site,progress=progress) if progress else ctl.view(site)
            else:
                result=ctl.action(site,device,mode,revision)
        except (RuntimeError,ValueError,OSError,KeyError,TypeError) as exc:
            if progress and mode is None:progress(None)
            messages={
                'device_changed_refresh':'Device binding or assignment changed. Refresh before retrying. No new operation was started.',
                'device_not_manageable':'This device cannot be changed in the current state.',
                'selected_route_not_ready':'The selected route is not ready. No new operation was started.',
                'invalid_route_mode':'This routing mode is not available at this site.',
                'rollback_not_available':'The previous route is unavailable or the device changed. No new operation was started.',
            }
            write(directory/'routing-last-error.json',dict(error=str(exc)[:256],type=type(exc).__name__,timestamp=time.time()))
            ctl=RoutingController(directory)
            try:
                result=ctl.view(site)
            except (RuntimeError,ValueError,OSError,KeyError,TypeError):
                result=dict(controller_release=RELEASE,site=site,checked_at=time.time(),devices=[],channels={},
                            outside_assignments=0,source_ready=False,error='Router unavailable or configuration requires review')
            result.update(success=False,operation_error=messages.get(str(exc),'Operation not confirmed; saved intent retained. Refresh and recover the affected device to Standard.'))
            ctl.checkpoint([directory/'routing-last-error.json'])
        if mode is not None:
            with (directory/'routing-actions.jsonl').open('a') as log:
                log.write(json.dumps(dict(timestamp=time.time(),site=site,device=device,mode=mode,
                    success=result.get('success') is True,generation=ctl.state['generation']))+'\n')
            ctl.checkpoint([directory/'routing-actions.jsonl'])
        return result
