import copy
from uplink_monitor.collector import POLICIES, SOURCES, evaluate, ingest_batch
from uplink_monitor.storage import Store, current
from uplink_monitor.timing import LEGACY_TIMING


def sample(slot=100):
    targets = dict(resolved_unix=90, expires_unix=200, targets={
        k: dict(host=v['host'], url=v['url'], ips=['1.1.1.1']) for k, v in POLICIES.items()})
    payload = dict(started_unix=slot, finished_unix=slot+1, generation=5, path_verified=True, upstreams={})
    for up, source in SOURCES.items():
        payload['upstreams'][up] = dict(probes={k: dict(returncode=0, output=
            f'http={v["expected_http"][0]} local={source} remote=1.1.1.1 seconds=0.2\n'
            'VALID_OBSERVATION curl_exit=0 generation=5') for k, v in POLICIES.items()})
    return payload, targets


def test_valid_batch_to_store(tmp_path):
    store = Store(tmp_path/'db', timing=LEGACY_TIMING)
    for slot in (100, 110):
        payload, targets = sample(slot)
        ingest_batch(store, payload, targets, 5, slot, run='test', mono=slot, revision='v1')
    assert all(v['state']=='UP' for v in current(store.path, 111).values())


def test_deadline_expiry_and_changed_generation_are_unknown():
    payload, targets = sample()
    targets['expires_unix'] = 100
    assert evaluate(payload, targets, 5, 100)['cenuta'][0].reason=='targets_expired'
    payload, targets = sample()
    payload['generation'] = 6
    assert evaluate(payload, targets, 5, 100)['cenuta'][0].reason=='path_invalid'
    payload['finished_unix'] = 146
    assert evaluate(payload, targets, 5, 100)['cenuta'][0].reason=='cycle_deadline'


def test_batch_started_before_ttl_may_finish_after_ttl():
    payload, targets = sample()
    targets['expires_unix'] = 101
    payload['finished_unix'] = 106
    assert evaluate(payload, targets, 5, 100)['cenuta'][0].kind == 'healthy'


def test_stale_and_missing_diagnostics_are_not_failures():
    payload, targets = sample()
    payload['upstreams']['cenuta']['signals'] = {
        'dns_udp': dict(value=False, observed_unix=50),
        'peer_icmp': dict(value=True, observed_unix=102),
        'handshake_age': dict(value=-5, observed_unix=100),
    }
    a, _ = evaluate(payload, targets, 5, 100)['cenuta']
    assert a.kind=='healthy' and not a.signals and a.transport_alive is None
    payload['upstreams']['cenuta']['signals']['dns_udp']['observed_unix'] = 100
    assert evaluate(payload, targets, 5, 100)['cenuta'][0].kind=='partial'


def test_fresh_wg_transfer_is_preserved_and_malformed_transfer_is_ignored():
    payload, targets = sample()
    payload['upstreams']['cenuta']['signals'] = {
        'wg_transfer': dict(observed_unix=101, value=dict(
            received_bytes=400, sent_bytes=300,
            received_delta_bytes=200, sent_delta_bytes=100)),
    }
    assessment, _ = evaluate(payload, targets, 5, 100)['cenuta']
    assert assessment.wg_transfer['received_delta_bytes'] == 200
    payload['upstreams']['cenuta']['signals']['wg_transfer']['value']['sent_delta_bytes'] = -1
    assessment, _ = evaluate(payload, targets, 5, 100)['cenuta']
    assert assessment.wg_transfer is None


def test_malformed_missing_and_mixed_results():
    payload, targets = sample()
    del payload['upstreams']['cenuta']
    result = evaluate(payload, targets, 5, 100)
    assert result['cenuta'][0].kind=='unknown' and result['fornex'][0].kind=='healthy'
    payload, targets = sample()
    targets['targets']['gstatic']['url'] = 'https://evil.example/'
    assert evaluate(payload, targets, 5, 100)['cenuta'][0].reason=='target_policy_changed'
    assert evaluate({}, {}, 5, 100)['fornex'][0].reason=='invalid_batch'
