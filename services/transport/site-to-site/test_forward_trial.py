import base64
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("forward_trial", Path(__file__).with_name("forward_trial.py"))
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)

KEY = base64.b64encode(bytes(range(32))).decode()


def test_forward_is_only_initiated_from_nakhimova():
    n = trial.peer_command("nakhimova", KEY, "194.61.140.217")
    f = trial.peer_command("fethiye", KEY, "194.61.140.217")
    assert "endpoint-address=194.61.140.217 endpoint-port=51972" in n
    assert "persistent-keepalive=25s" in n
    assert "endpoint-address" not in f and "endpoint-port" not in f
    assert "allowed-address=10.60.62.2/32" in n
    assert "allowed-address=10.60.62.1/32" in f


@pytest.mark.parametrize("site", trial.SITES)
def test_stage_is_isolated_and_does_not_touch_existing_transport(site):
    commands = trial.stage_commands(site, "5.18.141.112")
    assert len(commands) == 7
    assert "disabled=yes" in commands[0]
    assert sum("chain=forward action=drop" in c for c in commands) == 2
    assert "src-address=5.18.141.112/32" in commands[-1]
    assert all("place-before=([find where dynamic=no]->0)" in c for c in commands[2:])
    assert not any(x in "\n".join(commands) for x in ("wg-s2s-tw", "/ip route", "/ip firewall nat", "/system scheduler"))


@pytest.mark.parametrize("snapshot", [
    {"/interface wireguard": [{"listen-port": "51972"}]},
    {"/ip firewall nat": [{"to-ports": "51972"}]},
    {"/ip route": [{"dst-address": "10.60.0.0/16"}]},
    {"/interface wireguard peers": [{"allowed-address": ["10.60.62.1/32"]}]},
    {"/ip address": [{"address": "10.60.62.2/30"}]},
    {"/interface wireguard": [{"name": trial.IFACE}]},
])
def test_collisions_fail_closed(snapshot):
    with pytest.raises(ValueError):
        trial.assert_free(snapshot)


def test_unrelated_defaults_are_not_a_collision():
    trial.assert_free({"/ip route": [{"dst-address": "0.0.0.0/0"}, {"dst-address": "192.168.88.0/24"}]})


def test_cleanup_is_exact_and_has_no_global_flush():
    assert len(trial.cleanup_commands()) == 8
    assert all(trial.OWNER in c for c in trial.cleanup_commands())
    assert not any("wg-s2s-tw" in c or "remove [find]" in c for c in trial.cleanup_commands())


def test_probe_is_bound_to_new_interface_and_only_two_packet_sizes():
    assert "interface=wg-forward-trial" in trial.ping_command("nakhimova", 1380)
    with pytest.raises(ValueError):
        trial.ping_command("fethiye", 1500)


def test_non_public_endpoint_rejected():
    with pytest.raises(ValueError):
        trial.peer_command("nakhimova", KEY, "192.168.68.117")
