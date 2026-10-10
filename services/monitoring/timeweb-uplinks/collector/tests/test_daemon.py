import copy
import json
import sqlite3
import pytest

from uplink_monitor.daemon import Daemon
from uplink_monitor.runtime import read_json
from uplink_monitor.storage import current
from uplink_monitor.targets import dns_resolver
from uplink_monitor.targets import Refused
from test_collector import sample


class Clock:
    now = 120.
    mono = 1000.
    def wall(self): return self.now
    def monotonic(self): return self.mono
    def advance(self, seconds=120): self.now += seconds; self.mono += seconds


def test_failed_measurement_is_retried_on_next_slot(tmp_path):
    daemon, clock = build(tmp_path)
    good = daemon.adapter
    calls = []
    def failing(targets, budget):
        calls.append(clock.now)
        raise Refused('test_failure')
    daemon.adapter = failing
    try:
        assert daemon.cycle(120) == 'test_failure'
        clock.advance()
        assert daemon.cycle(240) == 'test_failure'
        clock.advance()
        assert daemon.cycle(360) == 'test_failure'
        assert daemon.errors == 3
        assert calls == [120, 240, 360]
        daemon.adapter = good
        clock.advance()
        assert daemon.cycle(480) == 'ok'
        assert daemon.errors == 0
    finally:
        daemon.close()


def build(tmp_path, *, adapter=None, resolver=None):
    clock = Clock()
    config = tmp_path/'config.json'
    config.write_text('{}')
    def good(targets, budget):
        value, _ = sample(clock.now)
        clock.now += 1; clock.mono += 1
        return value
    daemon = Daemon(tmp_path/'state', config, adapter or good,
        resolver=resolver or (lambda host: (['1.1.1.1'], 300)),
        clock=clock.wall, monotonic=clock.monotonic, boot='test-boot')
    return daemon, clock


def test_daemon_cycle_commits_both_and_persistent_epoch(tmp_path):
    daemon, clock = build(tmp_path)
    assert daemon.retention_days == 7
    try:
        assert daemon.cycle(120)=='ok'
        assert all(row['state']=='UP' for row in current(daemon.store.path, 121).values())
        assert daemon.store.epoch()['guard']=='5'
        assert read_json(daemon.health)['storage_ok']
        with pytest.raises(BlockingIOError):
            Daemon(daemon.directory, daemon.config, daemon.adapter)
    finally:
        daemon.close()


def test_short_ttl_does_not_shorten_started_batch_budget(tmp_path):
    daemon, clock = build(tmp_path, resolver=lambda _: (['1.1.1.1'], 5))
    good = daemon.adapter
    budgets = []
    def checked(targets, budget):
        budgets.append(budget)
        return good(targets, budget)
    daemon.adapter = checked
    try:
        assert daemon.cycle(120) == 'ok'
        assert budgets == [44.5]
    finally:
        daemon.close()


def test_valid_short_ttl_snapshot_starts_without_refresh(tmp_path):
    daemon, clock = build(tmp_path, resolver=lambda _: (['1.1.1.1'], 5))
    try:
        # An answer that is valid at the scheduled start may begin this batch,
        # even though it cannot cover the entire 43-second helper deadline.
        daemon.cache.refresh(daemon.resolver, 119.5)
        daemon.resolver = lambda _: (_ for _ in ()).throw(TimeoutError())
        assert daemon.cycle(120) == 'ok'
    finally:
        daemon.close()


def test_short_ttl_batch_may_finish_after_expiry(tmp_path):
    daemon, clock = build(tmp_path, resolver=lambda _: (['1.1.1.1'], 1))
    def completes_after_ttl(targets, budget):
        value, _ = sample(clock.now)
        value['finished_unix'] = clock.now + 6
        clock.now += 6
        clock.mono += 6
        return value
    daemon.adapter = completes_after_ttl
    try:
        assert daemon.cycle(120) == 'ok'
        assert all(row['state'] == 'UP' for row in current(daemon.store.path, 126).values())
    finally:
        daemon.close()


def test_restart_preserves_error_count_without_suppressing_measurement(tmp_path):
    daemon, clock = build(tmp_path)
    daemon.adapter = lambda *_: (_ for _ in ()).throw(Refused('batch_failed'))
    daemon.cycle(120)
    clock.advance()
    daemon.cycle(240)
    daemon.close()
    resumed = Daemon(daemon.directory, daemon.config, daemon.adapter,
        clock=clock.wall, monotonic=clock.monotonic, boot='test-boot')
    try:
        clock.advance()
        assert resumed.cycle(360) == 'batch_failed'
        assert resumed.store.epoch()['last_error'] == 'batch_failed'
    finally:
        resumed.close()


