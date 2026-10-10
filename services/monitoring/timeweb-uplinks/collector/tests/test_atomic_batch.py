import sqlite3
import pytest
from uplink_monitor.storage import Store, connect, current
from uplink_monitor.collector import ingest_batch
from uplink_monitor.timing import LEGACY_TIMING
from test_collector import sample


def test_second_channel_failure_rolls_back_everything(tmp_path):
    store = Store(tmp_path/'db', timing=LEGACY_TIMING)
    with connect(store.path) as db:
        db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON cycles WHEN NEW.upstream='fornex' BEGIN SELECT RAISE(ABORT,'disk fault'); END;")
    payload, targets = sample()
    with pytest.raises(sqlite3.Error):
        ingest_batch(store, payload, targets, 5, 100, run='test', mono=100, revision='v1', metadata={'cycle':1})
    with connect(store.path, readonly=True) as db:
        for table in ('channels', 'cycles', 'incidents', 'gaps', 'daily'):
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
    assert store.epoch() is None


def test_batch_epoch_and_aggregates_are_atomic_idempotent(tmp_path):
    store = Store(tmp_path/'db', timing=LEGACY_TIMING)
    payload, targets = sample()
    for _ in range(2):
        ingest_batch(store, payload, targets, 5, 100, run='test', mono=100, revision='v1', metadata={'cycle':1})
    assert store.epoch() == {'cycle':1}
    with connect(store.path, readonly=True) as db:
        assert [r['samples'] for r in db.execute('SELECT * FROM daily')] == [1,1]
    assert all(v['state']=='UP' for v in current(store.path, 101).values())


def test_corruption_never_creates_empty_healthy_database(tmp_path):
    path = tmp_path/'db'
    path.write_bytes(b'broken database'*50)
    with pytest.raises(sqlite3.DatabaseError):
        Store(path)
    assert path.read_bytes().startswith(b'broken database')


def test_actual_sqlite_full_rolls_back_both_channels(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import uplink_monitor.storage as storage
    store = Store(tmp_path/'db', timing=LEGACY_TIMING)
    original = storage.connect
    @contextmanager
    def limited(*args, **kwargs):
        with original(*args, **kwargs) as db:
            pages = db.execute('PRAGMA page_count').fetchone()[0]
            db.execute(f'PRAGMA max_page_count={pages}')
            yield db
    monkeypatch.setattr(storage, 'connect', limited)
    payload, targets = sample()
    with pytest.raises(sqlite3.OperationalError) as exc:
        ingest_batch(store, payload, targets, 5, 100, run='test', mono=100,
                     revision='v1', metadata={'padding':'x'*6000})
    assert exc.value.sqlite_errorcode == sqlite3.SQLITE_FULL
    with original(store.path, readonly=True) as db:
        assert db.execute('SELECT count(*) FROM cycles').fetchone()[0]==0


def test_retention_rebuilds_partial_day_aggregate(tmp_path):
    from uplink_monitor.storage import report
    store = Store(tmp_path/'db', timing=LEGACY_TIMING)
    for slot in (86400,86410,86420):
        payload, targets = sample(slot)
        targets.update(resolved_unix=slot-1,expires_unix=slot+100)
        ingest_batch(store, payload, targets, 5, slot, run='test', mono=slot, revision='v1')
    store.prune(2*86400+15, retention=86400)
    with connect(store.path, readonly=True) as db:
        assert [r[0] for r in db.execute('SELECT samples FROM daily')]==[2,2]
    assert report(store.path,'cenuta',86400,2*86400)['valid_seconds']==20


def test_incident_boundary_has_no_invented_known_start(tmp_path):
    from uplink_monitor.model import Assessment
    from uplink_monitor.storage import incidents
    store = Store(tmp_path/'db', timing=LEGACY_TIMING)
    for slot in (100,110,120):
        store.ingest('cenuta',slot,'t','1',Assessment('failed','timeout',available=False),mono=slot)
    item = incidents(store.path,'cenuta',0,200)['items'][0]
    assert item['start_window']==[None,100]
    assert item['end_is_censored'] and item['recovery_window'] is None
