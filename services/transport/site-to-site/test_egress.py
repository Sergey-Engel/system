import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("s2s_egress", Path(__file__).with_name("egress.py"))
egress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(egress)


def baseline():
    return dict(trusted=True, contracts_ok=True, files_ok=True, guard_ok=True,
                client=dict(ip="192.168.89.197", mac="A2:C1:5E:29:F5:8E", bound=True),
                sites={name:dict(serial=spec["serial"], ipip_available=True, interfaces=["bridge", "wg-s2s-tw"],
                                 tables=["main"], networks=["192.168.88.0/24", "192.168.89.0/24", "10.60.60.0/29"],
                                 owner_empty=True, anchors_ok=True, peer_allowed=spec["before_allowed"])
                       for name,spec in egress.SITES.items()})


def test_pinned_baseline_required():
    state=baseline(); egress.validate(state,egress.fingerprint(state))
    with pytest.raises(ValueError): egress.validate(state,"0"*64)


@pytest.mark.parametrize("field", ["trusted","contracts_ok","files_ok","guard_ok"])
def test_bad_global_gates_refused(field):
    state=baseline(); state[field]=False
    with pytest.raises(ValueError): egress.validate(state,egress.fingerprint(state))


@pytest.mark.parametrize("field,value", [("serial","FOREIGN"),("ipip_available",False),
    ("interfaces",["ipip-s2s-egress"]),("tables",["s2s_remote"]),
    ("networks",["10.60.61.0/24"]),("owner_empty",False),("anchors_ok",False),("peer_allowed","0.0.0.0/0")])
def test_router_scope_drift_refused(field,value):
    state=baseline(); state["sites"]["fethiye"][field]=value
    with pytest.raises(ValueError): egress.validate(state,egress.fingerprint(state))


@pytest.mark.parametrize("field,value", [("bound",False),("ip","192.168.89.198"),("mac","00:00:00:00:00:00")])
def test_target_is_not_guessed(field,value):
    state=baseline(); state["client"][field]=value
    with pytest.raises(ValueError): egress.validate(state,egress.fingerprint(state))


@pytest.mark.parametrize("dynamic", [False, None, "true", 1])
def test_lease_dynamic_flag_must_be_typed_and_explicit(dynamic):
    lease={"address":egress.CLIENT,"mac-address":egress.MAC,"status":"bound"}
    with pytest.raises(ValueError): egress.client_lease(lease,dynamic)


def test_current_dynamic_lease_identity_is_exact():
    lease={"address":egress.CLIENT,"mac-address":egress.MAC,"status":"bound"}
    assert egress.client_lease(lease,True)==dict(ip=egress.CLIENT,mac=egress.MAC,bound=True)
    for field,value in [("address","192.168.89.198"),("mac-address","00:00:00:00:00:00"),("status","waiting")]:
        with pytest.raises(ValueError): egress.client_lease({**lease,field:value},True)


def test_wg_peer_addresses_stay_specific():
    for site,spec in egress.SITES.items():
        commands=egress.transport_commands(site)
        assert commands[0].startswith('/interface ipip add disabled=yes')
        assert 'mtu=1400 clamp-tcp-mss=yes' in commands[0]
        assert all('0.0.0.0/0' not in c and 'private-key' not in c for c in commands)
        assert any(spec['after_allowed'] in c for c in commands)
        assert commands[-1].startswith('/interface wireguard peers set')


def test_dns_and_remote_route_are_disabled_in_local_mode():
    commands=egress.client_commands()
    assert sum('/ip firewall nat add' in c for c in commands)==2
    assert all('disabled=yes' in c and 'src-mac-address=A2:C1:5E:29:F5:8E' in c
               for c in commands if '/ip firewall nat add' in c)
    route_rules=[c for c in commands if '/routing rule add' in c]
    assert len(route_rules)==4 and all('disabled=yes' in c for c in route_rules)
    assert 'action=lookup-only-in-table table=s2s_remote' in route_rules[-1]
    assert any('blackhole' in c and 'routing-table=s2s_remote' in c for c in commands)
    assert all('routing-table=main' not in c for c in commands if '/ip route add' in c)


def test_ipv6_guards_use_chain_specific_static_anchors():
    commands=[c for c in egress.client_commands() if c.startswith('/ipv6 firewall filter add')]
    assert len(commands)==3
    for command in commands:
        chain='forward' if 'chain=forward ' in command else 'input'
        assert f'find where chain={chain} and comment=' in command


