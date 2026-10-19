"""Read-only soak observations and strict acceptance, not a router writer."""
import importlib.util
from pathlib import Path
import re

_SPEC = importlib.util.spec_from_file_location('sstp_soak_transport', Path(__file__).with_name('sstp_trial.py'))
transport = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(transport)

OWNER = 's2s-sstp-soak-20261019'
CLIENT, SERVER = 'sstp-soak-out', 'sstp-soak-in'
DURATION_SECONDS = 1800
PERIOD_SECONDS = 30
SAMPLE_COUNT = DURATION_SECONDS // PERIOD_SECONDS + 1
GUARD_SECONDS = 2700


def safe_prompt_active(transcript):
    prompts = re.findall(rb'\[[^@\r\n]+@[^\]\r\n]+\] (<SAFE>|>)', transcript)
    return bool(prompts) and prompts[-1] == b'<SAFE>'


def seconds(value):
    text = str(value)
    clock = re.fullmatch(r'(?:(\d+)w)?(?:(\d+)d)?(\d+):([0-5]\d):([0-5]\d)(?:\.(\d+))?', text)
    if clock:
        weeks, days, hours, minutes, secs, fraction = clock.groups()
        return (int(weeks or 0) * 604800 + int(days or 0) * 86400 + int(hours) * 3600
                + int(minutes) * 60 + int(secs) + float('0.' + (fraction or '0')))
    parts = re.findall(r'(\d+(?:\.\d+)?)(us|ms|w|d|h|m|s)', text)
    if not parts or ''.join(number + unit for number, unit in parts) != text:
        raise ValueError('invalid_router_duration')
    scale = dict(w=604800, d=86400, h=3600, m=60, s=1, ms=0.001, us=0.000001)
    return sum(float(number) * scale[unit] for number, unit in parts)


def probe_command(site, size=56):
    if site not in transport.SITES or size not in (56, 1400) or type(size) is not int:
        raise ValueError('unapproved_soak_probe')
    remote = 'fethiye' if site == 'nakhimova' else 'nakhimova'
    iface = CLIENT if site == 'nakhimova' else SERVER
    return (f'/ping address={transport.SITES[remote][1]} src-address={transport.SITES[site][1]} '
            f'interface={iface} count=5 interval=1s size={size} do-not-fragment')


def ping_result(output):
    text = output.decode()
    counts = re.findall(r'sent=(\d+)\s+received=(\d+)', text)
    if len(counts) != 1:
        raise ValueError('missing_or_ambiguous_ping_summary')
    sent, received = map(int, counts[0])
    if sent != 5 or not 0 <= received <= sent:
        raise ValueError('unexpected_ping_counts')
    result = dict(sent=sent, received=received)
    for metric, duration in re.findall(r'(min-rtt|avg-rtt|max-rtt)=([^\s]+)', text):
        result[metric] = seconds(duration)
    return result


def sample_issues(sample, previous=None, initial_http=None):
    issues = []
    if sample['running'] is not True:
        issues.append('sstp_not_running')
    if sample.get('encoding') != 'AES256-GCM' or sample.get('negotiated_mtu') != 1400:
        issues.append('transport_parameters_differ')
    if not sample.get('session_id'):
        issues.append('authenticated_session_missing')
    if previous and sample['running'] is True and previous['running'] is True:
        expected = previous['uptime_seconds'] + sample['elapsed_seconds'] - previous['elapsed_seconds']
        if sample['uptime_seconds'] < expected - 3 or sample.get('session_id') != previous.get('session_id'):
            issues.append('unexpected_reconnect')
    for kind in ('icmp', 'df1400'):
        values = sample.get(kind)
        if kind == 'df1400' and values is None:
            continue
        if not values or set(values) != set(transport.SITES) or any(v['received'] != v['sent'] for v in values.values()):
            issues.append(kind + '_timeout')
    http = sample['http']
    if http['status'] != 'up' or http['http-status-code'] != 200:
        issues.append('http_not_ok')
    if initial_http and http['failed-tests'] != initial_http['failed-tests']:
        issues.append('http_failure_observed')
    if previous and http['done-tests'] <= previous['http']['done-tests']:
        issues.append('http_observation_stalled')
    return issues


def qualify(samples, elapsed, initial_http, final_http, disconnect_events):
    issues = []
    if elapsed < DURATION_SECONDS or len(samples) < SAMPLE_COUNT:
        issues.append('incomplete_soak_window')
    if sum(s.get('df1400') is not None for s in samples) < 7:
        issues.append('incomplete_mtu_coverage')
    if any(s['issues'] for s in samples):
        issues.append('sample_failures')
    if disconnect_events:
        issues.append('unexpected_disconnect_log')
    if final_http['failed-tests'] != initial_http['failed-tests']:
        issues.append('http_failure_observed')
    if final_http['done-tests'] - initial_http['done-tests'] < 300:
        issues.append('insufficient_http_observations')
    if final_http['status'] != 'up' or final_http['http-status-code'] != 200:
        issues.append('final_http_not_ok')
    return dict(passed=not issues, issues=issues)
