import copy
import pytest
from uplink_monitor.storage import Store
from uplink_monitor.collector import ingest_batch
from uplink_monitor.history_export import export_page
from uplink_monitor.history_cache import Cache
from uplink_monitor.sync_daemon import synchronize
from test_collector import sample


def source(tmp_path):
    store=Store(tmp_path/'server.db')
    for slot in (120,240,360):
        payload,targets=sample(slot)
        targets.update(resolved_unix=slot-10,expires_unix=slot+100)
        ingest_batch(store,payload,targets,5,slot,run='test',mono=slot,revision='v1')
    return store


def getter(store):
    def get(after,limit=100):
        return dict(export_page(store.path,after,limit),server_time=361,source_ready=True)
    return get


def test_backfill_idempotent_and_offline_history(tmp_path):
    store=source(tmp_path); cache=Cache(tmp_path/'local.db')
    assert synchronize(cache,getter(store),lambda:361)
    assert synchronize(cache,getter(store),lambda:362)
    with cache.db() as db:
        assert db.execute('SELECT count(*) FROM samples').fetchone()[0]==6
    assert cache.snapshot(362)['synced']
    before=cache.history(120,400,'state')
    cache.error('network_unavailable')
    assert not cache.snapshot(363)['synced']
    assert all(r['state']==0 for r in cache.snapshot(363)['current'])
    assert cache.history(120,400,'state')==before


def test_partial_and_changed_batches_do_not_advance(tmp_path):
    store=source(tmp_path); cache=Cache(tmp_path/'local.db'); get=getter(store)
    page=get(-1,1); cache.apply(page,361)
    broken=get(120); broken['rows'].pop()
    with pytest.raises(ValueError): cache.apply(broken,362)
    assert cache.cursor(page['database_id'])==120
    changed=copy.deepcopy(page); changed['rows'][0]['state']='DOWN'
    with pytest.raises(ValueError,match='immutable'): cache.apply(changed,362)
    assert cache.cursor(page['database_id'])==120


def test_transport_failure_preserves_committed_cursor(tmp_path):
    store=source(tmp_path); cache=Cache(tmp_path/'local.db'); get=getter(store)
    def broken(after,limit):
        if after!=-1: raise TimeoutError()
        return get(after,limit)
    with pytest.raises(TimeoutError): synchronize(cache,broken,lambda:361)
    assert cache.cursor(get(-1)['database_id'])==120
    assert synchronize(cache,get,lambda:362)


def test_server_identity_and_invalid_cursor(tmp_path):
    store=source(tmp_path)
    assert export_page(store.path)['database_id']==export_page(store.path)['database_id']
    with pytest.raises(ValueError): export_page(store.path,9999)
    cache=Cache(tmp_path/'local.db')
    assert synchronize(cache,getter(store),lambda:361)
    page=getter(store)(-1,1); page['head']=120
    with pytest.raises(ValueError): cache.apply(page,362)
