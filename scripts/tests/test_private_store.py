"""Synthetic secrets only; no network or user keys."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import private_store as store


def fixture(root, paths=('clients/example.conf',)):
    root.mkdir(mode=0o700, exist_ok=True)
    payload = b'SYNTHETIC-SECRET'
    data = {'schema_version': 1, 'records': [], 'files': [
        {'path': path, 'sha256': hashlib.sha256(payload).hexdigest(),
         'value': base64.b64encode(payload).decode()} for path in paths]}
    store.write_private(root / 'secrets.json', json.dumps(data).encode())
    return data


def test_restore_portable_bytes_and_modes(tmp_path):
    root = tmp_path / 'different-checkout'
    fixture(root)
    assert store.materialize(root)['files'] == 1
    assert store.materialize(root, verify_only=True)['status'] == 'VERIFIED'
    assert (root / 'clients/example.conf').read_bytes() == b'SYNTHETIC-SECRET'
    assert (root / 'clients/example.conf').stat().st_mode & 0o777 == 0o600
    assert (root / 'clients').stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('path', ['../escape', '/tmp/escape', '.', 'secrets.json'])
def test_reject_unsafe_path_before_any_write(tmp_path, path):
    fixture(tmp_path, ('clients/example.conf', path))
    with pytest.raises(ValueError):
        store.materialize(tmp_path)
    assert not (tmp_path / 'clients').exists()


def test_reject_duplicate_path(tmp_path):
    fixture(tmp_path, ('clients/example.conf', 'clients/example.conf'))
    with pytest.raises(ValueError):
        store.materialize(tmp_path)


def test_reject_symlink_parent(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'elsewhere').mkdir()
    (tmp_path / 'clients').symlink_to(tmp_path / 'elsewhere')
    with pytest.raises(ValueError):
        store.materialize(tmp_path)
    assert not (tmp_path / 'elsewhere/example.conf').exists()


def test_reject_corrupt_record(tmp_path):
    data = fixture(tmp_path)
    data['files'][0]['sha256'] = '0' * 64
    store.write_private(tmp_path / 'secrets.json', json.dumps(data).encode())
    with pytest.raises(ValueError):
        store.materialize(tmp_path)


def test_reject_exposed_store(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'secrets.json').chmod(0o644)
    with pytest.raises(ValueError):
        store.load(tmp_path)


def test_verify_does_not_rewrite_modified_master(tmp_path):
    fixture(tmp_path)
    store.materialize(tmp_path)
    master = tmp_path / 'clients/example.conf'
    master.write_bytes(b'NEWER-MASTER')
    with pytest.raises(ValueError):
        store.materialize(tmp_path, verify_only=True)
    assert master.read_bytes() == b'NEWER-MASTER'


def test_ssh_renderer_uses_scoped_existing_identities(tmp_path, monkeypatch):
    import setup_mac
    monkeypatch.setattr(setup_mac, 'local_root', lambda: tmp_path)
    setup_mac.render_ssh()
    config = (tmp_path / 'ssh/config').read_text()
    assert 'StrictHostKeyChecking yes' in config
    assert 'PasswordAuthentication no' in config
    assert 'ForwardAgent no' in config
    assert 'known_hosts_cenuta' in config
    assert 'known_hosts_orekhovo' in config
    assert 'HostKeyAlias 192.168.88.1' in config
    assert 'LocalForward 19118 127.0.0.1:19108' in config
    assert str(tmp_path) in config


def test_launchd_cache_is_derived_from_same_store(tmp_path, monkeypatch):
    import setup_mac
    monkeypatch.setattr(setup_mac.Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(setup_mac, 'load', lambda: {'files': [
        {'path': 'ssh/synthetic-key', 'value': base64.b64encode(b'SYNTHETIC-SSH').decode()},
        {'path': 'clients/ignored.conf', 'value': base64.b64encode(b'IGNORED').decode()}]})
    config = setup_mac.materialize_ssh_cache()
    cache = tmp_path / '.local/state/system-project'
    assert config == cache / 'ssh/config'
    assert (cache / 'ssh/synthetic-key').read_bytes() == b'SYNTHETIC-SSH'
    assert not (cache / 'clients').exists()
    assert 'IdentityFile "' + str(cache / 'ssh') in config.read_text()