def test_remote_dns_preset_uses_qualified_resolver_without_local_fallback():
    commands=[c for c in egress.client_commands() if c.startswith('/ip firewall nat add')]
    assert len(commands)==2
    assert all('to-addresses=9.9.9.9 to-ports=53' in c and 'disabled=yes' in c for c in commands)
    assert all('1.1.1.1' not in c for c in commands)


def test_return_path_scoped_to_wan_not_lan():
    commands=egress.return_commands()
    rule=next(c for c in commands if '/routing rule add' in c)
    assert 'interface=ether1 dst-address=192.168.89.197/32' in rule
    assert 'place-before=' in rule and 'GLOBAL: Local bypass for ALL' in rule
    assert all('/ip firewall nat' not in c and 'new-routing-mark' not in c for c in commands)


def test_mode_order_guards_before_remote_clear_only_target():
    commands=egress.mode_commands('remote')
    clear=next(i for i,c in enumerate(commands) if '/ip firewall connection remove' in c)
    route=next(i for i,c in enumerate(commands) if '/routing rule enable' in c)
    assert 'wan-guard' in commands[0] and clear<route
    assert all('find]' not in c for c in commands if 'connection remove' in c)
    assert '197' in commands[clear] and 'src-address~' in commands[clear]
    local=egress.mode_commands('local')
    assert local[0].startswith('/routing rule disable')
    assert 'wan-guard' in local[-1]


def test_host_only_adds_authenticated_ipip_pair_not_internet():
    before=egress.lan_guard()
    after=egress.guard_rules(before)
    assert after.split('chain forward')[0]==before.split('chain forward')[0]
    assert after.count('ip protocol 4')==2
    assert 'ip saddr 10.60.60.2 ip daddr 10.60.60.3 ip protocol 4' in after
    assert '0.0.0.0/0' not in after and 'masquerade' not in after
    assert 'iifname "wg-s2s" oifname "wg-s2s"' in after
    with pytest.raises(ValueError): egress.guard_rules(before+'# drift')


def test_profiles_change_only_peer_vpn_address_not_default_or_identity():
    before='PrivateKey = unchanged\nAllowedIPs = 10.60.60.1/32, 192.168.88.0/24\n'
    after=egress.profile(before,'fethiye')
    assert after.replace('10.60.60.1/32, 10.60.60.2/32','10.60.60.1/32')==before
    assert '0.0.0.0/0' not in after


def test_forwarding_excludes_invalid_and_restricts_one_client():
    for site in egress.SITES:
        commands=egress.transport_commands(site)
        flows=[c for c in commands if 'chain=s2s-egress-forward action=accept' in c]
        assert len(flows)==2
        assert f'src-address={egress.CLIENT}/32' in flows[0]
        assert 'connection-state=new,established,related ' in flows[0]
        assert f'dst-address={egress.CLIENT}/32' in flows[1]
        assert 'connection-state=established,related ' in flows[1]
        assert any('chain=s2s-egress-forward action=drop' in c for c in commands)
    assert any('dst-address-list=!s2s-egress-not-internet' in c for c in egress.transport_commands('nakhimova'))


def controls():
    return [dict(path=path,row={".id":f"*{i:X}","comment":egress.OWNER+":"+name,"disabled":True})
            for i,(name,path) in enumerate(egress.CONTROL_PATHS.items(),1)]


@pytest.mark.parametrize("change", ["missing","duplicate","wrong-id","wrong-path","missing-flag","string-flag"])
def test_pinned_mode_controls_fail_closed(change):
    values=controls()
    if change=="missing": values.pop()
    elif change=="duplicate": values.append(values[0])
    elif change=="wrong-id": values[0]["row"][".id"]="*1; /system reboot"
    elif change=="wrong-path": values[0]["path"]="/ip route"
    elif change=="missing-flag": del values[0]["row"]["disabled"]
    else: values[0]["row"]["disabled"]="false"
    with pytest.raises(ValueError): egress.pinned_mode_commands("remote",values)


