import json
import sqlite3

import pytest

from uplink_monitor.storage import Store, current, report, incidents
from test_state import OK, FAIL, UNKNOWN
from uplink_monitor.timing import LEGACY_TIMING


def test_atomic_history_idempotency_gap_and_restart(tmp_path):
    path = tmp_path/'state.sqlite'
    store = Store(path, timing=LEGACY_TIMING)
    for slot in (0,10,20):
        store.ingest('cenuta',slot,'run1','gen5',FAIL,mono=slot)
    assert not store.ingest('cenuta',20,'run1','gen5',FAIL,mono=20)
    assert current(path,20)['cenuta']['outages']==1
    store = Store(path, timing=LEGACY_TIMING)
    store.ingest('cenuta',60,'run2','gen5',FAIL,mono=0)
    stats=report(path,'cenuta',0,70)
    assert stats['failed_seconds']==40 and stats['unknown_seconds']==30
    assert current(path,60)['cenuta']['state']=='DEGRADED'
    assert incidents(path,'cenuta',0,70)['items'][0]['boundary']=='interrupted'
    assert incidents(path,'cenuta',0,70)['items'][0]['ended']==30
    assert report(path,'cenuta',5,25)['failed_seconds']==20
    assert current(path,86)['cenuta']['state']=='UNKNOWN'


def test_invalid_zero_coverage_and_generation_change(tmp_path):
    store=Store(tmp_path/'db', timing=LEGACY_TIMING)
    store.ingest('cenuta',0,'r','g1',FAIL,mono=0)
    store.ingest('cenuta',10,'r','g2',FAIL,mono=10)
    assert current(store.path,10)['cenuta']['outages']==0
    store.ingest('cenuta',20,'r','g2',UNKNOWN,mono=20)
    assert report(store.path,'cenuta',20,30)['availability'] is None
    assert current(store.path,0)['cenuta']['state']=='UNKNOWN'
    with pytest.raises(ValueError):
        store.ingest('cenuta',10,'different','g2',FAIL,mono=10)


def test_deadline_and_storage_failure_do_not_publish_up(tmp_path):
    store=Store(tmp_path/'db', timing=LEGACY_TIMING)
    store.ingest('cenuta',0,'r','g',OK,mono=0,observed=9)
    assert current(store.path,9)['cenuta']['state']=='UNKNOWN'
    db=sqlite3.connect(store.path)
    db.execute('BEGIN IMMEDIATE')
    with pytest.raises(sqlite3.OperationalError):
        store.ingest('cenuta',10,'r','g',OK,mono=10)
    db.rollback()
    db.close()
    assert current(store.path,10)['cenuta']['reason']=='cycle_deadline'


def test_retention_keeps_lifetime_counter(tmp_path):
    store=Store(tmp_path/'db', timing=LEGACY_TIMING)
    for slot in (0,10,20):
        store.ingest('cenuta',slot,'r','g',FAIL,mono=slot)
    store.ingest('cenuta',30,'r','g',OK,mono=30)
    store.ingest('cenuta',40,'r','g',OK,mono=40)
    store.prune(100000,86400)
    assert current(store.path,100000)['cenuta']['outages']==1
    assert not incidents(store.path,'cenuta',0,50)['items']


def test_default_retention_is_seven_days(tmp_path):
    store = Store(tmp_path/'db')
    for slot in (0, 120):
        store.ingest('cenuta', slot, 'r', 'g', OK, mono=slot)
    store.prune(7*86400+120)
    with sqlite3.connect(store.path) as db:
        assert db.execute('select slot from cycles').fetchall() == [(120.0,)]
