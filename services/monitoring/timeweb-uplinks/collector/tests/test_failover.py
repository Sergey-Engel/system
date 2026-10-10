from types import SimpleNamespace

from uplink_monitor.failover import CenutaFailover, FornexFailover
from uplink_monitor.model import Assessment


class Runner:
    def __init__(self, controller='/usr/local/sbin/timeweb-cenuta-wg-console-transport'):
        self.mode = 'native'
        self.calls = []
        self.controller = controller

    def __call__(self, args, **_):
        self.calls.append(tuple(args))
        if args[-1] == 'status':
            return SimpleNamespace(returncode=0,
                                   stdout=f'mode={self.mode} endpoint=example:1 handshake_age=1s\n')
        if args[-1] == 'backup':
            self.mode = 'backup'
            return SimpleNamespace(returncode=0, stdout='mode=backup endpoint=127.0.0.1:1\n')
        raise AssertionError(args)


def config():
    return {'cenuta_auto_failover': {
        'enabled': True,
        'controller': '/usr/local/sbin/timeweb-cenuta-wg-console-transport',
        'required_consecutive_failures': 2,
        'handshake_stale_seconds': 180,
        'cooldown_seconds': 900,
    }}


def fornex_config():
    return {'fornex_auto_failover': {
        'enabled': True,
        'controller': '/usr/local/sbin/timeweb-fornex-wg-console-transport',
        'required_consecutive_failures': 2,
        'handshake_stale_seconds': 180,
        'cooldown_seconds': 900,
    }}


def results(*, failed=True, transport=False, one_way=False, control=True):
    cenuta = Assessment(
        'failed' if failed else 'partial',
        'tunnel_unreachable' if failed else 'partial_https',
        signals=('independent_control_ok',) if control else (),
        handshake_age=181,
        transport_alive=transport,
        one_way_suspect=one_way,
    )
    fornex = Assessment('healthy', 'ok')
    return {'cenuta': (cenuta, []), 'fornex': (fornex, [])}


def fornex_results(*, failed=True, transport=False, one_way=False, control=True):
    cenuta = Assessment('healthy', 'ok')
    fornex = Assessment(
        'failed' if failed else 'partial',
        'tunnel_unreachable' if failed else 'partial_https',
        signals=('independent_control_ok',) if control else (),
        handshake_age=181,
        transport_alive=transport,
        one_way_suspect=one_way,
    )
    return {'cenuta': (cenuta, []), 'fornex': (fornex, [])}


def test_requires_two_committed_qualifying_cycles_then_switches(tmp_path):
    runner = Runner()
    failover = CenutaFailover(config(), tmp_path, runner=runner, clock=lambda: 2000)
    assert failover.evaluate(results(), 120)['action'] == 'awaiting_confirmation'
    assert runner.mode == 'native'
    assert failover.evaluate(results(), 240)['action'] == 'switched_to_backup'
    assert runner.mode == 'backup'
    assert failover.evaluate(results(), 360)['action'] == 'already_backup'


def test_partial_or_unconfirmed_failure_never_switches(tmp_path):
    runner = Runner()
    failover = CenutaFailover(config(), tmp_path, runner=runner, clock=lambda: 2000)
    assert failover.evaluate(results(failed=False), 120)['action'] == 'criteria_not_met'
    assert failover.evaluate(results(transport=None, one_way=False), 240)['action'] == 'criteria_not_met'
    assert failover.evaluate(results(control=False), 360)['action'] == 'criteria_not_met'
    assert runner.mode == 'native'


def test_one_way_signal_is_an_alternative_transport_confirmation(tmp_path):
    runner = Runner()
    failover = CenutaFailover(config(), tmp_path, runner=runner, clock=lambda: 2000)
    assert failover.evaluate(results(transport=None, one_way=True), 120)['action'] == 'awaiting_confirmation'
    assert failover.evaluate(results(transport=None, one_way=True), 240)['action'] == 'switched_to_backup'


def test_fornex_uses_its_own_controller_and_state(tmp_path):
    controller = '/usr/local/sbin/timeweb-fornex-wg-console-transport'
    runner = Runner(controller)
    failover = FornexFailover(fornex_config(), tmp_path, runner=runner, clock=lambda: 2000)
    assert failover.evaluate(fornex_results(), 120)['action'] == 'awaiting_confirmation'
    assert failover.evaluate(fornex_results(), 240)['action'] == 'switched_to_backup'
    assert runner.mode == 'backup'
    assert failover.path.name == 'fornex-auto-failover.json'
    assert (controller, 'backup') in runner.calls
