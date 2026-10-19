"""Unified routing eligibility, exclusive modes and exact membership scope."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import device_routing as r

KEY='02:11:22:33:44:55'
OTHER='02:11:22:33:44:66'

def lease(key=KEY,ip='192.168.88.100',**fields):
    return dict({'.id':'*1','mac-address':key,'address':ip,'server':'defconf','status':'waiting',
                 'dynamic':False,'disabled':False},**fields)

def test_nakhimova_only_permanent_including_offline_and_directory_names():
    rows=[lease(comment='Do not infer this name'),lease(OTHER,'192.168.88.101',dynamic=True)]
    devices=r.catalog('nakhimova',rows,[],{KEY:'Known device'})
    assert list(devices)==[KEY]
    assert devices[KEY]['label']=='Known device' and devices[KEY]['online'] is False
    assert r.catalog('nakhimova',[lease()],[],{})[KEY]['label']=='Unknown device'
    assert not r.catalog('nakhimova',[lease(disabled=True)],[],{})

def test_fethiye_requires_actual_authorized_wifi_not_dhcp_bound():
    rows=[lease(ip='192.168.89.100',dynamic=True,status='bound'),lease(OTHER,'192.168.89.101',status='bound')]
    wifi=[dict(**{'mac-address':KEY,'authorized':True,'interface':'wifi1'})]
    assert set(r.catalog('fethiye',rows,wifi,{}))=={KEY}
    assert not r.catalog('fethiye',rows,[dict(wifi[0],authorized=False)],{})
    unknown=r.catalog('fethiye',[],wifi,{})[KEY]
    assert unknown['ip'] is None and unknown['manageable'] is False

def test_duplicate_bindings_fail_closed():
    with pytest.raises(ValueError):
        r.catalog('nakhimova',[lease(),lease(OTHER)],[],{})

def test_membership_and_direct_overlap_is_not_hidden():
    item=dict(address='192.168.88.100',list='CENUTA_Devices',disabled=False,dynamic=False,comment='Original')
    assert r.observed_mode('192.168.88.100',[item],False)=='cenuta'
    assert r.observed_mode('192.168.88.100',[item],True)=='conflict'
    assert r.observed_mode('192.168.88.100',[item,dict(item,list='VPN_Devices')],False)=='conflict'
    assert r.observed_mode('192.168.88.100',[dict(item,disabled=True)],False)=='local'
    assert r.observed_mode('192.168.88.100',[dict(item,address='192.168.88.0/24')],False)=='shared'

def test_projection_ignores_only_exact_host_membership():
    base='/ip firewall nat add chain=srcnat action=masquerade\n'
    item='/ip firewall address-list add address=192.168.88.100 comment=Original list=CENUTA_Devices\n'
    neighbor=item.replace('.100 ','.101 ')
    assert r.outside_membership(base+item,'192.168.88.100')==r.outside_membership(base,'192.168.88.100')
    assert r.outside_membership(base+neighbor,'192.168.88.100')!=r.outside_membership(base,'192.168.88.100')
    assert r.outside_membership(base+item.replace('CENUTA_Devices','UNRELATED'),'192.168.88.100')!=r.outside_membership(base,'192.168.88.100')
    assert r.outside_membership(base+item.replace('.100 ','.0/24 '),'192.168.88.100')!=r.outside_membership(base,'192.168.88.100')

def test_member_validation_rejects_dynamic_timeout_or_shared_records():
    item={'.id':'*1','list':'CENUTA_Devices','address':'192.168.88.100','comment':'Original','disabled':False,'dynamic':False}
    assert r.exact_members([item],'192.168.88.100')==[item]
    for fields in (dict(dynamic=True),dict(timeout='1h'),dict(address='192.168.88.0/24')):
        with pytest.raises(ValueError):
            r.exact_members([dict(item,**fields)],'192.168.88.100')
