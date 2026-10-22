"""Split policy is additive, preserves exceptions, and cannot select BTH."""
import importlib.util
from pathlib import Path
import pytest

def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
p=module('split_policy');base=module('policy')

def native():
    result=[]
    for name in ('CENUTA_Devices','VPN_Devices'):
        for fields in (dict(action='accept',**{'dst-address-list':'Local_Networks'}),
                       dict(action='mark-routing',**{'dst-address':'195.133.216.210','new-routing-mark':'old','passthrough':'no'}),
                       dict(action='accept',**{'dst-address-list':'RU_Networks'}),
                       dict(action='mark-routing',**{'new-routing-mark':'old','passthrough':'no'})):
            result.append(dict(fields,chain='prerouting',**{'src-address-list':name}))
    return result

def test_clones_native_exception_order_and_does_not_mutate_original():
    original=native();snapshot=repr(original);objects=p.router_objects(original)
    assert repr(original)==snapshot
    for mode,item in p.MODES.items():
        rows=[s['fields'] for s in objects if s['path']=='/ip firewall mangle' and s['fields'].get('src-address-list')==item['list']]
        assert [r.get('dst-address-list') for r in rows]==['Local_Networks',None,'RU_Networks',None]
        assert all(r.get('new-routing-mark',item['table'])==item['table'] for r in rows)
        assert all(r['in-interface']=='bridge' for r in rows)
        routes=[s['fields'] for s in objects if s['path']=='/ip route' and s['fields']['routing-table']==item['table']]
        assert len(routes)==2 and any(r.get('blackhole')=='yes' for r in routes)
    assert all(s['tag'].startswith(p.OWNER+':') for s in objects)
    assert not any('wg-home' in repr(s) or s['path']=='/interface wireguard' for s in objects)

def test_unreviewed_exceptions_fail_before_any_commands():
    for rows in ([],[dict(r,chain='output') for r in native()],
                 [dict(r,**{'connection-mark':'foreign'}) for r in native()]):
        with pytest.raises(ValueError):p.router_objects(rows)

def test_sstp_namespace_management_and_root_isolation_preserved():
    rules=p.namespace_rules(base.namespace_guard())
    assert 'tcp dport 22 accept' in rules and 'tcp dport 8080 accept' in rules
    assert 'policy drop' in rules and 'ct state established,related' in rules
    assert 'snat to 10.50.50.245' in rules and 'snat to 10.10.10.245' in rules
    assert 'wg-home' not in rules and 'eth0' not in rules
    with pytest.raises(ValueError):p.namespace_rules('unknown guard')

def test_relay_drops_wrong_egress_without_touching_unrelated_packets():
    guard=p.relay_guard()
    assert 'policy accept' in guard and 'iifname "sstprelay0" drop' in guard
    assert 'oifname "sstprelay0" drop' in guard
    assert 'wg-home' not in guard and '10.30.30.' not in guard
    assert guard.count('masquerade')==2


def test_routeros_flag_properties_are_bare_tokens_not_assignments():
    assert p.properties(dict(name='fixture',fib='yes'))=='name="fixture" fib'
    assert p.properties(dict(blackhole='yes',distance='254'))=='blackhole distance="254"'
    assert p.router_probe('sstp_cenuta').endswith('do-not-fragment]')
    assert '10.60.65.10' in p.router_probe('sstp_cenuta')
