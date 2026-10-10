import copy
import pytest
from uplink_monitor.adapter import BatchAdapter, decode_batch
from uplink_monitor.collector import POLICIES, SOURCES, evaluate
from uplink_monitor.model import parse_helper


def batch():
    targets = dict(resolved_unix=120, expires_unix=180, targets={
        name:dict(host=p['host'], url=p['url'], ips=['1.1.1.1']) for name,p in POLICIES.items()})
    value = dict(started_unix=120, finished_unix=121, generation=7, path_verified=True, records=[])
    for up,source in {**SOURCES, 'direct':'94.241.171.65'}.items():
        for name,p in POLICIES.items():
            value['records'].append(dict(upstream=up,target=name,curl_exit=0,
                output=f'http={p["expected_http"][0]} local={source} remote=1.1.1.1 seconds=0.2 connect=0.02 tls=0.1\n'))
    return value, targets


def test_batch_to_collector_preserves_failed_vs_invalid_and_control():
    value, targets = batch()
    for r in value['records']:
        if r['upstream']=='cenuta':
            r.update(curl_exit=28,output='http=000 local= remote= seconds=3 connect=0 tls=0\n')
    result = evaluate(decode_batch(value, targets), targets, 7, 120)
    assert result['fornex'][0].kind=='healthy'
    assert result['cenuta'][0].reason=='tcp_connect_failed'
    assert 'independent_control_ok' in result['cenuta'][0].signals
    assert 'other_uplink_ok' in result['cenuta'][0].signals


@pytest.mark.parametrize('mode',['missing','duplicate','marker','bad_rc','bad_generation'])
def test_bad_batch_protocol_refused(mode):
    value, targets = batch()
    if mode=='missing': value['records'].pop()
    if mode=='duplicate': value['records'][1]=value['records'][0]
    if mode=='marker': value['records'][0]['output']+='VALID_OBSERVATION'
    if mode=='bad_rc': value['records'][0]['curl_exit']=False
    if mode=='bad_generation': value['generation']='7'
    with pytest.raises(ValueError): decode_batch(value, targets)


def test_default_coverage_gate_prevents_any_command(tmp_path):
    adapter = BatchAdapter({}, tmp_path, runner=lambda *_: pytest.fail('must not run'))
    with pytest.raises(ValueError,match='generation_coverage_not_accepted'):
        adapter({},45)


@pytest.mark.parametrize('connect,tls,phase',[(0,0,'tcp_connect'),(.1,0,'tls'),(.1,.2,'http_body')])
def test_timeout_phase_timers(connect,tls,phase):
    raw=f'http=000 local= remote= seconds=5 connect={connect} tls={tls}\nVALID_OBSERVATION curl_exit=28 generation=7'
    p=parse_helper(raw,returncode=0,generation=7,source='10.40.40.2',pinned_ip='1.1.1.1',
                   expected_http=(204,),target='gstatic',family='google')
    assert p.valid and not p.success and p.phase==phase
