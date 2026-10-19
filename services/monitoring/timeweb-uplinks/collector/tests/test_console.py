from http.client import HTTPConnection
from contextlib import contextmanager
import json
import re
import shutil
import subprocess
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from uplink_monitor.console import PAGE_SCRIPT, Console, activity_section, card, flex_card, make_server


class Runner:
    def __init__(self):
        self.mode = {'cenuta': 'native', 'fornex': 'native'}

    def __call__(self, args, **_):
        upstream = 'cenuta' if 'cenuta' in args[0] else 'fornex'
        if args[1] in ('native', 'backup'):
            self.mode[upstream] = args[1]
        return SimpleNamespace(returncode=0,
                               stdout=f'mode={self.mode[upstream]} endpoint=example:1 handshake_age=1s\n')


def test_console_only_allows_fixed_controller_actions(tmp_path):
    runner = Runner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner, clock=lambda: 100)
    result = console.action('fornex', 'backup')
    assert result['success'] is True
    assert runner.mode['fornex'] == 'backup'
    assert '"upstream":"fornex"' in (tmp_path/'console-actions.jsonl').read_text()


def test_console_rejects_unknown_action(tmp_path):
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=Runner())
    try:
        console.action('fornex', 'status; rm -rf /')
    except ValueError as exc:
        assert str(exc) == 'invalid_action'
    else:
        raise AssertionError('unknown command accepted')


class FlexRunner(Runner):
    def __init__(self):
        super().__init__()
        self.default = {'exit': 'fx', 'ru_direct': 'off'}
        self.overrides = {device: {'exit': None, 'ru_direct': None}
                          for device in ('macbook', 'iphone12', 'macmini')}

    def __call__(self, args, **kwargs):
        if args[0].endswith('timeweb-flex-fleet'):
            if args[1] == 'set':
                scope, field, value = args[2:]
                target = self.default if scope == 'all' else self.overrides[scope]
                target[field] = None if value == 'default' else value
            devices = {}
            for device in self.overrides:
                effective = {field: self.overrides[device][field] or self.default[field]
                             for field in self.default}
                devices[device] = {'label': device, 'peer': '10.50.50.39/32',
                                   'overrides': self.overrides[device], 'effective': effective,
                                   'observed': {'exit': effective['exit'],
                                                'ru_direct': effective['ru_direct'] == 'on',
                                                'observed': 'ready'},
                                   'route': 'ready',
                                   'activity': {'state': 'inactive', 'age_seconds': None}}
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                'default': self.default, 'devices': devices,
                'counts': {'active': 0, 'inactive': 3, 'unknown': 0,
                           'total': 3, 'route_ready': 3}}))
        return super().__call__(args, **kwargs)


def test_concurrent_views_share_controller_reads_and_actions_invalidate(tmp_path):
    runner = FlexRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    original = console.snapshot
    calls = []

    def snapshot():
        calls.append(True)
        return original()

    console.snapshot = snapshot
    with ThreadPoolExecutor(max_workers=6) as pool:
        views = list(pool.map(lambda _: console.view(), range(6)))
    assert len(calls) == 1
    assert all(view is views[0] for view in views)
    console.flex_action('all', 'exit', 'cen')
    assert console.view()[1]['default']['exit'] == 'cen'
    assert len(calls) == 2
    console.action('cenuta', 'backup')
    assert console.view()[0]['cenuta']['controller']['mode'] == 'backup'
    assert len(calls) == 3


def test_flex_action_is_allowlisted_and_audited(tmp_path):
    runner = FlexRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner, clock=lambda: 100)
    result = console.flex_action('all', 'exit', 'cen')
    assert result['success'] is True
    assert console.flex_controller()['default']['exit'] == 'cen'
    assert console.flex_controller()['devices']['iphone12']['effective']['exit'] == 'cen'
    assert console.flex_controller()['devices']['macmini']['effective']['exit'] == 'cen'
    assert 'flex-fleet' in (tmp_path/'console-actions.jsonl').read_text()
    markup = flex_card(console.flex_controller(), 'token')
    assert 'name="exit" value="cen" checked' in markup
    assert 'name="ru_direct" value="off" checked' in markup
    assert 'Devices (3)' in markup
    assert '<legend>Gateway</legend>' in markup
    assert 'Apply' not in markup


