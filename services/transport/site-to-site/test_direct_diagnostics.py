import base64
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("direct_diagnostics", Path(__file__).with_name("direct_diagnostics.py"))
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


@pytest.mark.parametrize("site", d.SITES)
def test_observers_are_passive_and_match_only_new_port(site):
    commands = d.stage_commands(site, "5.18.143.112")
    assert len(commands) == 9
    assert "action=passthrough" in commands[-1] and "action=passthrough" in commands[-2]
    assert "limit=10/1s,20:packet" in commands[-1]
    assert f"dst-port={d.SITES[site][2]}" in commands[-2]
    assert f"src-port={d.SITES[site][2]}" in commands[-1]
    text = "\n".join(commands)
    assert "wg-s2s-tw" not in text and "wg-forward-trial" not in text
    assert "/ip route" not in text and "/ip firewall nat" not in text
    assert all(d.OWNER in c for c in commands)


def test_existing_raw_policy_requires_review():
    with pytest.raises(ValueError, match="raw_chain"):
        d.assert_free({"/ip firewall raw": [{"action": "drop"}]})


def test_new_namespace_cannot_be_reused():
    with pytest.raises(ValueError):
        d.assert_free({"/interface wireguard": [{"name": d.IFACE}]})


def test_exact_cleanup_and_peer_scope():
    assert len(d.cleanup_commands()) == 10
    assert all(d.OWNER in c and "find where" in c for c in d.cleanup_commands())
    key = base64.b64encode(bytes(range(32))).decode()
    assert f'interface="{d.IFACE}"' in d.peer_command("nakhimova", key, "194.61.140.217")
    assert "endpoint-address" not in d.peer_command("fethiye", key, "194.61.140.217")
