"""Separate measurement validity, protocol failure, and bounded attribution."""
from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class Probe:
    target: str
    family: str
    valid: bool
    success: bool | None
    reason: str
    phase: str = 'unmeasured'
    tcp_success: bool | None = None
    tls_success: bool | None = None
    http: int = 0
    seconds: float = 0
    generation: int | None = None


def parse_helper(text, *, returncode, generation, source, pinned_ip,
                 expected_http, target, family):
    def invalid(reason):
        return Probe(target, family, False, None, reason)

    if len(text) > 65536:
        return invalid('output_limit')
    for prefix in ('REFUSED ', 'UNKNOWN reason='):
        line = next((x for x in text.splitlines() if x.startswith(prefix)), None)
        if line:
            # Keep codes bounded; never export raw curl errors or response bodies.
            reason = line[len(prefix):].split()[0]
            return invalid(reason if re.fullmatch(r'[a-z_]{1,64}', reason) else 'helper_refused')
    if returncode != 0:
        return invalid('helper_failed')
    markers = re.findall(r'^VALID_OBSERVATION curl_exit=(\d+) generation=(\d+)$', text, re.M)
    rows = [x for x in text.splitlines() if x.startswith('http=')]
    if len(markers) != 1 or len(rows) != 1:
        return invalid('helper_failed')
    rc, observed_generation = map(int, markers[0])
    if observed_generation != generation:
        return invalid('generation_mismatch')
    fields = dict(re.findall(r'(\w+)=([^\s]*)', rows[0]))
    try:
        http, seconds = int(fields['http']), float(fields['seconds'])
        if not math.isfinite(seconds) or seconds < 0 or not 0 <= http <= 599:
            raise ValueError()
    except (KeyError, ValueError):
        return invalid('malformed_result')
    if fields.get('local') not in ('', source) or fields.get('remote') not in ('', pinned_ip):
        return invalid('path_mismatch')
    if rc == 0 and (fields.get('local') != source or fields.get('remote') != pinned_ip):
        return invalid('path_mismatch')
    if rc == 0 and http < 100:
        return invalid('malformed_result')
    args = dict(target=target, family=family, valid=True, http=http,
                seconds=seconds, generation=observed_generation)
    if rc == 0:
        return Probe(**args, success=http in expected_http,
                     reason='ok' if http in expected_http else 'http_unexpected',
                     phase='http', tcp_success=True, tls_success=True)
    if rc not in (7, 16, 18, 28, 35, 52, 55, 56, 60, 92):
        return invalid('probe_execution_error')
    # Older helper output lacks connect/TLS timers. Only localize explicit evidence.
    phase = 'unknown_phase'
    tcp = tls = None
    if rc == 7 or (rc == 28 and 'Failed to connect to ' in text):
        phase, tcp = 'tcp_connect', False
    elif rc in (35, 60):
        phase, tcp, tls = 'tls', True, False
    elif http > 0:
        phase, tcp, tls = 'http_body', True, True
    elif rc == 28 and 'connect' in fields and 'tls' in fields:
        try:
            connected, negotiated = float(fields['connect']), float(fields['tls'])
            if not all(math.isfinite(t) and 0 <= t <= seconds for t in (connected, negotiated)):
                return invalid('malformed_phase_timing')
        except ValueError:
            return invalid('malformed_phase_timing')
        if negotiated > 0:
            phase, tcp, tls = 'http_body', True, True
        elif connected > 0:
            phase, tcp, tls = 'tls', True, False
        else:
            phase, tcp = 'tcp_connect', False
    reason = 'timeout' if rc == 28 else ('tls_failed' if phase == 'tls' else 'network_error')
    return Probe(**args, success=False, reason=reason, phase=phase,
                 tcp_success=tcp, tls_success=tls)


@dataclass(frozen=True)
class Assessment:
    kind: str
    reason: str
    scope: str = 'undetermined'
    available: bool | None = None
    transport_alive: bool | None = None
    signals: tuple[str, ...] = ()
    handshake_age: float | None = None
    wg_transfer: dict | None = None
    one_way_suspect: bool | None = None


def assess(probes, *, path_verified, read_error=False, service_present=True,
           peer_icmp=None, handshake_age=None, dns_udp=None, dns_tcp=None,
           controls_healthy=None, peer_egress_failed=None, public_ip_match=None,
           wg_transfer=None):
    if read_error:
        return Assessment('unknown', 'read_error')
    if service_present is False:
        return Assessment('failed', 'local_service_down', 'local_service', False)
    if not path_verified or public_ip_match is False:
        return Assessment('unknown', 'path_invalid')
    if len(probes) != 2 or len({p.target for p in probes}) != 2 or len({p.family for p in probes}) != 2:
        return Assessment('unknown', 'independent_targets_required')
    generations = {p.generation for p in probes if p.valid}
    if len(generations) > 1:
        return Assessment('unknown', 'generation_mismatch')
    success = sum(p.valid and p.success is True for p in probes)
    valid = sum(p.valid for p in probes)
    signals = []
    for key, value in [('peer_icmp', peer_icmp), ('dns_udp', dns_udp), ('dns_tcp', dns_tcp)]:
        if value is not None:
            signals.append(key + ('_ok' if value else '_failed'))
    if handshake_age is not None and handshake_age > 180:
        signals.append('handshake_stale')
    one_way_suspect = None
    if wg_transfer is not None:
        received = wg_transfer['received_delta_bytes']
        sent = wg_transfer['sent_delta_bytes']
        # A 128-byte floor keeps ordinary keepalive traffic from becoming a
        # diagnostic signal. It is still corroborating evidence, never a verdict.
        one_way_suspect = ((received == 0 and sent >= 128) or
                           (sent == 0 and received >= 128))
        if one_way_suspect:
            signals.append('wg_one_way_suspect')
    transport = True if peer_icmp is True else (False if peer_icmp is False else None)
    if valid < 2 and success == 0:
        reasons = {p.reason for p in probes}
        reason = next(iter(reasons)) if valid == 0 and len(reasons) == 1 else 'incomplete_observation'
        return Assessment('unknown', reason, signals=tuple(signals),
                          wg_transfer=wg_transfer, one_way_suspect=one_way_suspect)
    if success:
        warnings = [s for s in signals if s.endswith(('_failed', '_stale'))]
        partial = success < 2 or bool(warnings)
        return Assessment('partial' if partial else 'healthy',
                          'partial_https' if success < 2 else (warnings[0] if warnings else 'ok'),
                          'https_available', True, transport, tuple(signals),
                          wg_transfer=wg_transfer, one_way_suspect=one_way_suspect)
    phases = {p.phase for p in probes}
    reason = 'tcp_connect_failed' if phases == {'tcp_connect'} else (
        'tls_failed' if phases == {'tls'} else 'https_failed')
    scope = 'undetermined'
    if peer_icmp is False and handshake_age is not None and handshake_age > 180:
        reason, scope = 'tunnel_unreachable', 'tunnel_direction'
    elif one_way_suspect and handshake_age is not None and handshake_age > 180:
        reason, scope = 'tunnel_one_way_suspect', 'tunnel_direction'
    elif peer_icmp is True:
        scope = 'beyond_peer_or_protocol_specific'
    if controls_healthy is True:
        signals.append('independent_control_ok')
    if controls_healthy is False:
        scope = 'shared_targets_or_paths'
    if peer_egress_failed is True:
        scope = 'peer_host_egress_or_external_path'
    return Assessment('failed', reason, scope, False, transport, tuple(signals),
                      wg_transfer=wg_transfer, one_way_suspect=one_way_suspect)
