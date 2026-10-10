"""Read-only loopback exporter. HTTP requests never initiate network probes."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import math
from pathlib import Path
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

from .collector import POLICIES
from .storage import UPSTREAMS, current, incidents, report
from .runtime import read_json
from .history_export import export_page

STATES = {'UNKNOWN': 0, 'UP': 1, 'DEGRADED': 2, 'DOWN': 3}


def transport_modes(path):
    if path is None:
        return {}
    try:
        payload = read_json(path)
        upstreams = payload.get('upstreams', {})
        if not isinstance(upstreams, dict):
            return {}
        return {upstream: state['mode'] for upstream, state in upstreams.items()
                if upstream in UPSTREAMS and isinstance(state, dict)
                and state.get('mode') in ('native', 'backup')}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def metrics(snapshot, pilot=False, transport_state_path=None):
    rows = []

    def emit(name, help_text, samples, kind='gauge'):
        rows.extend((f'# HELP {name} {help_text}', f'# TYPE {name} {kind}'))
        for labels, value in samples:
            if value is None:
                continue
            label_text = ','.join(f'{key}={json.dumps(val)}' for key, val in labels.items())
            rows.append(f'{name}{{{label_text}}} {int(value) if isinstance(value, bool) else value}')

    def upstream_samples(fn):
        return [({'upstream': up}, fn(snapshot[up])) for up in UPSTREAMS]

    if pilot:
        emit('vpn_uplink_pilot_info', 'Limited RTNL and pre/post snapshots; no universal WG/firewall ABA guarantee.',
             [({'scope': 'rtnl_and_snapshots', 'mode': 'pilot'}, 1)])
    modes = transport_modes(transport_state_path)
    emit('vpn_uplink_selected_transport_info',
         'Selected TimeWeb-to-upstream transport from the local controller state.',
         [({'upstream': upstream, 'mode': mode}, 1) for upstream, mode in modes.items()])
    emit('vpn_uplink_reason_info', 'Current bounded assessment reason.',
         [({'upstream': up, 'reason': snapshot[up]['reason']}, 1) for up in UPSTREAMS])
    emit('vpn_uplink_signal_info', 'Fresh differential diagnostic signals.',
         [({'upstream': up, 'signal': signal}, 1) for up in UPSTREAMS
          if snapshot[up]['fresh'] for signal in snapshot[up].get('assessment', {}).get('signals', [])])

    emit('vpn_uplink_expected', 'Configured upstream inventory.',
         upstream_samples(lambda s: 1))
    emit('vpn_uplink_state', 'HTTPS egress state: 0 unknown, 1 up, 2 degraded, 3 down.',
         upstream_samples(lambda s: STATES[s['state']]))
    emit('vpn_uplink_observation_fresh', 'Snapshot freshness, not network success.',
         upstream_samples(lambda s: s['fresh']))
    emit('vpn_uplink_last_cycle_timestamp_seconds', 'Last committed observation wall clock.',
         upstream_samples(lambda s: s['observed']))
    emit('vpn_uplink_outages_total', 'Confirmed outage segments, interrupted across unknown gaps.',
         upstream_samples(lambda s: s['outages']), 'counter')
    emit('vpn_uplink_transport_alive', 'Fresh successful peer ICMP evidence, absent if unmeasured.',
         upstream_samples(lambda s: s.get('assessment', {}).get('transport_alive') if s['fresh'] else None))
    emit('vpn_uplink_handshake_age_seconds', 'Handshake age at last measurement, absent when unmeasured or stale.',
         upstream_samples(lambda s: s.get('assessment', {}).get('handshake_age') if s['fresh'] else None))
    transfer_samples = {field: [] for field in ('received_bytes', 'sent_bytes',
                                                 'received_delta_bytes', 'sent_delta_bytes')}
    one_way_samples = []
    for up in UPSTREAMS:
        assessment = snapshot[up].get('assessment', {})
        transfer = assessment.get('wg_transfer') if snapshot[up]['fresh'] else None
        for field in transfer_samples:
            transfer_samples[field].append(({'upstream': up}, transfer.get(field) if isinstance(transfer, dict) else None))
        one_way_samples.append(({'upstream': up}, assessment.get('one_way_suspect') if snapshot[up]['fresh'] else None))
    emit('vpn_uplink_wg_peer_transfer_bytes', 'WireGuard peer byte counters captured around the bound HTTPS batch.',
         [({**labels, 'direction': direction}, value)
          for direction, field in (('received', 'received_bytes'), ('sent', 'sent_bytes'))
          for labels, value in transfer_samples[field]])
    emit('vpn_uplink_wg_peer_transfer_delta_bytes', 'WireGuard peer byte delta during the protected HTTPS batch.',
         [({**labels, 'direction': direction}, value)
          for direction, field in (('received', 'received_delta_bytes'), ('sent', 'sent_delta_bytes'))
          for labels, value in transfer_samples[field]])
    emit('vpn_uplink_wg_one_way_suspect', 'Corroborating one-way WG traffic signal; not an automatic failover decision.',
         one_way_samples)
    samples = {field: [] for field in ('valid', 'success', 'seconds', 'tcp_success', 'tls_success')}
    for up in UPSTREAMS:
        row = snapshot[up]
        probes = {p['target']: p for p in row.get('probes', [])}
        for name in POLICIES:
            p = probes.get(name, {})
            valid = bool(row['fresh'] and p.get('valid') and
                         row.get('assessment', {}).get('kind') != 'unknown')
            labels = dict(upstream=up, check='https', target=name)
            for field in samples:
                value = valid if field == 'valid' else (p.get(field) if valid else None)
                samples[field].append((labels, value))
    emit('vpn_uplink_probe_valid', 'Measurement is usable.', samples['valid'])
    emit('vpn_uplink_probe_success', 'Expected HTTPS response; absent for invalid observations.', samples['success'])
    emit('vpn_uplink_probe_duration_seconds', 'Elapsed probe time; a timeout is not an RTT.', samples['seconds'])
    emit('vpn_uplink_probe_tcp_success', 'TCP phase outcome; absent if phase is unknown.', samples['tcp_success'])
    emit('vpn_uplink_probe_tls_success', 'TLS phase outcome; absent if phase is unknown.', samples['tls_success'])
    return '\n'.join(rows)+'\n'


def make_server(database, port=0, clock=time.time, health_path=None, pilot=False,
                transport_state_path=None):
    path = Path(database)

    def storage_ready():
        if health_path is None:
            return
        status = read_json(health_path)
        if status.get('storage_ok') is not True or not 0 <= clock()-status['updated'] <= 180:
            raise OSError('storage_health_unavailable')

    class Handler(BaseHTTPRequestHandler):
        server_version = 'UplinkLocalCandidate/0.1'

        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def log_message(self, *_):
            pass

        def send(self, code, payload, content='application/json'):
            data = payload.encode() if isinstance(payload, str) else json.dumps(payload, allow_nan=False).encode()
            if len(data) > 1024*1024:
                code, data, content = 503, b'{"error":"response_limit"}', 'application/json'
            self.send_response(code)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if len(self.path) > 2048:
                self.send(414, dict(error='request_limit'))
                return
            url = urlsplit(self.path)
            try:
                if url.path == '/healthz':
                    self.send(200, dict(http_process='ok', network_health='not_checked'))
                elif url.path == '/readyz':
                    storage_ready()
                    current(path, clock())
                    self.send(200, dict(storage='ok', network_health='not_checked'))
                elif url.path == '/metrics':
                    storage_ready()
                    self.send(200, metrics(current(path, clock()), pilot=pilot,
                                           transport_state_path=transport_state_path),
                              'text/plain; version=0.0.4; charset=utf-8')
                elif url.path == '/api/current':
                    storage_ready()
                    self.send(200, current(path, clock()))
                elif url.path == '/api/sync':
                    params = parse_qs(url.query, keep_blank_values=True, max_num_fields=2)
                    if set(params)-{'after','limit'} or any(len(v)!=1 for v in params.values()):
                        raise ValueError('invalid_cursor')
                    page=export_page(path,int(params.get('after',['-1'])[0]),int(params.get('limit',['100'])[0]))
                    try:
                        storage_ready()
                        page['source_ready']=True
                    except (OSError,ValueError,KeyError,TypeError):
                        page['source_ready']=False
                    page['server_time']=clock()
                    self.send(200,page)
                elif url.path in ('/api/summary', '/api/incidents'):
                    params = parse_qs(url.query, keep_blank_values=True, max_num_fields=4)
                    if set(params) - {'from', 'to', 'upstream', 'offset'} or any(len(v)!=1 for v in params.values()):
                        raise ValueError()
                    start, end = (float(params[k][0])/1000 for k in ('from', 'to'))
                    if not all(math.isfinite(t) for t in (start, end)) or start < 0 or not 0 < end-start <= 30*86400:
                        raise ValueError()
                    up = params.get('upstream', [None])[0]
                    if up is not None and up not in UPSTREAMS:
                        raise ValueError()
                    if url.path == '/api/summary':
                        self.send(200, [report(path, u, start, end) for u in (UPSTREAMS if up is None else (up,))])
                    else:
                        self.send(200, incidents(path, up, start, end, int(params.get('offset', ['0'])[0])))
                else:
                    self.send(404, dict(error='not_found'))
            except (ValueError, KeyError, TypeError):
                self.send(400, dict(error='invalid_request'))
            except (sqlite3.Error, OSError):
                self.send(503, dict(error='storage_unavailable'))

    # One request at a time, with socket/SQL bounds; no thread-per-request growth.
    return HTTPServer(('127.0.0.1', port), Handler)