def test_pinned_switch_uses_exact_ids_and_scoped_conntrack():
    remote=egress.pinned_mode_commands("remote",controls())
    local=egress.pinned_mode_commands("local",controls())
    assert remote[0]=="/ip firewall filter enable *1"
    assert local[-1]=="/ip firewall filter disable *1"
    assert all("find" not in c for c in remote+local if "connection remove" not in c)
    assert sum(" enable " in c for c in remote)==10
    assert sum(" disable " in c for c in local)==10
    assert all('197(:|\\$)' in c for c in remote+local if "connection remove" in c)


def test_mode_export_only_ignores_approved_flags_and_binding():
    before="\n".join(f'{path} add action=drop comment="{egress.OWNER}:{name}" disabled=yes'
                     for name,path in egress.CONTROL_PATHS.items())
    after=before.replace(" disabled=yes", "")+f'\n/ip dhcp-server lease add address={egress.CLIENT} comment={egress.OWNER}:client-binding'
    assert egress.mode_export(before)==egress.mode_export(after)
    assert egress.mode_export(before+"\n/ip dns set servers=1.1.1.1")!=egress.mode_export(after)
    assert egress.mode_export(before.replace("action=drop","action=accept",1))!=egress.mode_export(after)
    with pytest.raises(ValueError): egress.mode_export(before+"\n"+before.splitlines()[0])
    with pytest.raises(ValueError): egress.mode_export("\n".join(before.splitlines()[1:]))


def tunnel():
    return {".id":"*42","name":egress.TUNNEL,"comment":egress.OWNER+":tunnel",
            "local-address":"10.60.60.3","remote-address":"10.60.60.2","disabled":False}


@pytest.mark.parametrize("field,value", [(".id","*42; /system reboot"),("name","wg-s2s-tw"),
    ("comment","foreign:tunnel"),("local-address","10.60.60.2"),
    ("remote-address","10.60.60.1"),("disabled","false")])
def test_outage_toggle_refuses_foreign_or_untyped_target(field,value):
    with pytest.raises(ValueError): egress.outage_command({**tunnel(),field:value},False)


def test_outage_toggle_only_changes_pinned_ipip():
    assert egress.outage_command(tunnel(),False)=="/interface ipip disable *42"
    assert egress.outage_command({**tunnel(),"disabled":True},True)=="/interface ipip enable *42"
    with pytest.raises(ValueError): egress.outage_command(tunnel(),"yes")


def test_outage_export_preserves_endpoints_and_unrelated_flags():
    controls="\n".join(f'{path} add comment={egress.OWNER}:{name} disabled=yes' for name,path in egress.CONTROL_PATHS.items())
    line=f'/interface ipip add comment={egress.OWNER}:tunnel local-address=10.60.60.3 name={egress.TUNNEL} remote-address=10.60.60.2'
    before=controls+"\n"+line
    assert egress.outage_export(before)==egress.outage_export(before.replace(line,line+" disabled=yes"))
    assert egress.outage_export(before)!=egress.outage_export(before.replace("remote-address=10.60.60.2","remote-address=10.60.60.1"))
    assert egress.outage_export(before+"\n/interface ethernet set ether1 disabled=yes")!=egress.outage_export(before+"\n/interface ethernet set ether1 disabled=no")
    with pytest.raises(ValueError): egress.outage_export(controls)
    with pytest.raises(ValueError): egress.outage_export(before+"\n"+line)


def outage_routes():
    return [{".id":"*1","comment":egress.OWNER+":remote-default","routing-table":"s2s_remote","dst-address":"0.0.0.0/0","distance":1},
            {".id":"*2","comment":egress.OWNER+":remote-blackhole","routing-table":"s2s_remote","dst-address":"0.0.0.0/0","distance":254}]


def test_outage_election_uses_positive_rib_rows_even_without_false_flags():
    routes=outage_routes()
    assert egress.outage_route_selection(routes,[routes[0]],False)=="*1"
    assert egress.outage_route_selection(routes,[routes[1]],True)=="*2"
    with pytest.raises(ValueError): egress.outage_route_selection(routes,[routes[0]],True)
    with pytest.raises(ValueError): egress.outage_route_selection(routes,[routes[1]],False)


@pytest.mark.parametrize("active", [[],[0,1],[2]])
def test_outage_missing_duplicate_or_foreign_election_fails(active):
    routes=outage_routes(); candidates=routes+[{**routes[0],".id":"*99"}]
    with pytest.raises(ValueError): egress.outage_route_selection(routes,[candidates[i] for i in active],False)
