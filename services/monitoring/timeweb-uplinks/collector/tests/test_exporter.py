import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen
import pytest
from uplink_monitor.exporter import make_server, metrics
from uplink_monitor.storage import Store, current
from uplink_monitor.collector import ingest_batch
from test_collector import sample
from uplink_monitor.timing import LEGACY_TIMING


def test_metrics_freshness_does_not_repeat_stale_success(tmp_path):
    store=Store(tmp_path/'db', timing=LEGACY_TIMING)
    payload, targets=sample()
    ingest_batch(store,payload,targets,5,100,run='t',mono=100,revision='v1')
    text=metrics(current(store.path,101))
    assert 'vpn_uplink_probe_success{upstream="cenuta",check="https",target="gstatic"} 1' in text
    text=metrics(current(store.path,127))
    assert 'vpn_uplink_state{upstream="cenuta"} 0' in text
    assert not any(l.startswith('vpn_uplink_probe_success{') for l in text.splitlines())
    assert text.endswith('\n')


def test_transport_mode_is_exported_only_from_valid_controller_state(tmp_path):
    snapshot = {up: dict(state='UNKNOWN', reason='no_data', fresh=False,
                         observed=0, outages=0) for up in ('cenuta', 'fornex')}
    state = tmp_path/'transport-state.json'
    state.write_text(json.dumps(dict(upstreams=dict(
        fornex=dict(mode='native'), cenuta=dict(mode='custom'), unknown=dict(mode='backup')))))
    text = metrics(snapshot, transport_state_path=state)
    assert 'vpn_uplink_selected_transport_info{upstream="fornex",mode="native"} 1' in text
    assert 'upstream="cenuta"' not in '\n'.join(
        line for line in text.splitlines() if line.startswith('vpn_uplink_selected_transport_info{'))
    state.write_text('{invalid')
    assert 'vpn_uplink_selected_transport_info{' not in metrics(snapshot, transport_state_path=state)


def test_wg_transfer_metrics_are_exported_only_for_fresh_measurements():
    snapshot = {up: dict(state='UNKNOWN', reason='no_data', fresh=False,
                         observed=0, outages=0) for up in ('cenuta', 'fornex')}
    snapshot['fornex'].update(fresh=True, assessment=dict(wg_transfer=dict(
        received_bytes=1000, sent_bytes=2000,
        received_delta_bytes=300, sent_delta_bytes=400), one_way_suspect=False))
    text = metrics(snapshot)
    assert 'vpn_uplink_wg_peer_transfer_delta_bytes{upstream="fornex",direction="sent"} 400' in text
    assert 'vpn_uplink_wg_one_way_suspect{upstream="fornex"} 0' in text
    assert 'upstream="cenuta",direction="sent"' not in text


def test_http_readonly_api_bounds_and_health(tmp_path):
    store=Store(tmp_path/'db')
    with make_server(store.path, clock=lambda:100) as server:
        thread=threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            assert server.server_address[0]=='127.0.0.1'
            with urlopen(base+'/healthz', timeout=2) as r:
                assert json.load(r)['network_health']=='not_checked'
            with urlopen(base+'/api/summary?from=0&to=10000', timeout=2) as r:
                assert json.load(r)[0]['availability'] is None
            for query in ('/api/summary?from=0&to=999999999999',
                          '/api/incidents?from=0&to=10000&upstream=arbitrary',
                          '/api/summary?from=nan&to=10000', '/api/summary?from=0&from=1&to=1000'):
                with pytest.raises(HTTPError) as e: urlopen(base+query,timeout=2)
                assert e.value.code==400
        finally:
            server.shutdown()
            thread.join(timeout=2)


def test_storage_health_blocks_stale_green_metrics(tmp_path):
    store = Store(tmp_path/'db')
    health = tmp_path/'health.json'
    health.write_text(json.dumps(dict(updated=100,storage_ok=False)))
    with make_server(store.path, clock=lambda:100, health_path=health) as server:
        thread=threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            for path in ('/metrics','/readyz','/api/current'):
                with pytest.raises(HTTPError) as exc: urlopen(base+path,timeout=2)
                assert exc.value.code==503
            assert urlopen(base+'/healthz',timeout=2).status==200
        finally:
            server.shutdown()
            thread.join(2)
