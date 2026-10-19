"""Exercise the real controller and strict export checks against an in-memory router."""
import copy
import json
from pathlib import Path
import re
import shlex
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import device_routing as routing
import direct_controller as direct
import managed
import sstp_direct as policy
from controller import write

KEY='02:11:22:33:44:55'
OTHER='02:11:22:33:44:66'

class Router:
    def __init__(self,site):
        self.site=site
        subnet='88' if site=='nakhimova' else '89'
        self.leases=[{'.id':'*1','address':f'192.168.{subnet}.100','mac-address':KEY,'server':'defconf',
                      'dynamic':site=='fethiye','disabled':False,'status':'waiting' if site=='nakhimova' else 'bound'},
                     {'.id':'*2','address':f'192.168.{subnet}.101','mac-address':OTHER,'server':'defconf',
                      'dynamic':False,'disabled':False,'status':'bound'}]
        self.wifi=[{'.id':'*1','mac-address':KEY,'authorized':True,'interface':'wifi1'}]
        self.members=[]
        self.specs={}
        self.extra=''
    def close(self):
        pass
    def export(self):
        lines=['/ip dns set allow-remote-requests=yes'+self.extra]
        for row in self.leases:
            if not row['dynamic']:
                lines.append('/ip dhcp-server lease add address='+row['address']+' mac-address='+row['mac-address']+' server=defconf')
        for row in self.members:
            lines.append('/ip firewall address-list add address='+row['address']+' list='+row['list']+
                         ' comment='+policy.quote(row.get('comment',''))+(' disabled=yes' if row['disabled'] else ''))
        for spec,disabled in reversed(list(self.specs.values())):
            lines.append(spec['path']+' add '+spec['properties']+' comment='+policy.quote(spec['comment'])+(' disabled=yes' if disabled else ''))
        return '\n'.join(lines)+'\n'

@pytest.fixture
def network(tmp_path,monkeypatch):
    routers={s:Router(s) for s in routing.MODES}
    n=routers['nakhimova']
    n.members=[{'.id':'*10','address':'192.168.88.101','list':'CENUTA_Devices','comment':'Neighbor','disabled':False,'dynamic':False}]
    (tmp_path/'reverse').mkdir()
    config=dict(version=1,routing_enabled=True,reverse_enabled=True,dhcp_server='defconf',reverse_dhcp_server='defconf',
                endpoint='194.61.140.217',certificate_expires=4_000_000_000,
                baseline_exports={s:r.export() for s,r in routers.items()})
    config['baseline']={s:direct.configuration_hash(e) for s,e in config['baseline_exports'].items()}
    write(tmp_path/'config.json',config)
    write(tmp_path/'state.json',dict(version=1,generation=0,clients={}))
    write(tmp_path/'reverse/state.json',dict(version=1,generation=0,clients={}))
    write(tmp_path/'routing-state.json',dict(version=1,generation=0,pending=None))
    writes=[]
    fault={'after_write':None}
    def run(c,command):
        assert command.startswith('/export terse')
        return c.export().encode()
    def rows(c,path):
        return copy.deepcopy({'/ip dhcp-server lease':c.leases,'/interface wifi registration-table':c.wifi,
                              '/ip firewall connection':[]}[path])
    def get(c,expression):
        if expression.startswith('[/ip cloud'):
            return '194.61.140.217'
        if expression.startswith('[/ip firewall address-list'):
            return copy.deepcopy(c.members)
        if 'routing-table="' in expression:
            return [dict(gateway=policy.CLIENT if c.site=='nakhimova' else policy.SERVER)]
        if expression.startswith('[/routing route'):
            return [dict(**{'routing-table':'CENUTA-Route','gateway':'wg-cenuta'}),
                    dict(**{'routing-table':'WG1-Route','gateway':'wg1'})]
        raise AssertionError(expression)
    def value(c,path,selector,field):
        if path.startswith('/interface '):
            return True
        collection=c.members if path==routing.MEMBER_PATH else c.leases
        return next(r for r in collection if r['.id']==selector).get(field,'' if field=='comment' else None)
    def mutate(c,command):
        writes.append((c.site,command))
        if command.startswith(routing.MEMBER_PATH):
            tokens=shlex.split(command[len(routing.MEMBER_PATH):].strip())
            action=tokens.pop(0)
            if action in ('set','remove'):
                ident=tokens.pop(0)
                row=next(r for r in c.members if r['.id']==ident)
                if action=='remove':
                    c.members.remove(row)
            else:
                row={'.id':'*'+format(30+len(writes),'X'),'dynamic':False,'disabled':False}
                c.members.append(row)
            if action!='remove':
                for token in tokens:
                    k,v=token.split('=',1)
                    row[k]=(v=='yes') if k=='disabled' else v
        elif command.startswith('/ip dhcp-server lease make-static '):
            next(r for r in c.leases if r['.id']==command.split()[-1])['dynamic']=False
        else:
            iface=policy.CLIENT if c.site=='nakhimova' else policy.SERVER
            direction='reverse' if c.site=='nakhimova' else 'forward'
            specs=policy.client_policy(KEY,c.leases[0]['address'],direction=direction)
            spec=next(s for s in specs if s['comment'] in command)
            disabled='disabled=yes' in command or ' disable ' in command
            c.specs[spec['comment']]=(spec,disabled)
        if fault['after_write'] and fault['after_write'](command):
            fault['after_write']=None
            raise RuntimeError('injected_unknown_write_result')
    monkeypatch.setattr(routing.access,'run',run)
    monkeypatch.setattr(routing.access,'rows',rows)
    monkeypatch.setattr(routing.access,'get',get)
    monkeypatch.setattr(routing.access,'value',value)
    monkeypatch.setattr(routing.access,'mutate',mutate)
    def controller():
        return routing.RoutingController(tmp_path,connector=lambda site:routers[site])
    def apply(mode,site='nakhimova'):
        ctl=controller()
        state=ctl.view(site)
        device=next(d for d in state['devices'] if d['id']==KEY)
        return ctl.action(site,KEY,mode,device['revision'])
    return dict(routers=routers,controller=controller,apply=apply,writes=writes,fault=fault,directory=tmp_path)

