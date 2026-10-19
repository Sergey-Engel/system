"""Safety controls for an isolated direct-connectivity experiment."""
import base64
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location("direct_trial", Path(__file__).with_name("direct_trial.py"))
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def test_namespace_and_network_refuse_collisions():
    for path, row in [("/interface wireguard", {"name": d.IFACE}),
                      ("/system scheduler", {"name": d.OWNER}),
                      ("/ip address", {"address": "10.60.62.1/30"}),
                      ("/ip route", {"dst-address": "10.60.62.0/24"}),
                      ("/interface wireguard peers", {"allowed-address": ["10.60.62.2/32"]}),
                      ("/interface wireguard", {"listen-port": "51971"})]:
        with pytest.raises(ValueError): d.assert_free({path: [row]})
    d.assert_free({"/ip route": [{"dst-address": "0.0.0.0/0"}, {"dst-address": "10.60.60.0/29"}]})


@pytest.mark.parametrize("site", d.SITES)
def test_stage_is_disabled_no_lan_routes_or_nat(site):
    commands = d.stage_commands(site, "5.18.141.112")
    assert commands[0].startswith("/interface wireguard add disabled=yes")
    assert len(commands) == 7
    assert all("/ip route" not in c and "/ip firewall nat" not in c and "0.0.0.0/0" not in c for c in commands)
    assert sum("action=drop" in c for c in commands) == 3
    assert "protocol=icmp" in commands[-2]
    assert "src-address=5.18.141.112/32" in commands[-1]
    assert "dst-port=" + str(d.SITES[site][2]) in commands[-1]
    assert all("public-key" not in c and "private-key" not in c for c in commands)
    assert all('find where dynamic=no' in c for c in commands if '/ip firewall filter add' in c)


def test_guard_is_bounded_and_cleanup_only_exact_owned_objects():
    command = d.guard_command("2026-10-17", "23:59:30")
    assert "start-date=2026-10-18 start-time=00:11:30" in command
    assert "interval=0s" in command
    for c in d.cleanup_commands():
        assert d.OWNER in c and "find where" in c and "~" not in c
        assert "reset" not in c and "flush" not in c and "reboot" not in c
    with pytest.raises(ValueError): d.guard_command("2026-10-17", "23:59:30", 9999)


def test_peer_has_single_test_host_only():
    command = d.peer_command("fethiye", base64.b64encode(bytes(range(32))).decode(), "5.18.141.112", 51971)
    assert "allowed-address=10.60.62.1/32" in command
    assert "0.0.0.0" not in command and "192.168" not in command
    with pytest.raises(ValueError): d.peer_command("fethiye", "bad", "5.18.141.112", 51971)
    with pytest.raises(ValueError): d.stage_commands("fethiye", '5.18.141.112;reboot')
    with pytest.raises(ValueError): d.stage_commands("fethiye", '10.0.0.1')


def test_capture_requires_new_unique_handshake_endpoint():
    text = "IP 5.18.141.112.10000 > 94.241.171.65.51860: UDP, length 148\n"
    text += "IP 5.18.141.112.20000 > 94.241.171.65.51860: UDP, length 148\n"
    assert d.captured_endpoints(text, "5.18.141.112", [("5.18.141.112", 10000)]) == ("5.18.141.112", 20000)
    with pytest.raises(ValueError): d.captured_endpoints(text, "5.18.141.112", [])
    with pytest.raises(ValueError): d.captured_endpoints("", "5.18.141.112", [])


def test_safe_mode_requires_positive_ack_across_ros_versions():
    assert d.safe_mode_confirmed(b'[Safe Mode taken]\r\n[admin@MikroTik] <SAFE>')
    assert d.safe_mode_confirmed(b'Taking Safe Mode session... Success!\r\n[codex@hAP] <SAFE>')
    assert not d.safe_mode_confirmed(b'Taking Safe Mode session... Success!\r\n')
    assert not d.safe_mode_confirmed(b'Taking Safe Mode session...')
    assert not d.safe_mode_confirmed(b'[admin@MikroTik] >')
    assert not d.safe_mode_confirmed(b'Hijacking Safe Mode from someone <SAFE>')


def test_ping_is_path_pinned_and_uses_boolean_flag_syntax():
    command = d.ping_command('fethiye', 1380)
    assert 'address=10.60.62.1 src-address=10.60.62.2 interface=wg-direct-trial' in command
    assert command.endswith('size=1380 do-not-fragment')
    with pytest.raises(ValueError): d.ping_command('fethiye', 1500)


def test_shared_socket_candidate_does_not_modify_existing_interface_or_peer():
    commands = d.shared_stage_commands('nakhimova', '194.61.140.217', 51862)
    peer = d.shared_peer_command('nakhimova', base64.b64encode(bytes(range(32))).decode(), '194.61.140.217', 51861)
    assert 'add disabled=yes interface="wg-s2s-tw"' in peer
    assert 'allowed-address=10.60.62.2/32' in peer
    assert 'interface=wg-s2s-tw' in d.ping_command('nakhimova', shared=True)
    assert all(' set ' not in c and '/interface wireguard' not in c and '/ip route' not in c for c in commands)
    assert sum('chain=forward action=drop' in c and '10.60.62.0/30' in c for c in commands) == 2
    assert all('10.60.62.0/30' in c for c in commands if 'action=drop' in c)
    assert all('find where dynamic=no' in c for c in commands if '/ip firewall filter add' in c)
