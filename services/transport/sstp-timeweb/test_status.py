import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('sstp_tw_status',Path(__file__).with_name('status.py'))
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    return dict(link_type='ppp',flags=['POINTOPOINT','UP'],mtu=1400,
                addr_info=[dict(family='inet',local='10.60.65.1',address='10.60.65.2',prefixlen=32)])


def test_live_iproute2_point_to_point_json_uses_address_for_peer():
    assert s.valid_peer(fixture())


def test_wrong_peer_or_mtu_or_type_is_not_ready():
    for key,value in [('link_type','ether'),('flags',[]),('mtu',1500)]:
        item=fixture();item[key]=value
        assert not s.valid_peer(item)
    for key,value in [('local','10.60.65.2'),('address','10.60.65.99'),('prefixlen',24)]:
        item=fixture();item['addr_info'][0][key]=value
        assert not s.valid_peer(item)
    assert not s.valid_peer({})