def test_flex_rejects_unknown_mode(tmp_path):
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=FlexRunner())
    try:
        console.flex_action('other', 'ru_direct', 'off')
    except ValueError as exc:
        assert str(exc) == 'invalid_flex_request'
    else:
        raise AssertionError('unknown FLEX route accepted')


def test_flex_http_action_requires_csrf_and_confirms_state(tmp_path):
    runner = FlexRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    server = make_server(tmp_path/'history.sqlite', tmp_path, port=0, console=console)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = HTTPConnection('127.0.0.1', server.server_port)
    try:
        conn.request('GET', '/')
        page = conn.getresponse()
        body = page.read().decode()
        assert '<title>TimeWeb: VPN control</title>' in body
        assert '<h1>TimeWeb: VPN control</h1>' in body
        cookie = page.getheader('Set-Cookie').split(';', 1)[0]
        csrf = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        assert 'SOCKS-TW-FLEX' in body
        assert 'http-equiv="refresh"' not in body
        assert 'Background refresh: 15 s.' in body
        assert 'Recent commands' in body
        assert '<legend>Gateway</legend>' in body
        assert 'onchange="switchFlex(this)"' in body
        fields = urlencode({'csrf': csrf, 'scope': 'all', 'field': 'exit', 'value': 'cen'})
        conn.request('POST', '/flex-action', fields, {'Cookie': cookie,
                     'Origin': f'http://127.0.0.1:{server.server_port}',
                     'Content-Type': 'application/x-www-form-urlencoded'})
        response = conn.getresponse()
        assert response.status == 303
        assert response.getheader('Location') == '/#activity'
        response.read()
        assert runner.default['exit'] == 'cen'
        conn.request('GET', '/state', headers={'Cookie': cookie})
        state = conn.getresponse()
        partial = state.read().decode()
        assert state.status == 200
        assert 'All devices: Gateway cen' in partial
        assert '1970-01-' not in partial
        assert '<html' not in partial
        conn.request('GET', '/?result=Legacy+notice', headers={'Cookie': cookie})
        legacy_page = conn.getresponse().read().decode()
        assert 'Legacy notice' not in legacy_page
        assert 'All devices: Gateway cen' in legacy_page
        conn.request('POST', '/flex-action', fields, {'Content-Type': 'application/x-www-form-urlencoded'})
        rejected = conn.getresponse()
        assert rejected.status == 400
        rejected.read()
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_recent_commands_are_bounded_and_show_requested_and_observed_modes(tmp_path):
    runner = FlexRunner()
    current_time = [100]
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner,
                      clock=lambda: current_time[0])
    for index in range(7):
        current_time[0] += 1
        console.action('fornex', 'backup' if index % 2 == 0 else 'native')
    recent = console.recent_actions()
    assert len(recent) == 6
    assert recent[0]['timestamp'] == 107
    assert recent[-1]['timestamp'] == 102
    markup = activity_section(recent)
    assert 'Fornex: switch to WSS' in markup
    assert 'Observed: native -&gt; backup' in markup
    assert '1970-01-01 00:01:47 UTC' in markup
    assert markup.count('<li>') == 6


def test_unconfirmed_command_is_not_reported_as_success(tmp_path):
    markup = activity_section([{'timestamp': 100, 'upstream': 'cenuta',
                                'action': 'native', 'before_mode': 'backup',
                                'result_mode': 'backup', 'success': False}])
    assert 'Cenuta: switch to native UDP' in markup
    assert 'Observed: backup -&gt; backup' in markup
    assert 'Error: not recorded in this legacy entry' in markup
    assert 'Not confirmed' in markup


def test_action_readback_confirms_mode_despite_failed_command_report(tmp_path):
    class FailedReport(Runner):
        def __call__(self, args, **kwargs):
            if args[1] == 'backup':
                self.mode['cenuta'] = 'backup'
                return SimpleNamespace(returncode=1, stdout='')
            return super().__call__(args, **kwargs)

    console = Console(tmp_path/'history.sqlite', tmp_path, runner=FailedReport(),
                      clock=lambda: 100)
    result = console.action('cenuta', 'backup')
    assert result['success'] is True
    assert result['result_mode'] == 'backup'
    assert result['command_error'] == 'controller_exit_1'
    assert 'mode verified by read-back' in activity_section(console.recent_actions())


