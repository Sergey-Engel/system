import importlib.util
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
spec=importlib.util.spec_from_file_location('sstp_tw_policy',Path(__file__).with_name('policy.py'))
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def test_client_is_separate_and_never_selects_routes():
    command=p.client_command('a'*40)
    assert 'disabled=yes' in command and 'add-default-route=no' in command
    assert 'port=443' in command and 'connect-to=91.222.238.208' in command
    assert 'verify-server-certificate=yes' in command
    assert 'verify-server-address-from-certificate=yes' in command and 'tls-version=only-1.2' in command
    assert 'ciphers=aes256-gcm-sha384' in command and 'pfs=required' in command
    assert '/ip route' not in command and 'wireguard' not in command
    assert 'use-ipv6=no' in p.profile_command()


@pytest.mark.parametrize('value',['short','a'*40+'\n','a'*40+';bad','"'+'a'*40])
def test_credential_injection_is_rejected(value):
    with pytest.raises(ValueError):
        p.client_command(value)


def test_server_has_only_sstp_and_fixed_static_peer():
    config=p.server_config()
    modules=config.split('[modules]\n',1)[1].split('\n[core]')[0].splitlines()
    assert 'sstp' in modules and 'auth_mschap_v2' in modules
    assert not {'pptp','l2tp','pppoe','radius','auth_pap','auth_mschap_v1'}.intersection(modules)
    assert 'bind=127.0.0.1' in config and 'ssl-protocol=tls1.2' in config
    assert 'ssl-keyfile=/etc/sstp-timeweb/server.key' in config
    assert 'ipv6=deny' in config and 'max-sessions=1' in config
    assert 'gw-ip-address='+p.LOCAL in config


def test_guards_do_not_allow_lan_transit_or_wan_management():
    guards=p.guards()
    assert len(guards)==8 and len({tag for path,props,tag in guards})==8
    for path,props,tag in guards:
        assert tag.startswith(p.OWNER+':')
        assert p.INTERFACE in props
        if 'action=accept' in props:
            assert 'chain=input' in props and 'src-address='+p.LOCAL in props and 'dst-address='+p.PEER in props
        if 'chain=forward' in props:
            assert 'action=drop' in props
    namespace=p.namespace_guard()
    assert 'policy drop' in namespace and 'chain forward' in namespace
    assert 'masquerade' not in namespace and 'snat' not in namespace


def test_socket_activation_crosses_namespace_without_root_veth_or_routes():
    units=p.units('5.18.141.112')
    assert len(units)==5
    socket=units['sstp-timeweb-proxy.socket']
    assert 'ListenStream=91.222.238.208:443' in socket and 'IPAddressDeny=any' in socket
    assert 'IPAddressAllow=5.18.141.112/32' in socket
    assert 'NetworkNamespacePath=' not in socket
    for name in ('sstp-timeweb-server.service','sstp-timeweb-proxy.service','sstp-timeweb-probe.service'):
        assert 'NetworkNamespacePath=/run/netns/sstp-timeweb' in units[name]
        assert 'NoNewPrivileges=yes' in units[name]
        assert 'CPUQuota=25%' in units[name] and 'MemoryMax=128M' in units[name]
    assert 'FreeBind=yes' in socket
    assert 'systemd-socket-proxyd' in units['sstp-timeweb-proxy.service']
    assert all('wg-relay' not in body and 'xray' not in body for body in units.values())
    assert 'ListenStream=94.241.171.65:443' not in socket
    assert '127.0.0.1:5444' in units['sstp-timeweb-proxy.service']


@pytest.mark.parametrize('source',['127.0.0.1','192.168.1.2','999.1.1.1','5.18.141.112\nExecStart=bad'])
def test_socket_source_must_be_one_public_ip(source):
    with pytest.raises(ValueError):
        p.units(source)


def test_namespace_code_never_changes_root_firewall_or_routes():
    source=Path(__file__).with_name('namespace.py').read_text()
    assert "run('ip','netns','exec',NAME,'nft'" in source
    assert "run('nft'" not in source
    assert "'route'" not in source and "'veth'" not in source
    assert "'ip','netns','pids',NAME" in source
    assert '/etc/sstp-timeweb/namespace.nft' in source


def test_guard_anchor_preserves_direct_rules_and_ignores_dynamic_placeholders():
    rows=[{'.id':'*0','chain':'forward','dynamic':True},
          {'.id':'*1','chain':'forward','comment':'s2s-sstp-reverse-v1:device-a:leak'},
          {'.id':'*2','chain':'input','comment':'default'},
          {'.id':'*3','chain':'forward','comment':'default'}]
    assert p.guard_anchor(rows,'forward')=='*3'
    assert p.guard_anchor(rows,'input')=='*2'
    assert p.guard_anchor(rows,'output') is None


def test_namespace_creation_handles_empty_iproute2_inventory(monkeypatch):
    spec=importlib.util.spec_from_file_location('sstp_tw_namespace',Path(__file__).with_name('namespace.py'))
    ns=importlib.util.module_from_spec(spec);spec.loader.exec_module(ns)
    calls=[]
    def run(*args):
        calls.append(args)
        return ''
    monkeypatch.setattr(ns,'run',run)
    ns.main('up')
    assert ('ip','netns','add',ns.NAME) in calls
    calls.clear()
    ns.main('down')
    assert calls==[('ip','-j','netns','list')]


@pytest.mark.parametrize('raw',['not-json','{}','["unknown"]','[{"id":1}]'])
def test_namespace_inventory_corruption_is_not_treated_as_empty(monkeypatch,raw):
    spec=importlib.util.spec_from_file_location('sstp_tw_namespace',Path(__file__).with_name('namespace.py'))
    ns=importlib.util.module_from_spec(spec);spec.loader.exec_module(ns)
    calls=[]
    def run(*args):
        calls.append(args)
        return raw
    monkeypatch.setattr(ns,'run',run)
    with pytest.raises(ValueError):ns.main('up')
    assert calls==[('ip','-j','netns','list')]
