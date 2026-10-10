import pytest
from uplink_monitor.exporter import metrics
from uplink_monitor.daemon import main


def test_pilot_scope_and_unknown_are_explicit():
    snapshot = {up: dict(state='UNKNOWN', reason='no_data', fresh=False,
                observed=0, outages=0) for up in ('cenuta', 'fornex')}
    text = metrics(snapshot, pilot=True)
    assert 'mode="pilot"' in text
    assert 'scope="rtnl_and_snapshots"' in text
    assert 'vpn_uplink_state{upstream="cenuta"} 0' in text
    assert 'reason="no_data"' in text
    assert 'vpn_uplink_handshake_age_seconds{upstream=' not in text
    assert 'vpn_uplink_pilot_info' not in metrics(snapshot)


def test_production_cannot_be_enabled_by_snapshot_flag_alone(monkeypatch):
    import uplink_monitor.daemon as module
    monkeypatch.setattr('sys.argv', ['daemon', '--config', '/test', '--state-dir', '/state'])
    monkeypatch.setattr(module, 'private_file', lambda path: path)
    monkeypatch.setattr(module, 'read_json', lambda _:dict(version=1,allow_snapshot_scope=True))
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