def test_failed_action_retains_error_in_log_and_card(tmp_path):
    class FailedSwitch(Runner):
        def __call__(self, args, **kwargs):
            if args[1] == 'backup':
                return SimpleNamespace(returncode=1, stdout='')
            return super().__call__(args, **kwargs)

    console = Console(tmp_path/'history.sqlite', tmp_path, runner=FailedSwitch(),
                      clock=lambda: 100)
    result = console.action('cenuta', 'backup')
    assert result['success'] is False
    assert result['error'] == 'Expected backup, observed native; controller: controller_exit_1'
    assert 'Error: Expected backup, observed native' in activity_section(console.recent_actions())
    data = {'monitor': {}, 'controller': console.controller('cenuta'),
            'auto': {'reason': 'no data', 'failures': 0}}
    assert 'Expected backup, observed native' in card('cenuta', data, 'token', result)
    assert 'setTimeout(()=>{element.textContent=\'\'},10000)' in PAGE_SCRIPT


def test_compact_transport_card_shows_verified_mode_and_details():
    data = {'monitor': {'state': 'UP', 'reason': 'ok',
                        'assessment': {'handshake_age': 42}},
            'controller': {'mode': 'backup', 'endpoint': '127.0.0.1:51921',
                           'xray_mode': 'backup', 'xray_endpoint': '127.0.0.1:51923'},
            'auto': {'reason': 'already_backup', 'failures': 0}}
    markup = card('fornex', data, 'token')
    assert 'name="action" value="backup" checked' in markup
    assert 'name="action" value="native" checked' not in markup
    assert 'data-mode="backup"' in markup
    assert '<details class="details">' in markup
    assert 'class="info"' not in markup
    assert '<dt>Endpoint</dt><dd>127.0.0.1:51921</dd>' in markup
    assert '<dt>WG path</dt><dd>WSS</dd>' in markup
    assert '<dt>Xray path</dt><dd>WSS</dd>' in markup
    assert '<dt>Xray</dt>' not in markup
    assert '<dt>Handshake</dt><dd>42 s</dd>' in markup
    assert '<dt>Monitoring</dt>' not in markup
    assert 'class="health-indicator"' in markup
    assert 'aria-label="Monitoring: UP: ok; transport: backup"' in markup
    data['controller']['mode'] = 'unavailable'
    unavailable = card('fornex', data, 'token')
    assert unavailable.count(' disabled onchange="switchTransport(this)"') == 2
    assert ' checked' not in unavailable


def test_partial_controller_is_preserved_and_red(tmp_path):
    class PartialRunner(Runner):
        def __call__(self, args, **kwargs):
            return SimpleNamespace(returncode=0, stdout=(
                'mode=partial relay_mode=backup endpoint=127.0.0.1:51922 '
                'xray_mode=native xray_endpoint=example:1 handshake_age=1s\n'))

    console = Console(tmp_path/'history.sqlite', tmp_path, runner=PartialRunner())
    controller = console.controller('cenuta')
    assert controller['mode'] == 'partial'
    assert controller['relay_mode'] == 'backup'
    data = {'monitor': {'state': 'UP', 'reason': 'ok'}, 'controller': controller,
            'auto': {'reason': 'no data', 'failures': 0}}
    markup = card('cenuta', data, 'token')
    assert 'class="card error"' in markup
    assert '<p class="error-text">PARTIAL</p>' in markup
    assert '>PARTIAL<span class="health-tooltip"' in markup
    assert '<dt>WG path</dt><dd>WSS</dd>' in markup
    assert '<dt>Xray path</dt><dd>UDP</dd>' in markup
    assert markup.count(' disabled onchange="switchTransport(this)"') == 2


