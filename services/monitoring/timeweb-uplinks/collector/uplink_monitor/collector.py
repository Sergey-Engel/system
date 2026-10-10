"""Local candidate: validate one trusted batch adapter result before storage.

The production adapter is not implemented here. A 120-second interval allows
bounded sequential guard probes; the whole cycle still requires validation.
"""
import math
from dataclasses import replace

from .model import Assessment, Probe, assess, parse_helper
from .storage import UPSTREAMS
from .timing import DEFAULT_TIMING

POLICIES = {
    'gstatic': dict(family='google', host='www.gstatic.com',
                    url='https://www.gstatic.com/generate_204', expected_http=(204,)),
    'cloudflare': dict(family='cloudflare', host='www.cloudflare.com',
                       url='https://www.cloudflare.com/cdn-cgi/trace', expected_http=(200,)),
}
SOURCES = {'fornex': '10.20.0.1', 'cenuta': '10.40.40.2'}
SIGNALS = ('peer_icmp', 'handshake_age', 'dns_udp', 'dns_tcp',
           'controls_healthy', 'peer_egress_failed', 'public_ip_match')
TRANSFER_FIELDS = ('received_bytes', 'sent_bytes', 'received_delta_bytes', 'sent_delta_bytes')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def evaluate(payload, targets, generation, slot, *, timing=DEFAULT_TIMING):
    """Payload is from a fixed local adapter, never from the HTTP API.

    targets must be the locally validated, immutable cache snapshot. A helper
    marker alone cannot certify its creator; this function is not a root trust
    boundary. Both start/end and per-signal freshness are required.
    """
    unknown = lambda why: {up: (Assessment('unknown', why), []) for up in UPSTREAMS}
    try:
        started, ended = payload['started_unix'], payload['finished_unix']
        if not all(finite(t) for t in (started, ended, slot)) or not slot <= started <= ended <= slot+timing.deadline:
            return unknown('cycle_deadline')
        if payload['generation'] != generation or payload['path_verified'] is not True:
            return unknown('path_invalid')
        # TTL controls whether a target snapshot may start a batch. The helper
        # copies the already-validated snapshot and has a separate hard deadline.
        if not targets['resolved_unix'] <= started < targets['expires_unix']:
            return unknown('targets_expired')
        result = {}
        for up in UPSTREAMS:
            entry = payload['upstreams'].get(up, {})
            context = {}
            for name in SIGNALS:
                signal = entry.get('signals', {}).get(name, {})
                when, value = signal.get('observed_unix'), signal.get('value')
                if not finite(when) or not slot <= when <= ended:
                    continue
                if name == 'handshake_age':
                    if finite(value) and value >= 0:
                        context[name] = value + ended - when
                elif type(value) is bool:
                    context[name] = value
            transfer = entry.get('signals', {}).get('wg_transfer', {})
            transfer_when, transfer_value = transfer.get('observed_unix'), transfer.get('value')
            if (finite(transfer_when) and slot <= transfer_when <= ended and
                    isinstance(transfer_value, dict) and
                    all(type(transfer_value.get(field)) is int and transfer_value[field] >= 0
                        for field in TRANSFER_FIELDS) and
                    transfer_value['received_delta_bytes'] <= transfer_value['received_bytes'] and
                    transfer_value['sent_delta_bytes'] <= transfer_value['sent_bytes']):
                context['wg_transfer'] = {field: transfer_value[field] for field in TRANSFER_FIELDS}
            probes = []
            for name, policy in POLICIES.items():
                record = entry.get('probes', {}).get(name)
                target = targets['targets'][name]
                if target['host'] != policy['host'] or target['url'] != policy['url']:
                    return unknown('target_policy_changed')
                if record is None:
                    probes.append(Probe(name, policy['family'], False, None, 'missing_probe'))
                    continue
                probes.append(parse_helper(
                    record['output'], returncode=record['returncode'], generation=generation,
                    source=SOURCES[up], pinned_ip=target['ips'][0],
                    expected_http=policy['expected_http'], target=name, family=policy['family']))
            result[up] = (replace(assess(probes, path_verified=True, **context),
                                  handshake_age=context.get('handshake_age')), probes)
        # A simultaneous healthy peer is a useful control, not proof of where
        # the failing peer's return path loses packets.
        for up in UPSTREAMS:
            other = 'fornex' if up == 'cenuta' else 'cenuta'
            a, probes = result[up]
            if a.kind == 'failed' and result[other][0].kind == 'healthy':
                result[up] = (replace(a, signals=tuple(sorted(set(a.signals) | {'other_uplink_ok'}))), probes)
        return result
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return unknown('invalid_batch')


def ingest_batch(store, payload, targets, generation, slot, *, run, mono, revision, metadata=None):
    results = evaluate(payload, targets, generation, slot, timing=store.timing)
    records = {}
    for up, (assessment, probes) in results.items():
        # A failed batch must not leave old per-probe green values in the exporter.
        if assessment.kind == 'unknown':
            probes = [replace(p, valid=False, success=None) for p in probes]
        when = payload.get('finished_unix', slot)
        if not finite(when):
            when = slot
        records[up] = dict(slot=slot, run=run, generation=str(generation), assessment=assessment,
                          mono=mono, observed=when, revision=revision, probes=probes)
    store.batch(records, metadata=metadata)
    return results
