import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("s2s_lan", Path(__file__).with_name("lan.py"))
lan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lan)


def baseline():
    sites = {}
    for name, serial, old in (("nakhimova", "HKM0BDXYG74", "s2s-nakhimova-20261016"),
                             ("fethiye", "HM20B6QXS8H", "s2s-pilot-20261016")):
        sites[name] = dict(serial=serial, trusted=True, peer_allowed="10.60.60.1/32", routes=[],
                           filters=[{"comment": old + ":forward-in", "chain": "forward", "action": "drop", "dynamic": False},
                                    {"comment": old + ":icmp", "chain": "s2s-pilot-input", "action": "accept", "dynamic": False}])
    return dict(contracts_ok=True, files_ok=True, guard_ok=True, sites=sites,
                hub_allowed=["10.60.60.2/32", "10.60.60.3/32"], hub_routes=["0.0.0.0/0", "10.60.60.0/29"])


def test_exact_baseline_and_identity_required():
    state = baseline()
    lan.validate(state, lan.fingerprint(state))
    with pytest.raises(ValueError, match="baseline"):
        lan.validate(state, "0" * 64)
    state["sites"]["fethiye"]["serial"] = "FOREIGN"
    with pytest.raises(ValueError, match="identity"):
        lan.validate(state, lan.fingerprint(state))


@pytest.mark.parametrize("field,value", [("contracts_ok", False), ("files_ok", False), ("guard_ok", False),
                                         ("hub_allowed", ["0.0.0.0/0"]), ("hub_routes", ["192.168.88.0/24"])])
def test_unreviewed_hub_or_occupied_route_rejected(field, value):
    state = baseline(); state[field] = value
    with pytest.raises(ValueError): lan.validate(state, lan.fingerprint(state))


@pytest.mark.parametrize("field,value", [("trusted", False), ("peer_allowed", "0.0.0.0/0"),
                                         ("routes", ["192.168.89.0/24"]), ("filters", [])])
def test_router_drift_rejected(field, value):
    state = baseline(); state["sites"]["nakhimova"][field] = value
    with pytest.raises(ValueError): lan.validate(state, lan.fingerprint(state))


def test_repeated_owned_scope_or_duplicate_static_anchor_rejected():
    for rule in ({"comment": lan.OWNER + ":foreign"}, baseline()["sites"]["fethiye"]["filters"][0]):
        state = baseline(); state["sites"]["fethiye"]["filters"].append(rule)
        with pytest.raises(ValueError): lan.validate(state, lan.fingerprint(state))


def test_only_two_allowed_ips_lines_change_no_keys_defaults_or_endpoints():
    before = "[Interface]\nPrivateKey = unchanged\nListenPort = 51860\n\n[Peer]\nPublicKey = n\nAllowedIPs = 10.60.60.2/32\n\n[Peer]\nPublicKey = f\nAllowedIPs = 10.60.60.3/32\n"
    after = lan.hub_config(before, before)
    assert after.replace(", 192.168.88.0/24", "").replace(", 192.168.89.0/24", "") == before
    with pytest.raises(ValueError): lan.hub_config(before + "# drift\n", before)


def test_forwarding_policy_is_exact_lan_pair_not_vps_or_internet():
    policy = lan.guard_rules()
    forward = policy.split("chain forward", 1)[1]
    assert forward.count(" counter accept") == 2
    assert 'iifname "wg-s2s" oifname "wg-s2s" ip saddr 192.168.88.0/24 ip daddr 192.168.89.0/24' in forward
    assert 'ct state invalid counter drop' in forward
    assert 'iifname "wg-s2s" counter drop' in forward
    assert 'oifname "wg-s2s" counter drop' in forward
    assert "192.168." not in policy.split("chain forward", 1)[0]
    assert "0.0.0.0/0" not in policy and "masquerade" not in policy and "flush" not in policy


@pytest.mark.parametrize("site", ["nakhimova", "fethiye"])
def test_router_rules_staged_disabled_precise_and_invalid_excluded(site):
    commands = lan.router_prepare(site)
    adds = [c for c in commands if " add " in c]
    assert len(adds) == 4 and all("disabled=yes" in c for c in adds)
    assert sum("connection-state=new,established,related,untracked" in c for c in adds) == 3
    assert 'gateway=wg-s2s-tw routing-table=main' in ' '.join(adds)
    assert 'place-before=0' not in ' '.join(adds)
    assert '/ip firewall nat' not in ' '.join(commands)
    assert all('0.0.0.0/0' not in c and 'private-key' not in c and 'public-key' not in c for c in commands)
    activate = lan.router_activate()
    assert activate[-1].startswith('/ip route enable')


def test_profile_update_only_adds_remote_lan():
    before = "PrivateKey = unchanged\nAllowedIPs = 10.60.60.1/32\n"
    assert lan.profile(before, "fethiye") == "PrivateKey = unchanged\nAllowedIPs = 10.60.60.1/32, 192.168.88.0/24\n"
    with pytest.raises(ValueError): lan.profile(before + before, "fethiye")


def test_router_disabled_flag_never_inferred_from_missing_old_ros_field():
    assert lan.disabled_flag(True) is True
    assert lan.disabled_flag("true") is True
    assert lan.disabled_flag("false") is False
    for value in (None, "", "yes", 0):
        with pytest.raises(ValueError): lan.disabled_flag(value)
