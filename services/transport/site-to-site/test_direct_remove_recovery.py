"""Failed removal must expose durable pending intent, not transient memory."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import direct_controller as ctl
import sstp_direct as policy
from controller import write

KEY, IP = 'A2:C1:5E:29:F5:8E', '192.168.89.197'


@pytest.mark.parametrize('expired', [False, True])
def test_remove_cleanup_failure_uses_saved_pending_state(tmp_path, monkeypatch, expired):
    lease = dict(mac=KEY, ip=IP, label='MacBookAir', lease='*D', online=True)
    write(tmp_path / 'config.json', dict(version=1))
    write(tmp_path / 'state.json', dict(version=1, generation=0,
          clients={KEY: dict(lease, selected=True, pending=False, prepared=True)}))
    original = ctl.DirectController
    commands, flags = [], {s['comment']: False for s in policy.client_policy(KEY, IP)}
    class Connection:
        def close(self):
            pass
    def factory(directory):
        instance = original(directory, connector=lambda site: Connection())
        def status():
            saved = instance.state['clients'][KEY]
            return dict(available=not saved['pending'], can_remove=True, error=None, revision='a' * 64,
                devices=[dict(id=KEY, selected=saved['selected'], status='pending' if saved['pending'] else 'remote' if saved['selected'] else 'local',
                              revision=instance.device_revision(KEY, lease))])
        instance.status = status
        instance.inspect = lambda c: ({KEY: lease}, dict(flags))
        return instance
    monkeypatch.setattr(ctl, 'DirectController', factory)
    def mutate(c, command):
        commands.append(command)
        if command.startswith('/ip firewall connection remove '):
            raise RuntimeError('router_command_failed')
        spec = next(s for s in policy.client_policy(KEY, IP) if s['comment'] in command)
        assert ' disable ' in command
        flags[spec['comment']] = True
    monkeypatch.setattr(ctl.access, 'mutate', mutate)
    reads = []
    def rows(*args):
        reads.append(True)
        return [] if expired and len(reads) > 1 else [dict(**{'.id': '*10', 'src-address': IP + ':443'})]
    monkeypatch.setattr(ctl.access, 'rows', rows)
    result = ctl.execute('remove', KEY, 'a' * 64, tmp_path)
    saved = json.loads((tmp_path / 'state.json').read_text())['clients'][KEY]
    assert sum(c.startswith('/ip firewall connection remove ') for c in commands) == 1
    assert len(commands) == len(flags) + 1 and all(flags.values())
    if expired:
        assert result['success'] is True
        assert saved['selected'] is False and saved['pending'] is False
        assert result['devices'][0]['status'] == 'local'
    else:
        assert result['success'] is False
        assert saved['selected'] is True and saved['pending'] is True
        assert result['devices'][0]['selected'] is True
        assert result['devices'][0]['status'] == 'pending'
        assert json.loads((tmp_path / 'last-error.json').read_text())['phase'] == 'connection_cleanup'


@pytest.mark.parametrize('read_fails', [False, True])
def test_cleanup_never_replays_or_removes_neighbor_flows(monkeypatch, read_fails):
    owned = {'.id': '*10', 'src-address': IP + ':443'}
    neighbor = {'.id': '*20', 'src-address': '192.168.89.198:443'}
    reads, writes = [], []
    def rows(*args):
        reads.append(True)
        if len(reads) > 1 and read_fails:
            raise OSError('fixture read unavailable')
        # The failed ID still exists, even if it no longer belongs to this IP.
        return [owned, neighbor] if len(reads) == 1 else [dict(neighbor, **{'.id': '*10'})]
    def mutate(c, command):
        writes.append(command)
        raise RuntimeError('router_command_failed')
    monkeypatch.setattr(ctl.access, 'rows', rows)
    monkeypatch.setattr(ctl.access, 'mutate', mutate)
    with pytest.raises((RuntimeError, OSError)):
        ctl.clear_device_connections(None, IP)
    assert writes == ['/ip firewall connection remove *10']
