"""One-way automatic native UDP to WSS failover for a monitored upstream.

This module consumes only an already committed, validated monitoring batch. It
never edits routes, firewall rules or WireGuard directly: the reviewed
transport controller owns the atomic endpoint transition and its rollback.
"""
import json
from pathlib import Path
import subprocess
import time

from .runtime import atomic_json


CONTROLLERS = {
    'cenuta': '/usr/local/sbin/timeweb-cenuta-wg-console-transport',
    'fornex': '/usr/local/sbin/timeweb-fornex-wg-console-transport',
}


class UplinkFailover:
    def __init__(self, upstream, config, directory, *, runner=subprocess.run, clock=time.time):
        if upstream not in CONTROLLERS:
            raise ValueError('invalid_failover_upstream')
        raw = config.get(f'{upstream}_auto_failover', {})
        if not isinstance(raw, dict):
            raise ValueError(f'invalid_{upstream}_auto_failover')
        self.upstream = upstream
        self.other_upstream = 'fornex' if upstream == 'cenuta' else 'cenuta'
        self.enabled = raw.get('enabled', False)
        self.required = raw.get('required_consecutive_failures', 2)
        self.handshake_stale = raw.get('handshake_stale_seconds', 180)
        self.cooldown = raw.get('cooldown_seconds', 900)
        self.controller = raw.get('controller', CONTROLLERS[upstream])
        if (type(self.enabled) is not bool or
                type(self.required) is not int or self.required < 2 or
                type(self.handshake_stale) is not int or self.handshake_stale < 180 or
                type(self.cooldown) is not int or self.cooldown < 300 or
                self.controller != CONTROLLERS[upstream]):
            raise ValueError(f'invalid_{upstream}_auto_failover')
        self.path = Path(directory) / f'{upstream}-auto-failover.json'
        self.runner, self.clock = runner, clock

    def _load(self):
        if not self.path.exists():
            return {'version': 1, 'consecutive_failures': 0, 'last_switch_unix': 0}
        try:
            value = json.loads(self.path.read_text())
            if (value.get('version') != 1 or type(value.get('consecutive_failures')) is not int or
                    type(value.get('last_switch_unix')) not in (int, float)):
                raise ValueError()
            return value
        except (OSError, ValueError, json.JSONDecodeError):
            return {'version': 1, 'consecutive_failures': 0, 'last_switch_unix': 0,
                    'last_reason': 'state_reset'}

    def _save(self, value):
        value['version'] = 1
        atomic_json(self.path, value)
        self.path.chmod(0o600)

    def _mode(self):
        try:
            result = self.runner([self.controller, 'status'], text=True, capture_output=True,
                                 timeout=12, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        fields = dict(item.split('=', 1) for item in result.stdout.strip().split() if '=' in item)
        mode, endpoint = fields.get('mode'), fields.get('endpoint')
        if mode not in ('native', 'backup') or not endpoint:
            return None
        return mode

    def _qualifies(self, results):
        try:
            current, independent = results[self.upstream][0], results[self.other_upstream][0]
        except (KeyError, IndexError, TypeError):
            return False
        return (
            current.kind == 'failed' and
            current.handshake_age is not None and current.handshake_age > self.handshake_stale and
            (current.transport_alive is False or current.one_way_suspect is True) and
            'independent_control_ok' in current.signals and
            independent.kind == 'healthy'
        )

    def evaluate(self, results, slot):
        """Return a bounded event dictionary; never raise into the collector."""
        if not self.enabled:
            return {'action': 'disabled'}
        state = self._load()
        now = self.clock()
        mode = self._mode()
        if mode != 'native':
            state.update(consecutive_failures=0, last_slot=slot,
                         last_reason='already_backup' if mode == 'backup' else 'mode_unavailable')
            self._save(state)
            return {'action': state['last_reason']}
        if not self._qualifies(results):
            state.update(consecutive_failures=0, last_slot=slot, last_reason='criteria_not_met')
            self._save(state)
            return {'action': 'criteria_not_met'}
        failures = state.get('consecutive_failures', 0) + 1
        state.update(consecutive_failures=failures, last_slot=slot, last_reason='qualified_failure')
        if failures < self.required:
            self._save(state)
            return {'action': 'awaiting_confirmation', 'failures': failures}
        if now - state.get('last_switch_unix', 0) < self.cooldown:
            state['last_reason'] = 'cooldown'
            self._save(state)
            return {'action': 'cooldown'}
        try:
            result = self.runner([self.controller, 'backup'], text=True, capture_output=True,
                                 timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            result = None
        if result is None or result.returncode != 0 or self._mode() != 'backup':
            state['last_reason'] = 'backup_failed'
            self._save(state)
            return {'action': 'backup_failed'}
        state.update(consecutive_failures=0, last_switch_unix=now, last_reason='switched_to_backup')
        self._save(state)
        return {'action': 'switched_to_backup'}


class CenutaFailover(UplinkFailover):
    def __init__(self, config, directory, **kwargs):
        super().__init__('cenuta', config, directory, **kwargs)


class FornexFailover(UplinkFailover):
    def __init__(self, config, directory, **kwargs):
        super().__init__('fornex', config, directory, **kwargs)
