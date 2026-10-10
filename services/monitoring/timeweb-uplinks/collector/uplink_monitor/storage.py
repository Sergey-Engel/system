"""Atomic state/incident journal. No network access and no raw command output."""
from dataclasses import asdict
from contextlib import contextmanager, nullcontext
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid

from .model import Assessment
from .state import Machine
from .timing import DEFAULT_TIMING, LEGACY_TIMING, Timing

UPSTREAMS = ('cenuta', 'fornex')


@contextmanager
def connect(path, readonly=False):
    path = Path(path).resolve()
    db = sqlite3.connect(path.as_uri() + '?mode=ro' if readonly else str(path),
                         uri=readonly, timeout=0.1)
    db.row_factory = sqlite3.Row
    try:
        if readonly:
            db.execute('PRAGMA query_only=ON')
            deadline = time.monotonic() + 0.7
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        with db:
            yield db
    finally:
        db.close()


def read_timing(db):
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version == 1:
        return LEGACY_TIMING
    if version != 2:
        raise ValueError('unsupported_schema_version')
    row = db.execute('SELECT value FROM settings WHERE name=?', ('timing',)).fetchone()
    if row is None:
        raise ValueError('missing_timing')
    return Timing(**json.loads(row[0]))


class Store:
    def __init__(self, path, *, timing=DEFAULT_TIMING):
        self.timing = timing
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with connect(path) as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            had_daily = db.execute("SELECT 1 FROM sqlite_master WHERE name='daily'").fetchone()
            if version == 1:
                raise ValueError('legacy_database_read_only_use_new_database')
            if version not in (0, 2):
                raise ValueError('unsupported_schema_version')
            if version == 2 and read_timing(db) != timing:
                raise ValueError('database_timing_mismatch_use_new_database')
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS channels (
                  upstream TEXT PRIMARY KEY, slot REAL, observed REAL, mono REAL,
                  run TEXT, generation TEXT, revision TEXT, machine TEXT, assessment TEXT);
                CREATE TABLE IF NOT EXISTS cycles (
                  upstream TEXT, slot REAL, run TEXT, generation TEXT, revision TEXT,
                  observed REAL, valid INTEGER, available INTEGER, failed INTEGER,
                  state TEXT, reason TEXT, probes TEXT, PRIMARY KEY(upstream, slot));
                CREATE TABLE IF NOT EXISTS incidents (
                  upstream TEXT, started REAL, confirmed INTEGER, confirmed_at REAL,
                  ended REAL, boundary TEXT, reason TEXT, PRIMARY KEY(upstream, started));
                CREATE TABLE IF NOT EXISTS gaps (
                  upstream TEXT, started REAL, ended REAL, reason TEXT);
                CREATE INDEX IF NOT EXISTS incidents_time ON incidents(upstream, started, ended);
                CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS daily (
                  upstream TEXT, day INTEGER, samples INTEGER, valid INTEGER,
                  available INTEGER, failed INTEGER, PRIMARY KEY(upstream, day));
                PRAGMA user_version=2;
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',
                       ('timing', json.dumps(asdict(timing))))
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('database_id', str(uuid.uuid4())))
            if not had_daily:
                db.execute('''INSERT INTO daily SELECT upstream,CAST(slot/86400 AS INTEGER)*86400,
                    count(*),sum(valid),sum(coalesce(available,0)*valid),sum(failed*valid)
                    FROM cycles GROUP BY upstream,CAST(slot/86400 AS INTEGER)''')
        self.path.chmod(0o600)

    def ingest(self, upstream, slot, run, generation, assessment, *, mono,
               observed=None, revision='v1', probes=(), _db=None):
        observed = slot if observed is None else observed
        if upstream not in UPSTREAMS or not all(math.isfinite(t) for t in (slot, mono, observed)):
            raise ValueError('invalid_cycle_identity')
        interval = self.timing.interval
        if slot < 0 or slot % interval or not run or not generation or not revision:
            raise ValueError('invalid_cycle_identity')
        if observed < slot or observed > slot + self.timing.deadline:
            assessment = Assessment('unknown', 'cycle_deadline')
        encoded = json.dumps([asdict(p) for p in probes])
        if len(encoded) > 16384:
            raise ValueError('probe_record_limit')
        with (connect(self.path) if _db is None else nullcontext(_db)) as db:
            if _db is None:
                db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM channels WHERE upstream=?', (upstream,)).fetchone()
            existing = db.execute('SELECT run,generation,revision FROM cycles WHERE upstream=? AND slot=?',
                                  (upstream, slot)).fetchone()
            if existing:
                if tuple(existing) != (run, generation, revision):
                    raise ValueError('conflicting_cycle_identity')
                return False
            if old and slot <= old['slot']:
                raise ValueError('out_of_order_or_clock_regression')
            machine = Machine(**json.loads(old['machine'])) if old else Machine()
            events = []
            if old:
                gap = None
                if (run, generation, revision) != (old['run'], old['generation'], old['revision']):
                    gap = 'generation_or_run_changed'
                elif abs((slot - old['slot']) - (mono - old['mono'])) > 2:
                    gap = 'clock_discontinuity'
                elif slot > old['slot'] + interval:
                    gap = 'observation_gap'
                if gap:
                    events += machine.step(Assessment('unknown', gap), old['slot'] + interval)
                    db.execute('INSERT INTO gaps VALUES (?,?,?,?)',
                               (upstream, old['slot'] + interval, slot, gap))
            events += machine.step(assessment, slot)
            for event in events:
                if event['type'] == 'opened':
                    db.execute('INSERT INTO incidents VALUES (?,?,?,?,?,?,?)',
                               (upstream, event['started'], 0, None, None, 'open', event['reason']))
                elif event['type'] == 'confirmed':
                    db.execute('UPDATE incidents SET confirmed=1, confirmed_at=? WHERE upstream=? AND started=?',
                               (event['confirmed_at'], upstream, event['started']))
                else:
                    db.execute('UPDATE incidents SET ended=?,boundary=? WHERE upstream=? AND started=?',
                               (event['ended'], event['type'], upstream, event['started']))
            db.execute('INSERT INTO cycles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (upstream, slot, run, generation, revision, observed,
                        int(assessment.kind != 'unknown'), assessment.available,
                        int(assessment.kind == 'failed'), machine.state,
                        assessment.reason, encoded))
            db.execute('''INSERT OR REPLACE INTO channels
                (upstream,slot,observed,mono,run,generation,revision,machine,assessment)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                       (upstream, slot, observed, mono, run, generation, revision,
                        json.dumps(asdict(machine)), json.dumps(asdict(assessment))))
            day = int(slot//86400)*86400
            db.execute('''INSERT INTO daily VALUES (?,?,?,?,?,?)
                ON CONFLICT(upstream,day) DO UPDATE SET
                samples=samples+1,valid=valid+excluded.valid,
                available=available+excluded.available,failed=failed+excluded.failed''',
                (upstream, day, 1, int(assessment.kind != 'unknown'),
                 int(bool(assessment.available) and assessment.kind != 'unknown'),
                 int(assessment.kind == 'failed')))
        return True

    def batch(self, records, *, metadata=None):
        """Commit both upstreams and the persistent daemon epoch, or none."""
        if set(records) != set(UPSTREAMS):
            raise ValueError('complete_batch_required')
        identities = {(r['slot'], r['run'], r['generation'], r['revision']) for r in records.values()}
        if len(identities) != 1:
            raise ValueError('mixed_batch_identity')
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            changed = [self.ingest(up, **records[up], _db=db) for up in UPSTREAMS]
            if len(set(changed)) != 1:
                raise ValueError('partial_existing_batch')
            if metadata is not None:
                encoded = json.dumps(metadata, allow_nan=False, sort_keys=True)
                if len(encoded) > 8192:
                    raise ValueError('metadata_limit')
                db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', ('daemon_epoch', encoded))
            return all(changed)

    def epoch(self):
        with connect(self.path, readonly=True) as db:
            row = db.execute('SELECT value FROM settings WHERE name=?', ('daemon_epoch',)).fetchone()
            return json.loads(row[0]) if row else None

    def prune(self, now, retention=7 * 86400):
        if retention < 86400:
            raise ValueError('retention_too_short')
        cutoff = now - retention
        with connect(self.path) as db:
            db.execute('DELETE FROM cycles WHERE slot+?<=?', (self.timing.interval, cutoff))
            db.execute('DELETE FROM incidents WHERE ended IS NOT NULL AND ended<=?', (cutoff,))
            db.execute('DELETE FROM gaps WHERE ended<=?', (cutoff,))
            db.execute('DELETE FROM daily WHERE day+86400<=?', (cutoff,))
            day = int(cutoff//86400)*86400
            db.execute('DELETE FROM daily WHERE day=?', (day,))
            db.execute('''INSERT INTO daily SELECT upstream,?,count(*),sum(valid),
                sum(coalesce(available,0)*valid),sum(failed*valid) FROM cycles
                WHERE slot>=? AND slot<? GROUP BY upstream''', (day, day, day+86400))


def current(path, now):
    with connect(path, readonly=True) as db:
        timing = read_timing(db)
        rows = {r['upstream']: r for r in db.execute('SELECT * FROM channels')}
        probes = {}
        for up, row in rows.items():
            latest = db.execute('SELECT probes FROM cycles WHERE upstream=? AND slot=?',
                                (up, row['slot'])).fetchone()
            probes[up] = json.loads(latest[0]) if latest else []
    result = {}
    for up in UPSTREAMS:
        row = rows.get(up)
        if row is None:
            result[up] = dict(state='UNKNOWN', reason='no_data', fresh=False, outages=0, observed=0)
            continue
        machine, assessment = json.loads(row['machine']), json.loads(row['assessment'])
        age = now - row['observed']
        fresh = 0 <= age <= timing.stale_after
        result[up] = dict(state=machine['state'] if fresh else 'UNKNOWN',
                         reason=assessment['reason'] if fresh else 'monitor_stale',
                         fresh=fresh, outages=machine['outages'], observed=row['observed'],
                         assessment=assessment, generation=row['generation'], probes=probes[up],
                         interval_seconds=timing.interval, stale_after_seconds=timing.stale_after)
    return result


def report(path, upstream, start, end):
    if upstream not in UPSTREAMS or not all(math.isfinite(t) for t in (start, end)):
        raise ValueError('invalid_range')
    if start < 0 or not 0 < end - start <= 30 * 86400:
        raise ValueError('invalid_range')
    with connect(path, readonly=True) as db:
        interval = read_timing(db).interval
        has_daily = db.execute("SELECT 1 FROM sqlite_master WHERE name='daily'").fetchone()
        full_start = math.ceil(start/86400)*86400
        full_end = math.floor(end/86400)*86400
        if not has_daily or full_start >= full_end:
            full_start = full_end = 0
        row = db.execute('''SELECT
            coalesce(sum(min(slot+?,?)-max(slot,?)),0) AS observed,
            coalesce(sum((min(slot+?,?)-max(slot,?))*valid),0) AS valid,
            coalesce(sum((min(slot+?,?)-max(slot,?))*coalesce(available,0)*valid),0) AS available,
            coalesce(sum((min(slot+?,?)-max(slot,?))*failed*valid),0) AS failed
            FROM cycles WHERE upstream=? AND slot<? AND slot+?>?
            AND (slot<? OR slot>=?)''',
            (interval, end, start, interval, end, start, interval, end, start,
             interval, end, start, upstream, end, interval, start, full_start, full_end)).fetchone()
        row = dict(row)
        if full_end > full_start:
            daily = db.execute('''SELECT coalesce(sum(samples),0),coalesce(sum(valid),0),
                coalesce(sum(available),0),coalesce(sum(failed),0) FROM daily
                WHERE upstream=? AND day>=? AND day<?''', (upstream, full_start, full_end)).fetchone()
            for key, count in zip(('observed','valid','available','failed'), daily):
                row[key] += count*interval
        episodes = db.execute('''SELECT count(*) FROM incidents
            WHERE upstream=? AND confirmed=1 AND started>=? AND started<?''',
            (upstream, start, end)).fetchone()[0]
    return dict(upstream=upstream, start=start, end=end, valid_seconds=row['valid'],
                unknown_seconds=end-start-row['valid'], failed_seconds=row['failed'],
                available_seconds=row['available'], coverage=row['valid']/(end-start),
                availability=row['available']/row['valid'] if row['valid'] else None,
                outage_segments_started=episodes, resolution_seconds=interval)


def incidents(path, upstream, start, end, offset=0):
    if upstream not in UPSTREAMS or not 0 < end-start <= 30*86400 or start < 0 or not 0 <= offset <= 100000:
        raise ValueError('invalid_range')
    with connect(path, readonly=True) as db:
        interval = read_timing(db).interval
        last = db.execute('SELECT slot FROM channels WHERE upstream=?', (upstream,)).fetchone()
        stop = min(end, last[0]+interval) if last else start
        rows = db.execute('''SELECT * FROM incidents WHERE upstream=?
            AND started<? AND coalesce(ended,?)>? ORDER BY started LIMIT 1001 OFFSET ?''',
            (upstream, end, stop, start, offset)).fetchall()
        windows = {}
        for row in rows[:1000]:
            previous_good = db.execute('''SELECT observed FROM cycles
                WHERE upstream=? AND slot<? AND available=1 AND valid=1
                ORDER BY slot DESC LIMIT 1''', (upstream, row['started'])).fetchone()
            first_failed = db.execute('SELECT observed FROM cycles WHERE upstream=? AND slot=?',
                                      (upstream, row['started'])).fetchone()
            recovery = None
            if row['boundary'] == 'closed':
                last_failed = db.execute('''SELECT observed FROM cycles WHERE upstream=?
                    AND slot>=? AND slot<? AND failed=1 AND valid=1 ORDER BY slot DESC LIMIT 1''',
                    (upstream, row['started'], row['ended'])).fetchone()
                first_good = db.execute('SELECT observed FROM cycles WHERE upstream=? AND slot=?',
                                        (upstream, row['ended'])).fetchone()
                recovery = [last_failed[0] if last_failed else None, first_good[0] if first_good else None]
            windows[row['started']] = ([previous_good[0] if previous_good else None,
                                       first_failed[0] if first_failed else None], recovery)
    items = []
    for row in rows[:1000]:
        item = dict(row)
        item['start_window'], item['recovery_window'] = windows[row['started']]
        item['end_is_censored'] = row['boundary'] != 'closed'
        items.append(item)
    return dict(items=items,
                next_offset=offset+1000 if len(rows)>1000 else None)
