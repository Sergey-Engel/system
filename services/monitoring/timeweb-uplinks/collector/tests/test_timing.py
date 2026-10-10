import sqlite3

import pytest

from uplink_monitor.collector import evaluate, ingest_batch
from uplink_monitor.exporter import metrics
from uplink_monitor.scheduler import Scheduler
from uplink_monitor.storage import Store, current, report, incidents
from uplink_monitor.timing import DEFAULT_TIMING, LEGACY_TIMING, Timing
from test_collector import sample
from test_state import OK, FAIL


def test_120_second_scheduler_no_early_or_catchup_probe():
    s=Scheduler(100,wall_started=130)
    assert s.due(100,130) is None
    assert s.due(210,240)['slot']==240
    assert s.due(329,359) is None
    assert s.due(330,360)['slot']==360
    assert s.due(710,740)['missed']==2
    assert s.next_due==810


def test_thresholds_freshness_and_120_second_history(tmp_path):
    store=Store(tmp_path/'db')
    for slot in (0,120,240):
        store.ingest('cenuta',slot,'r','g',FAIL,mono=slot)
    assert current(store.path,240)['cenuta']['state']=='DOWN'
    store.ingest('cenuta',360,'r','g',OK,mono=360)
    assert current(store.path,360)['cenuta']['state']=='DOWN'
    store.ingest('cenuta',480,'r','g',OK,mono=480)
    assert current(store.path,660)['cenuta']['state']=='UP'
    assert current(store.path,661)['cenuta']['state']=='UNKNOWN'
    stats=report(store.path,'cenuta',0,600)
    assert stats['failed_seconds']==360 and stats['available_seconds']==240
    assert stats['unknown_seconds']==0 and stats['resolution_seconds']==120
    assert incidents(store.path,'cenuta',0,600)['items'][0]['ended']==360
    store.ingest('cenuta',840,'r','g',OK,mono=840)
    assert report(store.path,'cenuta',0,960)['unknown_seconds']==240
    with pytest.raises(ValueError): store.ingest('cenuta',850,'r','g',OK,mono=850)


def test_batch_deadline_expiry_and_exporter_are_consistent(tmp_path):
    store=Store(tmp_path/'db')
    payload, targets=sample(120)
    payload['finished_unix']=150
    results=ingest_batch(store,payload,targets,5,120,run='r',mono=120,revision='120s')
    assert results['cenuta'][0].kind=='healthy'
    assert 'vpn_uplink_state{upstream="cenuta"} 1' in metrics(current(store.path,300))
    assert 'vpn_uplink_state{upstream="cenuta"} 0' in metrics(current(store.path,331))
    payload['finished_unix']=166
    assert evaluate(payload,targets,5,120)['cenuta'][0].reason=='cycle_deadline'
    payload['finished_unix']=150
    targets['expires_unix']=120
    assert evaluate(payload,targets,5,120)['cenuta'][0].reason=='targets_expired'


def test_old_database_resolution_is_not_reinterpreted(tmp_path):
    store=Store(tmp_path/'old', timing=LEGACY_TIMING)
    store.ingest('cenuta',0,'r','g',FAIL,mono=0)
    with pytest.raises(ValueError,match='timing_mismatch'): Store(store.path)
    # Simulate the previously written v1 schema on a disposable fixture.
    with sqlite3.connect(store.path) as db:
        db.execute('DROP TABLE settings')
        db.execute('PRAGMA user_version=1')
    assert report(store.path,'cenuta',0,120)['failed_seconds']==10
    assert report(store.path,'cenuta',0,120)['unknown_seconds']==110
    assert current(store.path,26)['cenuta']['state']=='UNKNOWN'
    with pytest.raises(ValueError,match='legacy_database_read_only'): Store(store.path)


@pytest.mark.parametrize('values', [dict(interval=0),dict(deadline=120),dict(stale_after=150)])
def test_invalid_timing_refused(values):
    with pytest.raises(ValueError): Timing(**values)
