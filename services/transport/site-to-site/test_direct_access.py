"""Initial SSH retry must not replay writes or bypass identity failures."""
from pathlib import Path
import socket
import sys

import paramiko
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import direct_access as access


@pytest.mark.parametrize('failure,retry', [
    (socket.timeout('fixture timeout'), True),
    (EOFError('fixture EOF'), True),
    (paramiko.SSHException('fixture negotiation failed'), True),
    (paramiko.AuthenticationException('fixture denied'), False),
    (paramiko.BadHostKeyException('host', object(), object()), False),
    (RuntimeError('router_identity_mismatch'), False),
    (LookupError('fixture missing pinned host'), False),
])
def test_initial_connect_retry_preserves_identity_checks(monkeypatch, failure, retry):
    clients, proxies, attempts = [], [], []
    class Proxy:
        closed = False
        def __init__(self, command):
            proxies.append(self)
        def close(self):
            self.closed = True
    class Client:
        closed = False
        def __init__(self):
            clients.append(self)
        def load_host_keys(self, path):
            pass
        def get_host_keys(self):
            return self
        def lookup(self, host):
            return None if isinstance(failure, LookupError) else True
        def set_missing_host_key_policy(self, policy):
            assert isinstance(policy, paramiko.RejectPolicy)
        def connect(self, host, **kwargs):
            attempts.append(kwargs)
            if len(attempts) == 1 and not isinstance(failure, RuntimeError):
                raise failure
        def get_transport(self):
            return self
        def set_keepalive(self, value):
            pass
        def close(self):
            self.closed = True
    monkeypatch.setattr(access.paramiko, 'SSHClient', Client)
    monkeypatch.setattr(access.paramiko, 'ProxyCommand', Proxy)
    monkeypatch.setattr(access.paramiko.PKey, 'from_path', lambda path: object())
    reads = []
    def run(client, command):
        reads.append(command)
        return b'WRONG' if isinstance(failure, RuntimeError) else access.SERIAL['nakhimova'].encode()
    monkeypatch.setattr(access, 'run', run)
    if retry:
        result = access.connect('nakhimova')
        assert result is clients[-1]
        assert len(attempts) == 2
        assert clients[0].closed and proxies[0].closed
        assert reads == [':put [/system routerboard get serial-number]']
    else:
        with pytest.raises(RuntimeError):
            access.connect('nakhimova')
        assert len(attempts) == (0 if isinstance(failure, LookupError) else 1)
        assert clients[0].closed and proxies[0].closed
    assert all(k['allow_agent'] is False and k['look_for_keys'] is False for k in attempts)


def test_connect_stops_after_two_transport_failures(monkeypatch):
    attempts = []
    def fail(site, interactive=False):
        attempts.append(site)
        raise access.RouterUnavailable(site, 'timeout')
    monkeypatch.setattr(access, '_connect_once', fail, raising=False)
    with pytest.raises(access.RouterUnavailable):
        access.connect('nakhimova')
    assert attempts == ['nakhimova', 'nakhimova']


@pytest.mark.parametrize('failure', ['connection', 'drift', 'identity'])
def test_status_distinguishes_management_failure_from_drift(tmp_path, monkeypatch, failure):
    from controller import write
    import direct_controller as ctl
    write(tmp_path / 'config.json', dict(version=1, certificate_expires=4_000_000_000,
          endpoint='194.61.140.217', baseline={'nakhimova': 'expected'}))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    class Connection:
        def close(self):
            pass
    connections = []
    def connector(site):
        connections.append(site)
        if site == 'nakhimova' and failure == 'connection':
            raise access.RouterUnavailable(site, 'timeout')
        if site == 'nakhimova' and failure == 'identity':
            raise RuntimeError('router_validation_failed:nakhimova')
        return Connection()
    instance = ctl.DirectController(tmp_path, connector=connector)
    monkeypatch.setattr(instance, 'inspect', lambda c: ({}, {}))
    monkeypatch.setattr(access, 'value', lambda *args: True)
    monkeypatch.setattr(access, 'get', lambda c, expression: [{'gateway': 'sstp-direct-in'}] if expression.startswith('[/routing') else '194.61.140.217')
    monkeypatch.setattr(access, 'run', lambda *args: b'unreviewed export')
    status = instance.status()
    assert status['available'] is False and status['can_remove'] is True
    assert status['tunnel']['state'] == 'unknown'
    assert connections == ['fethiye', 'nakhimova']
    expected = {
        'connection': 'Nakhimova management unavailable after connection retry (timeout); selection unchanged',
        'drift': 'Nakhimova configuration requires review',
        'identity': 'Nakhimova management read or identity validation failed; selection unchanged',
    }
    assert status['error'] == expected[failure]


def test_write_failure_never_replays_command(monkeypatch):
    calls = []
    def fail(client, command):
        calls.append(command)
        raise EOFError('fixture write response lost')
    monkeypatch.setattr(access, 'run', fail)
    with pytest.raises(EOFError):
        access.mutate(None, '/fixture enable exact-owned-rule')
    assert calls == ['/fixture enable exact-owned-rule']