def test_transport_radio_post_returns_controller_confirmation(tmp_path):
    assert 'new URLSearchParams(new FormData(form))' in PAGE_SCRIPT
    assert "fetch('/flex-action',{method:'POST'" in PAGE_SCRIPT
    assert 'confirm(' not in PAGE_SCRIPT
    assert "'Content-Type':'application/x-www-form-urlencoded'" in PAGE_SCRIPT
    runner = Runner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    server = make_server(tmp_path/'history.sqlite', tmp_path, port=0, console=console)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = HTTPConnection('127.0.0.1', server.server_port)
    try:
        conn.request('GET', '/')
        page = conn.getresponse()
        body = page.read().decode()
        cookie = page.getheader('Set-Cookie').split(';', 1)[0]
        csrf = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        fields = urlencode({'csrf': csrf, 'upstream': 'fornex', 'action': 'backup'})
        conn.request('POST', '/action', fields, {'Cookie': cookie,
                     'Origin': f'http://127.0.0.1:{server.server_port}',
                     'Accept': 'application/json',
                     'Content-Type': 'application/x-www-form-urlencoded'})
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader('Content-Type') == 'application/json; charset=utf-8'
        assert json.loads(response.read()) == {'success': True, 'error': None}
        assert runner.mode['fornex'] == 'backup'
        conn.request('GET', '/state', headers={'Cookie': cookie})
        state = conn.getresponse()
        assert 'data-mode="backup"' in state.read().decode()
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join()


MAC = 'AA:BB:CC:DD:EE:01'
REVISION = 'a' * 64


def s2s_status():
    return {'available': True, 'can_remove': True, 'revision': REVISION, 'checked_at': 100,
            'tunnel': {'state': 'up', 'path': 'TimeWeb', 'egress': 'route-ready',
                       'detail': 'Route verified'},
            'devices': [{'id': MAC, 'label': 'Laptop', 'ip': '192.168.89.10',
                         'online': True, 'selected': False, 'status': 'local'}],
            'error': None}


class S2SRunner(FlexRunner):
    def __init__(self):
        super().__init__()
        self.status = s2s_status()
        self.calls = []

    def __call__(self, args, **kwargs):
        if args[0] != '/usr/local/sbin/timeweb-s2s':
            return super().__call__(args, **kwargs)
        self.calls.append((args, kwargs))
        value = json.loads(json.dumps(self.status))
        if args[1] != 'status':
            value['devices'][0].update(selected=args[1] == 'add',
                                       status='remote' if args[1] == 'add' else 'local')
            self.status = value
            value['success'] = True
        return SimpleNamespace(returncode=0, stdout=json.dumps(value))


def test_s2s_cache_is_separate_lazy_and_serialized(tmp_path, monkeypatch):
    runner = S2SRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner, clock=lambda: 100)
    now = [10]
    monkeypatch.setattr('uplink_monitor.console.time.monotonic', lambda: now[0])
    vpn = console.view()
    assert len(vpn) == 2
    assert runner.calls == []
    with ThreadPoolExecutor(max_workers=6) as pool:
        views = list(pool.map(lambda _: console.s2s_view(), range(6)))
    assert len(runner.calls) == 1
    assert all(view is views[0] for view in views)
    now[0] += 14
    assert console.s2s_view() is views[0]
    now[0] += 1
    console.s2s_view()
    assert len(runner.calls) == 2
    result = console.s2s_action('add', MAC, REVISION)
    assert result['success'] is True
    assert result['devices'][0]['selected'] is True
    assert console.s2s_view()['devices'][0]['selected'] is True
    assert runner.calls[-1][0] == ['/usr/local/sbin/timeweb-s2s', 'add', MAC, REVISION]
    assert runner.calls[-1][1] == {'text': True, 'capture_output': True,
                                  'timeout': 125, 'check': False}
    assert console._view_cache is vpn


@pytest.mark.parametrize('action,device,revision', [
    ('add;id', MAC, REVISION), ('status', MAC, REVISION),
    ('remove', MAC.lower(), REVISION), ('add', MAC + '\n', REVISION),
    ('add', '--help', REVISION), ('add', MAC, REVISION + ';id'),
    ('add', MAC, REVISION + '\n'), ('add', MAC, 'a' * 63),
])
def test_s2s_rejects_injected_or_noncanonical_arguments(tmp_path, action, device, revision):
    runner = S2SRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    with pytest.raises(ValueError, match='invalid_s2s_request'):
        console.s2s_action(action, device, revision)
    assert runner.calls == []