@pytest.mark.parametrize('old',routing.MODES['nakhimova'])
@pytest.mark.parametrize('new',routing.MODES['nakhimova'])
def test_all_nakhimova_mode_transitions_are_exclusive(network,old,new):
    f=network['routers']['fethiye'].export()
    neighbor=copy.deepcopy(network['routers']['nakhimova'].members[0])
    network['apply'](old)
    result=network['apply'](new)
    assert result['success'] is True
    assert next(d for d in result['devices'] if d['id']==KEY)['mode']==new
    assert network['routers']['fethiye'].export()==f
    assert neighbor in network['routers']['nakhimova'].members
    assert all(site=='nakhimova' for site,_ in network['writes'])
    assert all('/interface ' not in cmd and 'flush' not in cmd for _,cmd in network['writes'])

def test_lost_membership_ack_requires_explicit_standard_recovery(network):
    network['apply']('cenuta')
    network['fault']['after_write']=lambda cmd:cmd.startswith(routing.MEMBER_PATH+' set ')
    with pytest.raises(RuntimeError,match='unknown_write'):
        network['apply']('fornex')
    ctl=network['controller']()
    view=ctl.view('nakhimova')
    item=next(d for d in view['devices'] if d['id']==KEY)
    assert item['pending'] and item['can_apply'] and item['allowed_modes']==['local']
    assert item['mode']=='fornex'
    before=len(network['writes'])
    assert network['apply']('local')['success']
    assert network['controller']().state['pending'] is None
    assert len(network['writes'])==before+1

def test_pending_recovery_never_adopts_neighbor_drift(network):
    network['apply']('cenuta')
    network['fault']['after_write']=lambda cmd:cmd.startswith(routing.MEMBER_PATH+' set ')
    with pytest.raises(RuntimeError):
        network['apply']('fornex')
    network['routers']['nakhimova'].members[0]['comment']='Unapproved neighbor change'
    before=len(network['writes'])
    with pytest.raises(ValueError,match='outside_scope'):
        network['apply']('local')
    assert len(network['writes'])==before
    assert network['controller']().state['pending']

