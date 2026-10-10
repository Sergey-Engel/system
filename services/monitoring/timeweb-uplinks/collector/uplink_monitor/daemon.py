"""Local daemon candidate, fail closed; never install or reapply routing guards."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import time
import uuid

from .adapter import BatchAdapter
from .collector import POLICIES, ingest_batch
from .failover import CenutaFailover, FornexFailover
from .model import Assessment
from .runtime import atomic_json, digest, read_json, private_file
from .scheduler import Scheduler
from .storage import Store, UPSTREAMS
from .targets import Targets, Refused, dns_resolver
from .timing import DEFAULT_TIMING


class Daemon:
    def __init__(self, directory, config, adapter, *, resolver=dns_resolver,
                 clock=time.time, monotonic=time.monotonic, boot=None):
        self.directory = Path(directory)
        if 'Dropbox' in self.directory.resolve().parts:
            raise ValueError('live_database_in_sync_directory_forbidden')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.directory/'daemon.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close()
            raise
        self.health = self.directory/'health.json'
        self.config = Path(config)
        self.retention_days = read_json(self.config).get('retention_days', 7)
        if type(self.retention_days) is not int or not 1 <= self.retention_days <= 30:
            self.lock.close()
            raise ValueError('invalid_retention_days')
        self.revision = digest(config)
        self.clock, self.monotonic, self.adapter, self.resolver = clock, monotonic, adapter, resolver
        self.run = str(uuid.uuid4())
        self.boot = boot or (Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                             if Path('/proc/sys/kernel/random/boot_id').exists() else 'local-test')
        self.cache = Targets(self.directory/'targets.json', POLICIES)
        failover_config = read_json(self.config)
        self.failovers = (
            CenutaFailover(failover_config, self.directory),
            FornexFailover(failover_config, self.directory),
        )
        self.errors = 0
        self.stopped = False
        try:
            self.store = Store(self.directory/'history.sqlite')
            self.previous = self.store.epoch()
            if self.previous:
                self.errors = int(self.previous.get('errors', 0))
            self.status(True, 'starting')
        except (OSError, ValueError, sqlite3.Error):
            self.status(False, 'storage_start_failed')
            self.close()
            raise

    def close(self):
        self.lock.close()

    def status(self, storage, reason, *, committed=None):
        # This channel is independent of SQLite; filesystem failure also reaches stderr.
        try:
            atomic_json(self.health, dict(updated=self.clock(), storage_ok=storage,
                reason=reason, run=self.run, committed=committed))
        except OSError:
            print('MONITOR_HEALTH_WRITE_FAILED', flush=True)

    def cycle(self, slot):
        started, mono = self.clock(), self.monotonic()
        targets, payload, generation, reason = {}, {}, 'unknown', 'ok'
        epoch = dict(wall=started, mono=mono, slot=slot, boot=self.boot,
                     config=self.revision, run=self.run)
        if self.previous:
            for key in ('guard', 'cache', 'cache_sha256'):
                if key in self.previous:
                    epoch[key] = self.previous[key]
        try:
            if not all(math.isfinite(t) for t in (started, mono, slot)):
                raise Refused('invalid_clock')
            previous = self.previous
            if previous and (started < previous['wall'] or slot <= previous['slot']):
                raise Refused('clock_regression')
            if previous and previous['boot']==self.boot and abs(
                    (started-previous['wall'])-(mono-previous['mono']))>2:
                raise Refused('clock_discontinuity')
            if digest(self.config) != self.revision:
                raise Refused('config_changed_restart_required')
            if started-slot > 2:
                raise Refused('late_cycle_start')
            try:
                targets = self.cache.get(started)
            except Refused:
                targets = None
            # DNS TTL admits a target snapshot to the batch start; it is not a
            # second batch deadline.  The helper copies this snapshot and is
            # independently bounded below.  A later slot must resolve again.
            if targets is None:
                try:
                    self.cache.refresh(self.resolver, started)
                except Exception as exc:
                    raise Refused('dns_refresh_failed') from exc
                try:
                    targets = self.cache.get(self.clock())
                except Refused as exc:
                    raise Refused('dns_refresh_expired') from exc
            cache_hash = digest(self.cache.path)
            if previous and targets['generation'] < previous.get('cache', 0):
                raise Refused('cache_generation_regression')
            if previous and targets['generation'] == previous.get('cache') and cache_hash != previous.get('cache_sha256'):
                raise Refused('cache_same_revision_changed')
            remaining = slot + DEFAULT_TIMING.deadline - self.clock() - 0.5
            if remaining < 1:
                raise Refused('dns_consumed_cycle_deadline')
            payload = self.adapter(targets, remaining)
            generation = payload['generation']
            end_wall, end_mono = self.clock(), self.monotonic()
            if abs((end_wall-started)-(end_mono-mono)) > 2 or end_mono < mono:
                raise Refused('clock_changed_during_probe')
            if digest(self.cache.path) != cache_hash:
                raise Refused('cache_revision_changed')
            if digest(self.config) != self.revision:
                raise Refused('config_changed_during_probe')
            if end_wall > slot+DEFAULT_TIMING.deadline or payload['finished_unix']>end_wall:
                raise Refused('cycle_deadline')
            epoch.update(guard=str(generation), cache=targets['generation'], cache_sha256=cache_hash,
                         errors=0, retry_after_mono=0)
            # Mono is normalized to the slot so varying probe duration is not a clock jump.
            results = ingest_batch(self.store, payload, targets, generation, slot, run=self.run,
                mono=mono-(started-slot), revision=self.revision, metadata=epoch)
            for failover in self.failovers:
                event = failover.evaluate(results, slot)
                print(json.dumps(dict(event=f'{failover.upstream}_failover', slot=slot, **event)),
                      flush=True)
            self.errors = 0
        except (Refused, ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
            if isinstance(exc, sqlite3.Error) or isinstance(exc, OSError):
                self.status(False, 'storage_or_runtime_io_failed')
                return 'storage_or_runtime_io_failed'
            reason = str(exc) if isinstance(exc, Refused) else 'adapter_invalid'
            self.errors += 1
            epoch['last_error'] = reason
            print(json.dumps(dict(event='cycle_refused', reason=reason,
                error_type=type(exc).__name__, slot=slot)), flush=True)
            # Record the failure, but preserve the fixed collection cadence.
            epoch.update(errors=self.errors, retry_after_mono=0)
            # Do not overwrite future history after backward clock movement.
            if self.previous and slot <= self.previous['slot']:
                self.status(True, reason)
                return reason
            try:
                self.store.batch({up:dict(slot=slot, run=self.run, generation=str(generation),
                    revision=self.revision, assessment=Assessment('unknown', reason),
                    mono=mono-(started-slot), observed=slot) for up in UPSTREAMS}, metadata=epoch)
            except (ValueError, OSError, sqlite3.Error):
                self.status(False, 'storage_commit_failed')
                return 'storage_commit_failed'
        self.previous = epoch
        self.status(True, reason, committed=slot)
        return reason

    def serve(self):
        scheduler = Scheduler(self.monotonic(), self.clock())
        while not self.stopped:
            due = scheduler.due(self.monotonic(), self.clock())
            if due is not None:
                self.cycle(due['slot'])
                try:
                    self.store.prune(self.clock(), retention=self.retention_days * 86400)
                except (OSError, sqlite3.Error):
                    self.status(False, 'retention_failed')
            time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description='Local uplink daemon candidate, no installation.')
    parser.add_argument('--config', required=True)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--pilot', action='store_true', help='Explicit limited-scope observational pilot.')
    args = parser.parse_args()
    os.umask(0o077)
    config = read_json(private_file(args.config))
    if config.get('version') != 1:
        parser.error('Unsupported configuration version.')
    if not config.get('allow_snapshot_scope', False):
        parser.error('Production gate closed: universal WG/firewall generation coverage not accepted.')
    if not args.pilot or config.get('deployment_mode') != 'pilot':
        parser.error('Only an explicit pilot is allowed; production acceptance is still closed.')
    adapter = BatchAdapter(config, args.state_dir)
    daemon = Daemon(args.state_dir, args.config, adapter)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: setattr(daemon, 'stopped', True))
    try:
        daemon.serve()
    finally:
        daemon.close()


if __name__ == '__main__':
    main()
