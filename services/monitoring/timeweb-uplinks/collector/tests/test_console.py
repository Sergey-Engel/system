from http.client import HTTPConnection
import json
import re
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import urlencode

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
