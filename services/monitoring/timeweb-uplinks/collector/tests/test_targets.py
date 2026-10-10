import pytest
import json
from uplink_monitor.targets import Targets, Refused

POLICIES={'a':{'url':'https://www.gstatic.com/generate_204','host':'www.gstatic.com'}}


def test_expiry_atomic_refresh_and_failed_refresh(tmp_path):
    cache=Targets(tmp_path/'targets.json',POLICIES)
    with pytest.raises(Refused): cache.get(100)
    cache.refresh(lambda host: (['1.1.1.1'],30),100)
    assert cache.get(129)['generation']==1
    with pytest.raises(Refused): cache.get(130)
    original=cache.path.read_bytes()
    with pytest.raises(Refused): cache.refresh(lambda host: (['127.0.0.1'],30),131)
    assert cache.path.read_bytes()==original
    with pytest.raises(Refused): cache.get(131)
    assert cache.refresh(lambda host: (['8.8.8.8'],15),132)['generation']==2
    with pytest.raises(Refused): cache.get(131)


@pytest.mark.parametrize('ips,ttl',[([],30),(['10.1.1.1'],30),(['::1'],30),(['1.1.1.1'],0),(['1.1.1.1'],float('nan'))])
def test_bad_dns_answers_refused(tmp_path,ips,ttl):
    with pytest.raises(Refused): Targets(tmp_path/'cache',POLICIES).refresh(lambda h:(ips,ttl),100)


def test_extended_ttl_and_bad_generation_refused(tmp_path):
    cache=Targets(tmp_path/'cache',POLICIES)
    value=cache.refresh(lambda host: (['1.1.1.1'],30),100)
    value['expires_unix']=10000
    cache.path.write_text(json.dumps(value))
    with pytest.raises(Refused): cache.get(101)
    value['expires_unix']=130
    value['generation']=0
    cache.path.write_text(json.dumps(value))
    with pytest.raises(Refused): cache.get(102)
