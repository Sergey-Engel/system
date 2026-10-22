"""No routing choice or unauthorised namespace drift can pass readiness."""
import importlib.util
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parent))
spec=importlib.util.spec_from_file_location('split_bridge',Path(__file__).with_name('split_bridge.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def test_cenuta_selector_never_targets_bth_or_a_client_ip():
    rule=b.cenuta_rule()
    assert rule==['priority','218','from','10.50.50.245/32','iif','sstprelay0','table','200','protocol','243']

def test_config_requires_owned_hashes_and_no_failover(tmp_path):
    file=tmp_path/'code.py';file.write_text('fixture')
    cfg=dict(version=1,automatic_fallback=False,files={str(file):b.hashlib.sha256(b'fixture').hexdigest()})
    b.verify_files(cfg)
    file.write_text('drift')
    with pytest.raises(ValueError):b.verify_files(cfg)
    with pytest.raises(ValueError):b.verify_files(dict(cfg,automatic_fallback=True))

def test_nft_normalization_does_not_hide_policy_or_interface_changes():
    first={'nftables':[{'metainfo':{'version':'1'}},{'rule':{'handle':1,'chain':'forward','expr':[{'counter':{'bytes':10,'packets':2}},{'accept':None}]}}]}
    other={'nftables':[{'rule':{'handle':99,'chain':'forward','expr':[{'counter':{'bytes':40,'packets':3}},{'accept':None}]}}]}
    assert b.normalize_nft(first)==b.normalize_nft(other)
    other['nftables'][0]['rule']['chain']='input'
    assert b.normalize_nft(first)!=b.normalize_nft(other)

def test_prepared_source_has_no_device_or_transport_choice_mutator():
    source=Path(b.__file__).read_text()
    assert 'controller.lock' not in source and 'CENUTA_Devices' not in source
    assert 'wg set' not in source and "'flush'" not in source
    assert "CONFIG=Path('/etc/sstp-timeweb/split-config.json')" in source
