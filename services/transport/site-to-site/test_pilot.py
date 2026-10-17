import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("s2s_pilot", Path(__file__).with_name("pilot.py"))
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def baseline():
    return dict(serial="HM20B6QXS8H", trusted=True, contracts_ok=True,
                interfaces=["eth0", "bridge"], ports=[51820],
                networks=["192.168.89.1/24", "10.10.10.1/24"],
                router_export=('/ip address\nadd address=192.168.89.1/24 interface=bridge\n'
                               '/ip firewall filter add chain=input action=accept comment="Allow admin Mac from Deco LAN"\n'),
                owned_files=[], owned_table=False)


def test_exact_baseline_and_empty_scope_required():
    state = baseline()
    assert pilot.validate(state, pilot.fingerprint(state)) is None
    with pytest.raises(ValueError, match="baseline"):
        pilot.validate(state, "0" * 64)


def test_static_anchor_and_foreign_chain_are_checked():
    state = baseline()
    state["router_export"] = ''
    with pytest.raises(ValueError, match="anchor"):
        pilot.validate(state, pilot.fingerprint(state))
    state = baseline()
    state["router_export"] += '/ip firewall filter add chain=s2s-pilot-input action=accept\n'
    with pytest.raises(ValueError, match="chain"):
        pilot.validate(state, pilot.fingerprint(state))


@pytest.mark.parametrize("field,value", [
    ("serial", "FOREIGN"), ("trusted", False), ("contracts_ok", False),
    ("interfaces", ["wg-s2s"]), ("interfaces", ["wg-s2s-tw"]),
    ("ports", [51860]), ("networks", ["10.60.60.2/32"]),
    ("networks", ["10.60.0.0/16"]),
    ("owned_files", ["/etc/wireguard/wg-s2s.conf"]), ("owned_table", True),
])
def test_fail_before_rendering_or_writes(field, value):
    state = baseline()
    state[field] = value
    with pytest.raises(ValueError):
        pilot.validate(state, pilot.fingerprint(state))


def test_router_export_continuations_and_dotted_property():
    state = baseline()
    state["router_export"] += '/interface wireguard\nadd name=foreign ' + chr(92) + '\n        .listen-port=51860\n'
    with pytest.raises(ValueError, match="port"):
        pilot.validate(state, pilot.fingerprint(state))
    state = baseline()
    state["router_export"] += '/interface wireguard peers\nadd interface=foreign ' + chr(92) + '\n        .allowed-address=10.60.60.1/32\n'
    with pytest.raises(ValueError, match="network"):
        pilot.validate(state, pilot.fingerprint(state))


def test_ntp_dns_address_is_not_a_network_allocation():
    state = baseline()
    state["router_export"] += '/system ntp client servers add address=0.tr.pool.ntp.org\n'
    pilot.validate(state, pilot.fingerprint(state))


def test_guard_is_fail_closed_and_scoped():
    rules = pilot.guard_rules()
    assert 'table inet s2s_pilot' in rules
    assert 'hook forward priority -50' in rules
    assert 'iifname "wg-s2s" counter drop' in rules
    assert 'oifname "wg-s2s" counter drop' in rules
    assert 'ip saddr 10.60.60.3 ip daddr 10.60.60.1 icmp type { echo-request, echo-reply }' in rules
    assert "flush ruleset" not in rules
    assert "reality_fornex" not in rules
    assert "ct state established" not in rules


def test_bad_guard_rejected_before_bundle():
    with pytest.raises(ValueError, match="guard"):
        pilot.bundle("A" * 43 + "=", "B" * 43 + "=", "accept")


def test_configs_have_no_default_or_lan_routes():
    files = pilot.bundle("A" * 43 + "=", "B" * 43 + "=", pilot.guard_rules())
    assert "AllowedIPs = 10.60.60.3/32" in files["/etc/wireguard/wg-s2s.conf"]
    assert all("0.0.0.0/0" not in body and "192.168.89" not in body for body in files.values())
    dropin = files["/etc/systemd/system/wg-quick@wg-s2s.service.d/pilot.conf"]
    assert "Requires=s2s-pilot-guard.service" in dropin
    assert "ExecStartPre=" in dropin


def test_router_guards_created_before_interface_enabled():
    commands = pilot.router_commands("A" * 43 + "=", "B" * 43 + "=")
    assert commands[0].startswith('/interface wireguard add disabled=yes')
    enable = next(i for i, x in enumerate(commands) if x.startswith('/interface wireguard enable'))
    guards = [i for i, x in enumerate(commands) if '/ip firewall filter add' in x]
    assert len(guards) == 5 and max(guards) < enable
    assert 'place-before=0' not in ' '.join(commands)
    assert 'jump-target=s2s-pilot-input' in commands[guards[-1]]
    assert 'chain=s2s-pilot-input action=accept' in commands[guards[2]]
    assert 'chain=s2s-pilot-input action=drop' in commands[guards[3]]
    assert 'persistent-keepalive=25s' in ' '.join(commands)
