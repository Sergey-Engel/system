import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("second_leg", Path(__file__).with_name("second_leg.py"))
leg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(leg)


def baseline():
    return dict(serial="HKM0BDXYG74", trusted=True, contracts_ok=True,
                interfaces=["bridge", "wg-home", "wg1", "wg-cenuta"],
                ports=[13231, 13232, 13250], networks=["192.168.88.1/24", "10.30.30.2/24"],
                filters=[{".id": "*2B", "comment": "REALITY-B5-input", "chain": "input",
                          "action": "drop", "dynamic": False}],
                hub_peers={"B" * 43 + "=": "10.60.60.3/32"},
                hub_files_ok=True, hub_guard_ok=True)


def test_exact_reviewed_baseline_required():
    state = baseline()
    leg.validate(state, leg.fingerprint(state))
    with pytest.raises(ValueError, match="baseline"):
        leg.validate(state, "0" * 64)


@pytest.mark.parametrize("field,value", [
    ("serial", "WRONG"), ("trusted", False), ("contracts_ok", False),
    ("interfaces", ["wg-s2s-tw"]), ("ports", [51860]),
    ("networks", ["10.60.60.2/32"]), ("networks", ["10.60.0.0/16"]),
    ("hub_files_ok", False), ("hub_guard_ok", False),
    ("hub_peers", {}), ("hub_peers", {"foreign": "0.0.0.0/0"}),
    ("filters", []),
])
def test_fail_closed_before_writes(field, value):
    state = baseline()
    state[field] = value
    with pytest.raises(ValueError):
        leg.validate(state, leg.fingerprint(state))


def test_foreign_chain_and_ambiguous_anchor_rejected():
    for row in ({"chain": "s2s-pilot-input"}, baseline()["filters"][0]):
        state = baseline()
        state["filters"].append(row)
        with pytest.raises(ValueError):
            leg.validate(state, leg.fingerprint(state))


def test_hub_append_preserves_exact_original_and_refuses_drift():
    before = leg.initial_config("A" * 43 + "=", "B" * 43 + "=")
    after = leg.hub_config(before, "A" * 43 + "=", "B" * 43 + "=", "C" * 43 + "=")
    assert after.startswith(before)
    assert after.count("[Peer]") == 2
    assert after.endswith("AllowedIPs = 10.60.60.2/32\n")
    with pytest.raises(ValueError):
        leg.hub_config(before + "# foreign\n", "A" * 43 + "=", "B" * 43 + "=", "C" * 43 + "=")
    with pytest.raises(ValueError):
        leg.hub_config(before, "A" * 43 + "=", "B" * 43 + "=", "B" * 43 + "=")


def test_guard_allows_only_two_host_icmp_peers_no_transit():
    rules = leg.guard_rules()
    assert rules.count("icmp type { echo-request, echo-reply }") == 4
    assert 'ip saddr 10.60.60.2 ip daddr 10.60.60.1' in rules
    forward = rules.split("chain forward", 1)[1]
    assert "accept" not in forward.replace("policy accept", "")
    assert "flush" not in rules and "192.168." not in rules


def test_router_guards_before_enable_and_no_unrelated_mutation():
    commands = leg.router_commands("A" * 43 + "=", "B" * 43 + "=")
    assert commands[0].startswith("/interface wireguard add disabled=yes")
    assert commands[-1].startswith("/interface wireguard enable")
    assert sum("/ip firewall filter add" in c for c in commands) == 5
    assert "place-before=0" not in " ".join(commands)
    assert 'comment="REALITY-B5-input"' in " ".join(commands)
    assert all("remove" not in c and " set " not in c for c in commands)
    assert "0.0.0.0/0" not in " ".join(commands)
    assert "192.168." not in " ".join(commands)


def test_allowed_file_delta_is_exact_and_old_metadata_preserved():
    before = {"config": "old", "guard": "old", "manifest": "old", "unit": "same"}
    assert leg.changed_paths(before, {**before, "config": "new"}, {"config"}) == {"config"}
    with pytest.raises(ValueError):
        leg.changed_paths(before, {**before, "unit": "changed"}, {"config"})
