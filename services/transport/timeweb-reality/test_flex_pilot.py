import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("flex_pilot", Path(__file__).with_name("flex_pilot.py"))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_iphone_is_isolated_from_macbook():
    assert pilot.PEER == "10.50.50.39"
    assert pilot.TABLE == "410"
    pilot.select_device("iphone12")
    assert pilot.PEER == "10.50.50.40"
    assert pilot.TABLE == "412"
    assert pilot.MARK == "0x40"
    assert pilot.SRC_PRIORITY == 241
    assert pilot.FIREWALL_TABLE == "flex_iphone12"
    assert '10.50.50.40' in pilot.guard_rules()
    assert '10.50.50.39' not in pilot.guard_rules()


def test_macmini_uses_separate_peer_and_policy():
    pilot.select_device("macmini")
    assert pilot.PEER == "10.50.50.41"
    assert pilot.TABLE == "414"
    assert pilot.MARK == "0x41"
    assert pilot.SRC_PRIORITY == 243
    assert pilot.MARK_PRIORITY == 184
    assert pilot.FIREWALL_TABLE == "flex_macmini"
    assert '10.50.50.41' in pilot.guard_rules()
    assert '10.50.50.40' not in pilot.guard_rules()


def test_quarantines_are_removed_only_after_verification():
    checks = iter([0, 0, 1, 1])
    events = []

    def net(*args, **kwargs):
        if args[:2] == ('iptables', '-C'):
            events.append('check')
            return SimpleNamespace(returncode=next(checks))
        if args[:2] == ('iptables', '-D'):
            events.append('delete')
        return SimpleNamespace(returncode=0, stdout='')

    def verify(value, allow_quarantine=False):
        assert allow_quarantine
        events.append('verified')
        return {'observed': 'ready'}

    with patch.object(pilot, 'peer_present', return_value=True), \
         patch.object(pilot, 'net', side_effect=net), \
         patch.object(pilot, 'ensure_guard'), patch.object(pilot, 'check_guard'), \
         patch.object(pilot, 'ensure_rule'), \
         patch.object(pilot, 'ru_rule_handles', return_value=[]), \
         patch.object(pilot, 'verify', side_effect=verify):
        assert pilot.apply({'exit': 'cen', 'ru_direct': False}) == {'observed': 'ready'}
    assert events == ['verified', 'check', 'delete', 'check', 'delete', 'check', 'check']