@pytest.mark.parametrize('payload', [None, [], {}, 'bad json',
    dict(s2s_status(), available=1), dict(s2s_status(), revision='--help'),
    dict(s2s_status(), checked_at=float('nan')),
    dict(s2s_status(), tunnel={'state': 'up'}),
    dict(s2s_status(), devices=[dict(s2s_status()['devices'][0], online='yes')]),
    dict(s2s_status(), devices=[dict(s2s_status()['devices'][0], id=MAC.lower())]),
    dict(s2s_status(), devices=[dict(s2s_status()['devices'][0], ip='not an IP')]),
    dict(s2s_status(), devices=s2s_status()['devices'] * 2),
])
def test_s2s_malformed_output_is_unavailable_without_raw_output(tmp_path, payload):
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    value = console.s2s_view()
    assert value['available'] is False
    assert value['devices'] == []
    assert value['tunnel'] == {'state': 'unknown', 'path': 'TimeWeb',
                                'egress': 'unknown', 'detail': ''}
    assert value['error'] == 'Invalid site-to-site controller output'


def test_s2s_success_requires_controller_confirmation_and_requested_state(tmp_path):
    value = s2s_status()

    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(value))

    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    assert console.s2s_action('add', MAC, REVISION)['success'] is False
    value['success'] = True
    assert console.s2s_action('add', MAC, REVISION)['success'] is False
    value['devices'][0].update(selected=True, status='remote')
    assert console.s2s_action('add', MAC, REVISION)['success'] is True
    value['success'] = False
    assert console.s2s_action('add', MAC, REVISION)['success'] is False


def test_s2s_remove_is_confirmed_with_local_router_when_remote_is_unavailable(tmp_path):
    value = dict(s2s_status(), available=False, can_remove=True, success=True,
                 error='Remote router unavailable')
    value['tunnel'].update(state='unknown', egress='unknown')
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(value))
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    result = console.s2s_action('remove', MAC, REVISION)
    assert result['success'] is True
    assert result['can_remove'] is True and result['available'] is False
    value['can_remove'] = 'yes'
    assert console.s2s_action('remove', MAC, REVISION)['success'] is False


def test_s2s_controller_failure_preserves_last_known_selection_as_unknown(tmp_path):
    runner = S2SRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner, clock=lambda: 100)
    console.s2s_action('add', MAC, REVISION)
    def unavailable(*args, **kwargs):
        raise OSError('unavailable')
    console.runner = unavailable
    console._s2s_time = 0
    status = console.s2s_view()
    assert status['devices'][0]['selected'] is True
    assert status['devices'][0]['status'] == 'unknown'
    assert status['can_remove'] is False and status['revision'] == ''
    assert 'Last known selection' in status['tunnel']['detail']
    assert console.s2s_action('remove', MAC, REVISION)['success'] is False
    assert console.s2s_view()['devices'][0]['selected'] is True


@contextmanager
def s2s_http(tmp_path):
    runner = S2SRunner()
    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner, clock=lambda: 100)
    server = make_server(tmp_path/'history.sqlite', tmp_path, port=0, console=console)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = HTTPConnection('127.0.0.1', server.server_port)
    try:
        conn.request('GET', '/')
        page = conn.getresponse()
        body = page.read().decode()
        cookie = page.getheader('Set-Cookie').split(';', 1)[0]
        csrf = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        yield conn, runner, console, body, {'Cookie': cookie,
            'Origin': f'http://127.0.0.1:{server.server_port}',
            'Content-Type': 'application/x-www-form-urlencoded'}, csrf
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_s2s_http_lazy_state_and_verified_add_remove(tmp_path):
    with s2s_http(tmp_path) as (conn, runner, console, body, headers, csrf):
        assert runner.calls == []
        assert 'href="#vpn"' in body
        assert 'href="#site-to-site"' in body
        assert 'Available devices' in body
        assert 'Fethiye → Nakhimova' in body
        assert 'Egress readiness' in body
        assert 'cdn' not in body.lower()
        conn.request('GET', '/state', headers=headers)
        assert conn.getresponse().read()
        assert runner.calls == []
        conn.request('GET', '/s2s-state', headers=headers)
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader('Cache-Control') == 'no-store'
        assert response.getheader('Content-Type') == 'application/json; charset=utf-8'
        assert json.loads(response.read()) == s2s_status()
        for action, selected in [('add', True), ('remove', False)]:
            if action == 'remove':
                runner.status['checked_at'] = 1
                runner.status['tunnel'].update(state='down', egress='blocked')
            fields = urlencode({'csrf': csrf, 'action': action, 'device': MAC, 'revision': REVISION})
            conn.request('POST', '/s2s-action', fields, headers)
            response = conn.getresponse()
            assert response.status == 200
            assert response.getheader('Cache-Control') == 'no-store'
            value = json.loads(response.read())
            assert value['success'] is True
            assert value['devices'][0]['selected'] is selected
        assert len(runner.calls) == 3


