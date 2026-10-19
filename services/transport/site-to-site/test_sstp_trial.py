from datetime import datetime, timezone
import importlib.util
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID
import pytest

SPEC = importlib.util.spec_from_file_location('sstp_trial', Path(__file__).with_name('sstp_trial.py'))
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
PASSWORD = 'test-only-password-never-used-live-123'


def test_calculated_fingerprint_requested_even_when_print_omits_it():
    row = {'.id': '*1', 'name': 'test-cert', 'trusted': 'untyped'}
    values = {'fingerprint': 'AB:' * 31 + 'AB', 'trusted': True}
    result = d.certificate_snapshot([row], lambda ident, prop: values[prop])
    assert result == {'ab' * 32: dict(name='test-cert', trusted=True)}


@pytest.mark.parametrize('values', [
    {'fingerprint': '', 'trusted': True},
    {'fingerprint': 'x' * 64, 'trusted': True},
    {'fingerprint': 'a' * 64, 'trusted': 'true'},
])
def test_unidentifiable_certificate_or_untyped_trust_refused(values):
    with pytest.raises(ValueError):
        d.certificate_snapshot([{'.id': '*1', 'name': 'unknown'}], lambda ident, prop: values[prop])


def test_duplicate_fingerprint_refused():
    values = {'fingerprint': 'a' * 64, 'trusted': True}
    with pytest.raises(ValueError):
        d.certificate_snapshot([{'.id': '*1', 'name': 'a'}, {'.id': '*2', 'name': 'b'}],
                               lambda ident, prop: values[prop])


@pytest.mark.parametrize('site', d.SITES)
def test_new_objects_only_no_working_transport_routes_or_nat(site):
    commands = d.stage_commands(site, '194.61.140.217', PASSWORD)
    text = '\n'.join(commands)
    assert 'wg-s2s-tw' not in text and '/ip route' not in text and '/ip firewall nat' not in text
    assert text.count('chain=forward action=drop') == 2
    assert d.PROFILE in text
    assert 'use-vj-compression' not in text
    if site == 'nakhimova':
        for required in ('disabled=yes', 'verify-server-certificate=yes', 'verify-server-address-from-certificate=yes',
                         'add-default-route=no', 'tls-version=only-1.2', 'authentication=mschap2'):
            assert required in text
        assert 'use-peer-dns=yes' not in text
        assert 'src-address=10.60.64.1/32 dst-address=10.60.64.2/32 src-port=80 connection-state=established' in text
        assert commands[-1].endswith('comment="' + d.OWNER + ':http"')
        assert commands.index(next(c for c in commands if ':input-deny"' in c)) < len(commands) - 1
    else:
        assert 'routes=""' in text and 'dst-port=5443' in text
        assert 'dst-port=443,5443' in text and 'action=passthrough' in text


def test_server_requires_mutual_tls_and_approved_port():
    text = d.enable_server()
    assert 'verify-client-certificate=yes' in text
    assert 'certificate="' + d.SERVER_CERT + '"' in text
    assert 'tls-version=only-1.2' in text and 'pfs=required' in text
    with pytest.raises(ValueError):
        d.enable_server(80)


def test_cannot_restore_unknown_active_server():
    with pytest.raises(ValueError):
        d.restore_server({'enabled': True})
    state = {k: '' for k in d.SERVER_FIELDS}
    state.update(enabled=False, port=443, authentication=['mschap2'], pfs=False, **{'keepalive-timeout': 60.0})
    text = d.restore_server(state)
    assert 'enabled=no' in text and 'pfs=no' in text and 'authentication="mschap2"' in text
    assert 'keepalive-timeout=60 ' in text and '60.0' not in text


@pytest.mark.parametrize('snapshot', [
    {'/ip address': [{'address': '10.60.64.1/30'}]},
    {'/ip route': [{'dst-address': '10.60.0.0/16'}]},
    {'/interface sstp-client': [{'name': d.CLIENT}]},
    {'/ppp secret': [{'name': d.USER}]},
])
def test_collision_refused(snapshot):
    with pytest.raises(ValueError):
        d.assert_free(snapshot)


def test_certificate_bundle_has_scoped_eku_ip_san_and_encrypted_keys():
    password = PASSWORD.encode()
    files, meta = d.bundle('194.61.140.217', datetime.now(timezone.utc), password)
    ca = x509.load_pem_x509_certificate(files['ca.pem'])
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    for role, eku in [('server', ExtendedKeyUsageOID.SERVER_AUTH), ('client', ExtendedKeyUsageOID.CLIENT_AUTH)]:
        key, cert, extra = pkcs12.load_key_and_certificates(files[role + '.p12'], password)
        assert key is not None and extra == []
        assert cert.fingerprint(hashes.SHA256()).hex() == meta[role]['fingerprint']
        assert cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == x509.ExtendedKeyUsage([eku])
        cert.verify_directly_issued_by(ca)
        with pytest.raises(ValueError):
            pkcs12.load_key_and_certificates(files[role + '.p12'], b'wrong-password')
        if role == 'server':
            assert str(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value[0].value) == '194.61.140.217'
    assert b'ENCRYPTED PRIVATE KEY' in files['ca-key.pem']
    assert files['ca-key.pem'] not in (files['client.p12'], files['server.p12'])


def test_http_is_scoped_and_no_event_scripts():
    command = d.http_probe()
    assert 'host=10.60.64.1 src-address=10.60.64.2 port=80' in command
    assert 'http-codes=200-399' in command and 'http-code-min' not in command
    assert 'up-script="" down-script="" test-script=""' in command


@pytest.mark.parametrize('site', d.SITES)
def test_cleanup_is_exact_owned_scope(site):
    assert all(d.OWNER in c or d.CLIENT in c or d.SERVER in c for c in d.cleanup_commands(site))
    assert all('find where' in c for c in d.cleanup_commands(site))


def test_invalid_secrets_or_nonpublic_endpoint_rejected():
    with pytest.raises(ValueError):
        d.stage_commands('nakhimova', '194.61.140.217', 'short')
    with pytest.raises(ValueError):
        d.bundle('192.168.68.117', datetime.now(timezone.utc), PASSWORD.encode())