def test_dns_error_does_not_extend_snapshot(tmp_path):
    daemon, clock = build(tmp_path)
    try:
        daemon.cycle(120)
        original = daemon.cache.path.read_bytes()
        clock.now, clock.mono = 480., 1360.
        daemon.resolver = lambda _: (_ for _ in ()).throw(TimeoutError())
        assert daemon.cycle(480)=='dns_refresh_failed'
        assert daemon.cache.path.read_bytes()==original
        assert all(v['state']=='UNKNOWN' for v in current(daemon.store.path, 480).values())
    finally:
        daemon.close()


def test_cache_aba_revision_and_config_change_discard_whole_cycle(tmp_path):
    daemon, clock = build(tmp_path)
    good = daemon.adapter
    def changed(targets, budget):
        payload = good(targets, budget)
        data = read_json(daemon.cache.path)
        data['generation'] += 1
        daemon.cache.path.write_text(json.dumps(data))
        return payload
    daemon.adapter = changed
    try:
        assert daemon.cycle(120)=='cache_revision_changed'
        assert all(v['state']=='UNKNOWN' for v in current(daemon.store.path, 121).values())
    finally:
        daemon.close()


def test_restart_backward_clock_keeps_history_and_blocks_probe(tmp_path):
    daemon, clock = build(tmp_path)
    daemon.cycle(120)
    daemon.close()
    clock.now, clock.mono = 0., 1001.
    resumed = Daemon(daemon.directory, daemon.config,
        lambda *_: pytest.fail('must not probe'), clock=clock.wall,
        monotonic=clock.monotonic, boot='test-boot')
    try:
        assert resumed.cycle(0)=='clock_regression'
        assert resumed.store.epoch()['slot']==120
    finally:
        resumed.close()


def test_storage_full_health_is_separate_from_history(tmp_path, monkeypatch):
    daemon, clock = build(tmp_path)
    def full(*_, **__): raise sqlite3.OperationalError('database or disk is full')
    monkeypatch.setattr(daemon.store, 'batch', full)
    try:
        assert daemon.cycle(120)=='storage_or_runtime_io_failed'
        assert read_json(daemon.health)['storage_ok'] is False
        assert daemon.store.epoch() is None
    finally:
        daemon.close()


def test_real_dnspython_api_uses_answer_expiration(monkeypatch):
    import dns.resolver
    import time
    class A:
        expiration = time.time()+17
        def __iter__(self):
            return iter([type('Record', (), {'address':'1.1.1.1'})()])
    def resolve(host, rdtype, **kwargs):
        assert rdtype=='A' and kwargs==dict(lifetime=2., search=False)
        return A()
    monkeypatch.setattr(dns.resolver, 'resolve', resolve)
    ips, ttl = dns_resolver('test.example')
    assert ips==['1.1.1.1'] and 0 < ttl <= 17


def test_daemon_loop_runs_slots_and_stops_without_catchup(tmp_path, monkeypatch):
    import uplink_monitor.daemon as module
    daemon, clock = build(tmp_path)
    good = daemon.adapter
    slots = []
    def capture(targets,budget):
        slots.append(int(clock.now))
        value = good(targets,budget)
        if len(slots)==2: daemon.stopped=True
        return value
    daemon.adapter = capture
    def sleep(_):
        clock.now, clock.mono = 240.,1120.
    monkeypatch.setattr(module.time, 'sleep', sleep)
    try:
        daemon.serve()
        assert slots==[120,240]
        assert daemon.store.epoch()['slot']==240
    finally:
        daemon.close()


def test_config_change_after_start_does_not_run_adapter(tmp_path):
    daemon, clock = build(tmp_path, adapter=lambda *_:pytest.fail('must not run'))
    daemon.config.write_text('{"changed":true}')
    try:
        assert daemon.cycle(120)=='config_changed_restart_required'
        assert all(v['state']=='UNKNOWN' for v in current(daemon.store.path,120).values())
    finally:
        daemon.close()


def test_backward_clock_during_batch_is_unknown(tmp_path):
    daemon, clock = build(tmp_path)
    good = daemon.adapter
    def backwards(targets,budget):
        value=good(targets,budget)
        clock.now-=10
        return value
    daemon.adapter=backwards
    try:
        assert daemon.cycle(120)=='clock_changed_during_probe'
        assert daemon.store.epoch()['errors']==1
    finally:
        daemon.close()