@pytest.mark.parametrize('case,expected', [('csrf', 400), ('cookie', 400),
    ('origin', 403), ('host', 404), ('extra', 400), ('duplicate', 400),
    ('oversize', 400), ('injection', 400), ('unicode_csrf', 400)])
def test_s2s_http_rejects_untrusted_mutations(tmp_path, case, expected):
    with s2s_http(tmp_path) as (conn, runner, console, body, headers, csrf):
        fields = {'csrf': csrf, 'action': 'add', 'device': MAC, 'revision': REVISION}
        if case == 'csrf':
            fields['csrf'] = 'bad'
        elif case == 'cookie':
            headers.pop('Cookie')
        elif case == 'origin':
            headers['Origin'] = 'https://attacker.example'
        elif case == 'host':
            headers['Host'] = 'attacker.example:19118'
        elif case == 'extra':
            fields['scope'] = 'all'
        elif case == 'injection':
            fields['device'] = MAC + ';id'
        elif case == 'unicode_csrf':
            fields['csrf'] = '\u0410' * 32
        encoded = urlencode(fields)
        if case == 'duplicate':
            encoded += '&device=' + MAC
        elif case == 'oversize':
            encoded += '&padding=' + 'a' * 512
        conn.request('POST', '/s2s-action', encoded, headers)
        response = conn.getresponse()
        assert response.status == expected
        response.read()
        assert runner.calls == []


def test_s2s_state_rejects_foreign_host_and_controller_secrets_are_not_forwarded(tmp_path):
    with s2s_http(tmp_path) as (conn, runner, console, body, headers, csrf):
        conn.request('GET', '/s2s-state', headers={'Host': 'attacker.example:19118'})
        response = conn.getresponse()
        assert response.status == 404
        response.read()
        assert runner.calls == []
        runner.status['router_password'] = 'private-router-secret'
        runner.status['devices'][0]['private_key'] = 'private-router-secret'
        conn.request('GET', '/s2s-state', headers=headers)
        value = conn.getresponse().read().decode()
        assert 'private-router-secret' not in value
        assert json.loads(value)['available'] is True