def test_partial_direct_add_can_recover_without_creating_more_rules(network):
    network['fault']['after_write']=lambda cmd:' add disabled=yes ' in cmd
    with pytest.raises(RuntimeError):
        network['apply']('direct')
    before=len(network['writes'])
    result=network['apply']('local')
    assert result['success'] and next(d for d in result['devices'] if d['id']==KEY)['mode']=='local'
    assert not any(' add ' in cmd for _,cmd in network['writes'][before:])
    assert all(disabled for spec,disabled in network['routers']['nakhimova'].specs.values())

def test_fethiye_wifi_only_and_no_split(network):
    ctl=network['controller']()
    view=ctl.view('fethiye')
    assert [d['id'] for d in view['devices']]==[KEY]
    with pytest.raises(ValueError,match='invalid_route_mode'):
        network['apply']('cenuta','fethiye')
    assert network['apply']('direct','fethiye')['success']
    network['routers']['fethiye'].wifi=[]
    assert network['controller']().view('fethiye')['devices']==[]
    assert network['controller']().view('fethiye')['outside_assignments']==1
    network['routers']['fethiye'].wifi=[{'.id':'*1','mac-address':KEY,'authorized':True}]
    assert network['apply']('local','fethiye')['success']

def test_old_direct_writer_cannot_bypass_exclusivity(network):
    ctl=network['controller']().controller('nakhimova')
    with pytest.raises(ValueError,match='use_unified'):
        ctl.action('add',KEY,'anything')
    assert not network['writes']

def test_stale_revision_and_binding_changes_never_start_operation(network):
    ctl=network['controller']()
    view=ctl.view('nakhimova')
    revision=next(d for d in view['devices'] if d['id']==KEY)['revision']
    network['routers']['nakhimova'].leases[0]['.id']='*90'
    with pytest.raises(ValueError,match='changed_refresh'):
        ctl.action('nakhimova',KEY,'cenuta',revision)
    assert not network['writes'] and network['controller']().state['pending'] is None


def test_unknown_configuration_change_is_not_adopted(network):
    network['routers']['nakhimova'].extra=' servers=9.9.9.9'
    with pytest.raises(ValueError,match='configuration_drift'):
        network['apply']('cenuta')
    assert not network['writes'] and network['controller']().state['pending'] is None


def test_disconnected_fethiye_client_cannot_apply_stale_choice(network):
    ctl=network['controller']()
    revision=ctl.view('fethiye')['devices'][0]['revision']
    network['routers']['fethiye'].wifi=[]
    with pytest.raises(ValueError,match='changed_refresh'):
        ctl.action('fethiye',KEY,'direct',revision)
    assert not network['writes']


def test_unavailable_split_route_never_starts_write(network,monkeypatch):
    original=routing.access.value
    monkeypatch.setattr(routing.access,'value',lambda c,path,selector,field:
                        False if path=='/interface wireguard' else original(c,path,selector,field))
    with pytest.raises(ValueError,match='selected_route_not_ready'):
        network['apply']('fornex')
    assert not network['writes'] and network['controller']().state['pending'] is None


@pytest.mark.parametrize('fail_at',[1,5,13,20,26])
def test_direct_partial_write_recovery_is_explicit_and_scoped(network,fail_at):
    network['apply']('cenuta')
    count=0
    def fail(command):
        nonlocal count
        count+=1
        return count==fail_at
    network['fault']['after_write']=fail
    with pytest.raises(RuntimeError,match='unknown_write'):
        network['apply']('direct')
    ctl=network['controller']()
    item=next(d for d in ctl.view('nakhimova')['devices'] if d['id']==KEY)
    assert item['pending'] and item['allowed_modes']==['local']
    assert network['apply']('local')['success']
    assert network['routers']['nakhimova'].members==[
        {'.id':'*10','address':'192.168.88.101','list':'CENUTA_Devices','comment':'Neighbor','disabled':False,'dynamic':False}]
