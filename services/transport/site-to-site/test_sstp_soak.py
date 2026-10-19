from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('sstp_soak_tests', Path(__file__).with_name('sstp_soak.py'))
soak = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(soak)


def sample(elapsed=0):
    ping = {s: dict(sent=5, received=5) for s in ('nakhimova', 'fethiye')}
    return dict(running=True, encoding='AES256-GCM', negotiated_mtu=1400,
                session_id='*1', uptime_seconds=elapsed + 10, elapsed_seconds=elapsed,
                icmp=ping, df1400=None, issues=[],
                http=dict(status='up', **{'http-status-code': 200, 'done-tests': int(elapsed / 5) + 1, 'failed-tests': 0}))


def test_latest_safe_prompt_required_not_historical_ack():
    safe = b'Taking Safe Mode session... Success!\r\n[user@router] <SAFE> \x1b[c'
    assert soak.safe_prompt_active(safe)
    assert not soak.safe_prompt_active(safe + b'\r\n[user@router] > ')
    assert not soak.safe_prompt_active(b'Safe Mode taken')


@pytest.mark.parametrize('value, expected', [('00:30:00', 1800), ('01:02:03.5', 3723.5),
                                           ('1d01:00:00', 90000), ('232ms784us', .232784), ('2m3s', 123)])
def test_router_durations(value, expected):
    assert soak.seconds(value) == pytest.approx(expected)


@pytest.mark.parametrize('value', ['', '1970-01-01 00:00:04', '00:70:00', '1ms garbage'])
def test_unknown_duration_refused(value):
    with pytest.raises(ValueError):
        soak.seconds(value)


def test_ping_uses_ordinary_interval_and_exact_source_interface():
    for site in ('nakhimova', 'fethiye'):
        for size in (56, 1400):
            text = soak.probe_command(site, size)
            assert 'interval=1s' in text and f'size={size}' in text
            assert 'src-address=10.60.64.' in text and 'interface=sstp-soak-' in text
            assert text.endswith('do-not-fragment')
    with pytest.raises(ValueError):
        soak.probe_command('nakhimova', 1500)


def test_ping_counts_and_wrapped_rtt_parsed_without_hiding_loss():
    result = soak.ping_result(b'sent=5 received=4 packet-loss=20% min-rtt=113ms\r\n max-rtt=1s2ms')
    assert result == dict(sent=5, received=4, **{'min-rtt': .113, 'max-rtt': 1.002})
    for raw in (b'bad parameter', b'sent=1 received=1', b'sent=5 received=6'):
        with pytest.raises(ValueError):
            soak.ping_result(raw)


def test_normal_observation_and_reconnect_detection():
    initial, current = sample(), sample(30)
    assert soak.sample_issues(current, initial, initial['http']) == []
    current['uptime_seconds'] = 12
    assert 'unexpected_reconnect' in soak.sample_issues(current, initial, initial['http'])
    current = sample(30)
    current['session_id'] = '*2'
    assert 'unexpected_reconnect' in soak.sample_issues(current, initial, initial['http'])


def test_http_failures_and_stalled_counter_are_not_a_healthy_scrape():
    initial, current = sample(), sample(30)
    current['http']['failed-tests'] = 1
    assert 'http_failure_observed' in soak.sample_issues(current, initial, initial['http'])
    current['http'] = deepcopy(initial['http'])
    assert 'http_observation_stalled' in soak.sample_issues(current, initial, initial['http'])
    current['icmp']['fethiye']['received'] = 4
    assert 'icmp_timeout' in soak.sample_issues(current, initial, initial['http'])


def test_complete_window_required_and_prior_failures_cannot_be_erased():
    samples = [sample(i * 30) for i in range(soak.SAMPLE_COUNT)]
    for index, item in enumerate(samples):
        if index % 10 == 0:
            item['df1400'] = deepcopy(item['icmp'])
    args = (samples, 1800, samples[0]['http'], samples[-1]['http'], [])
    assert soak.qualify(*args)['passed']
    assert not soak.qualify(samples, 1799, *args[2:])['passed']
    samples[2]['issues'] = ['icmp_timeout']
    assert not soak.qualify(*args)['passed']
    samples[2]['issues'] = []
    assert not soak.qualify(samples, 1800, *args[2:4], ['disconnected'])['passed']