@pytest.mark.parametrize('failure', ['timeout', 'missing', 'exit', 'malformed'])
def test_s2s_controller_failures_have_safe_default_shape(tmp_path, failure):
    def runner(*args, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(args[0], 125, output='private-router-secret')
        if failure == 'missing':
            raise OSError('private-router-secret')
        return SimpleNamespace(returncode=1 if failure == 'exit' else 0,
                               stdout='private-router-secret', stderr='private-router-secret')

    console = Console(tmp_path/'history.sqlite', tmp_path, runner=runner)
    for value in [console.s2s_view(), console.s2s_action('add', MAC, REVISION)]:
        assert value['available'] is False
        assert value['devices'] == []
        assert value['tunnel']['state'] == 'unknown'
        assert 'private-router-secret' not in json.dumps(value)
    assert value['success'] is False


def test_s2s_browser_refresh_pending_actions_and_responsive_layout(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for the optional browser regression')
    with s2s_http(tmp_path) as (_, _, _, markup, _, _):
        result = subprocess.run([node, '-e', r'''
const fs=require('fs'), assert=require('node:assert/strict');
let chromium;
try{({chromium}=require('playwright'));}catch{process.exit(77);}
const input=JSON.parse(fs.readFileSync(0,'utf8'));
(async()=>{
  let browser;
  try{browser=await chromium.launch({headless:true,channel:process.platform==='darwin'?'chrome':undefined});}
  catch(error){console.error(error.message);process.exit(77);}
  try{
    const page=await browser.newPage({viewport:{width:1200,height:900}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    const mac=input.state.devices[0].id;
    const selected='AA:BB:CC:DD:EE:02';
    let state=structuredClone(input.state), reads=0, writes=0;
    state.checked_at=Date.now()/1000;
    state.devices.push({...state.devices[0],id:selected,selected:true,online:false,status:'blocked',label:'Selected device'});
    state.devices.push({...state.devices[0],id:'AA:BB:CC:DD:EE:03',online:false});
    let releaseAction, releaseRead, holdRead=false;
    await page.route('http://127.0.0.1:19118/**',async route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/s2s-state'){
        reads++;
        if(holdRead)await new Promise(resolve=>releaseRead=resolve);
        await route.fulfill({json:state});
      }else if(path==='/s2s-action'){
        writes++;
        const fields=new URLSearchParams(route.request().postData());
        assert.equal(fields.get('revision'),input.state.revision);
        assert.equal(fields.get('device'),selected);
        assert.equal(fields.get('action'),'remove');
        await new Promise(resolve=>releaseAction=resolve);
        await route.fulfill({json:{...state,success:false,error:'Revision changed; refresh and retry'}});
      }else await route.fulfill({contentType:'text/html',body:input.markup});
    });
    await page.goto('http://127.0.0.1:19118/');
    assert.equal(reads,0);
    await page.locator('#s2s-tab').click();
    await page.waitForFunction(()=>s2sData!==null);
    const select=page.locator('.s2s-add select'), add=page.locator('.s2s-add button');
    assert.equal(await select.locator('option').count(),2);
    await select.selectOption(mac);
    assert.equal(await add.isEnabled(),true);
    await page.evaluate(()=>refreshState());
    assert.equal(await select.inputValue(),mac);
    assert.equal(new URL(page.url()).hash,'#site-to-site');
    assert.equal(await page.locator('.s2s-remove').getAttribute('title'),'Return to local internet');
    assert.equal(await page.locator('.s2s-selected').innerText().then(text=>text.includes('192.168.89.10')),true);
    for(const mode of ['down','stale','blocked']){
      state.tunnel.state=mode==='down'?'down':'up';
      state.tunnel.egress=mode==='blocked'?'blocked':'route-ready';
      state.checked_at=Date.now()/1000-(mode==='stale'?90:0);
      await page.evaluate(()=>refreshState());
      assert.equal(await add.isDisabled(),true);
      assert.equal(await page.locator('.s2s-remove').isEnabled(),true);
    }
    state.available=false;
    await page.evaluate(()=>refreshState());
    assert.equal(await add.isDisabled(),true);
    assert.equal(await page.locator('[data-s2s="availability"]').innerText(),'Unavailable');
    state.available=true;state.checked_at=Date.now()/1000;state.tunnel.egress='route-ready';
    await page.evaluate(()=>refreshState());
    holdRead=true;
    await page.evaluate(()=>{window.pendingRefresh=refreshState();});
    await page.waitForFunction(()=>true);
    while(!releaseRead)await new Promise(resolve=>setTimeout(resolve,10));
    await page.locator('.s2s-remove').click();
    while(!releaseAction)await new Promise(resolve=>setTimeout(resolve,10));
    const before=await page.locator('.s2s-selected').innerHTML();
    state.devices[1].label='Changed by a background read';
    holdRead=false;releaseRead();
    await page.evaluate(()=>window.pendingRefresh);
    assert.equal(await page.locator('.s2s-selected').innerHTML(),before);
    assert.equal(await select.inputValue(),mac);
    assert.equal(await select.isDisabled(),true);
    const pendingReads=reads;
    await page.evaluate(()=>refreshState());
    assert.equal(reads,pendingReads);
    releaseAction();
    await page.waitForFunction(()=>!submitting);
    assert.equal(writes,1);
    assert.match(await page.locator('.s2s-message').innerText(),/Revision changed/);
    assert.equal(await select.inputValue(),mac);
    await page.reload();
    await page.waitForFunction(()=>s2sData!==null);
    assert.equal(await page.locator('#site-to-site').isVisible(),true);
    state.devices[1].label='LongDeviceNameWithoutSpaces'.repeat(12);
    await page.evaluate(()=>refreshState());
    for(const width of [1200,390,320]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      const rows=await page.locator('.s2s-selected li').evaluateAll(rows=>rows.map(row=>{
        const [identity,status,button]=Array.from(row.children).map(child=>child.getBoundingClientRect());
        return identity.right<=status.left && status.right<=button.left;
      }));
      assert.ok(rows.every(Boolean));
    }
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
'''], input=json.dumps({'markup': markup, 'state': s2s_status()}),
            text=True, capture_output=True, timeout=60, check=False)
    if result.returncode == 77:
        pytest.skip('Playwright and a local Chromium browser are required')
    assert result.returncode == 0, result.stdout + result.stderr
