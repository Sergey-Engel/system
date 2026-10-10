from dataclasses import replace

import pytest

from uplink_monitor.model import Probe, assess as classify, parse_helper


def assess(probes, **context):
    context.setdefault('path_verified', True)
    return classify(probes, **context)


def result(exit_code=0, http=204, generation=5, text='', local='10.40.40.2'):
    return f'{text}\nhttp={http:03d} local={local} remote=1.1.1.1 seconds=0.2\nVALID_OBSERVATION curl_exit={exit_code} generation={generation}\n'


def parse(text=None, **kwargs):
    return parse_helper(text or result(), returncode=0, generation=5,
                        source='10.40.40.2', pinned_ip='1.1.1.1',
                        expected_http=(204,), target='a', family='google', **kwargs)


def test_exit_zero_does_not_mean_up():
    p = parse(result(28, 0, text='curl: (28) Failed to connect to host port 443: Timeout was reached', local=''))
    assert p.valid and not p.success and p.phase == 'tcp_connect'


def test_incomplete_http_success_is_invalid():
    assert not parse(result(http=0)).valid


@pytest.mark.parametrize('text,reason', [
    ('REFUSED targets_expired', 'targets_expired'),
    ('UNKNOWN reason=generation_or_manifest_changed result_discarded', 'generation_or_manifest_changed'),
    (result(generation=6), 'generation_mismatch'),
    (result(local='10.20.0.1'), 'path_mismatch'),
    ('', 'helper_failed'),
])
def test_invalid_is_not_remote_down(text, reason):
    p = parse_helper(text, returncode=2 if not text.startswith('\nhttp') else 0,
                     generation=5, source='10.40.40.2', pinned_ip='1.1.1.1',
                     expected_http=(204,), target='a', family='google')
    assert not p.valid and p.reason == reason


@pytest.mark.parametrize('http', [301, 403, 429, 500])
def test_http_response_is_not_automatically_healthy(http):
    p = parse(result(http=http))
    assert p.valid and not p.success and p.phase == 'http'
    assert p.tcp_success is True


def healthy_pair():
    return [parse(), replace(parse(), target='b', family='cloudflare')]


def test_cenuta_protocol_specific_failure():
    probes = [replace(p, success=False, phase='tcp_connect', reason='timeout',
                      tcp_success=False, tls_success=None) for p in healthy_pair()]
    a = assess(probes, peer_icmp=True, handshake_age=15, dns_udp=True,
               controls_healthy=True, peer_egress_failed=True)
    assert a.kind == 'failed' and a.reason == 'tcp_connect_failed'
    assert a.scope == 'peer_host_egress_or_external_path'
    assert a.transport_alive and 'dns_udp_ok' in a.signals
    assert 'rkn' not in str(a).lower()


def test_no_peer_egress_evidence_no_precise_localization():
    p = [replace(p, success=False, phase='tcp_connect') for p in healthy_pair()]
    assert assess(p, peer_icmp=True).scope == 'beyond_peer_or_protocol_specific'
    assert assess(p).scope == 'undetermined'


def test_partial_invalid_and_shared_targets():
    ok, second = healthy_pair()
    bad = replace(second, success=False)
    invalid = replace(second, valid=False, success=None)
    assert assess([ok, bad]).kind == 'partial'
    assert assess([ok, invalid]).kind == 'partial'
    assert assess([replace(ok, success=False), invalid]).kind == 'unknown'
    assert assess([ok, replace(second, family='google')]).kind == 'unknown'


def test_ping_dns_handshake_are_not_internet_status():
    assert assess(healthy_pair(), peer_icmp=False).kind == 'partial'
    assert assess(healthy_pair(), dns_udp=False).reason == 'dns_udp_failed'
    assert assess(healthy_pair(), handshake_age=181).kind == 'partial'
    failed = [replace(p, success=False) for p in healthy_pair()]
    assert assess(failed, peer_icmp=False, handshake_age=200).reason == 'tunnel_unreachable'


def test_one_way_transfer_is_only_corroborating_evidence():
    transfer = dict(received_bytes=500, sent_bytes=1000,
                    received_delta_bytes=0, sent_delta_bytes=256)
    healthy = assess(healthy_pair(), wg_transfer=transfer)
    assert healthy.kind == 'healthy' and healthy.one_way_suspect is True
    failed = [replace(p, success=False) for p in healthy_pair()]
    suspect = assess(failed, handshake_age=200, wg_transfer=transfer)
    assert suspect.reason == 'tunnel_one_way_suspect'


def test_local_service_vs_read_error():
    assert assess([], service_present=False).reason == 'local_service_down'
    assert assess([], read_error=True).kind == 'unknown'
    assert assess(healthy_pair(), path_verified=False).kind == 'unknown'


def test_tls_failure_distinct_from_connect_timeout_and_partial_body():
    p=parse(result(60,0))
    assert p.valid and not p.success and p.phase=='tls' and p.tcp_success
    assert p.tls_success is False
    p=parse(result(28,200,text='curl: (28) Operation timed out after 5000 milliseconds'))
    assert p.phase=='http_body' and p.tcp_success and p.tls_success and not p.success
    assert parse(result(28,0)).phase=='unknown_phase'
