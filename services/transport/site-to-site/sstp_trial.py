"""Certificate-verified, isolated SSTP trial builder; not a production writer."""
from datetime import timedelta
import importlib.util
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_SPEC = importlib.util.spec_from_file_location('direct_trial', Path(__file__).with_name('direct_trial.py'))
_helpers = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_helpers)
quote, public_ip, safe_mode_confirmed = _helpers.quote, _helpers.public_ip, _helpers.safe_mode_confirmed
OWNER = 's2s-sstp-trial-20261019'
NETWORK = ipaddress.ip_network('10.60.64.0/30')
SITES = {'nakhimova': ('HKM0BDXYG74', '10.60.64.2', 443),
         'fethiye': ('HM20B6QXS8H', '10.60.64.1', 5443)}
CLIENT, SERVER = 'sstp-direct-trial-out', 'sstp-direct-trial-in'
PROFILE, USER = OWNER + '-profile', OWNER + '-user'
CA, SERVER_CERT, CLIENT_CERT = OWNER + '-ca', OWNER + '-server', OWNER + '-client'
SERVER_FIELDS = ('enabled', 'port', 'certificate', 'authentication', 'default-profile',
                 'tls-version', 'verify-client-certificate', 'max-mtu', 'max-mru',
                 'pfs', 'keepalive-timeout', 'ciphers')


def certificate_snapshot(rows, get_property):
    """RouterOS print as-value omits calculated certificate fingerprints."""
    result = {}
    for row in rows:
        fingerprint = str(get_property(row['.id'], 'fingerprint')).lower().replace(':', '')
        if len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
            raise ValueError('unidentifiable_certificate')
        if fingerprint in result:
            raise ValueError('duplicate_certificate_fingerprint')
        trusted = get_property(row['.id'], 'trusted')
        if type(trusted) is not bool:
            raise ValueError('untyped_certificate_trust')
        result[fingerprint] = dict(name=row['name'], trusted=trusted)
    return result


def assert_free(snapshot):
    for path, rows in snapshot.items():
        for row in rows:
            if row.get('name') in (CLIENT, SERVER, PROFILE, USER, CA, SERVER_CERT, CLIENT_CERT) or row.get('comment', '').startswith(OWNER):
                raise ValueError('sstp_namespace_occupied')
            candidates = []
            if path == '/ip address':
                candidates.append(row.get('address', ''))
            if path == '/ip route':
                candidates.append(row.get('dst-address', ''))
            if path == '/interface wireguard peers':
                value = row.get('allowed-address', [])
                candidates.extend(value.split(',') if isinstance(value, str) else value)
            for value in candidates:
                if not value:
                    continue
                network = ipaddress.ip_network(value, strict=False)
                if network.version == 4 and network.prefixlen and NETWORK.overlaps(network):
                    raise ValueError('sstp_network_occupied')


def bundle(endpoint, now, password, valid_days=7):
    endpoint = public_ip(endpoint)
    if type(valid_days) is not int or not 1 <= valid_days <= 825:
        raise ValueError('invalid_certificate_lifetime')
    if not isinstance(password, bytes) or len(password) < 24:
        raise ValueError('weak_import_password')
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA)])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
          .not_valid_after(now + timedelta(days=valid_days)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
          .sign(ca_key, hashes.SHA256()))
    result = {'ca.pem': ca.public_bytes(serialization.Encoding.PEM),
              'ca-key.pem': ca_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                serialization.BestAvailableEncryption(password))}
    metadata = {'ca': dict(name=CA, fingerprint=ca.fingerprint(hashes.SHA256()).hex())}
    # Legacy-compatible encryption protects only the import files; TLS uses AES-GCM.
    encryption = (serialization.PrivateFormat.PKCS12.encryption_builder().kdf_rounds(20000)
                  .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC).hmac_hash(hashes.SHA1()).build(password))
    for role, cn, eku in [('server', SERVER_CERT, ExtendedKeyUsageOID.SERVER_AUTH),
                           ('client', CLIENT_CERT, ExtendedKeyUsageOID.CLIENT_AUTH)]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
                   .issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=valid_days))
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
                   .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), True)
                   .add_extension(x509.ExtendedKeyUsage([eku]), False)
                   .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
                   .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False))
        if role == 'server':
            builder = builder.add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(endpoint))]), False)
        cert = builder.sign(ca_key, hashes.SHA256())
        result[role + '.p12'] = pkcs12.serialize_key_and_certificates(cn.encode(), key, cert, None, encryption)
        metadata[role] = dict(name=cn, fingerprint=cert.fingerprint(hashes.SHA256()).hex())
    return result, metadata


def stage_commands(site, endpoint, password):
    endpoint = public_ip(endpoint)
    if not isinstance(password, str) or len(password) < 24:
        raise ValueError('weak_ppp_password')
    iface = CLIENT if site == 'nakhimova' else SERVER
    local = SITES[site][1]
    remote = SITES['fethiye' if site == 'nakhimova' else 'nakhimova'][1]
    commands = [f'/ppp profile add name="{PROFILE}" use-ipv6=no use-mpls=no use-compression=no only-one=yes change-tcp-mss=yes']
    if site == 'fethiye':
        commands += [f'/ppp secret add name="{USER}" password={quote(password)} service=sstp profile="{PROFILE}" local-address={local} remote-address={remote} routes="" comment="{OWNER}:secret"',
                     f'/interface sstp-server add name="{SERVER}" user="{USER}" comment="{OWNER}:interface"']
    else:
        commands += [f'/interface sstp-client add disabled=yes name="{CLIENT}" connect-to={endpoint} port=443 user="{USER}" password={quote(password)} certificate="{CLIENT_CERT}" profile="{PROFILE}" authentication=mschap2 verify-server-certificate=yes verify-server-address-from-certificate=yes tls-version=only-1.2 ciphers=aes256-gcm-sha384 pfs=required max-mtu=1400 max-mru=1400 keepalive-timeout=10 add-default-route=no comment="{OWNER}:interface"']
    head = 'place-before=([find where dynamic=no]->0)'
    commands += [f'/ip firewall filter add chain=forward action=drop in-interface="{iface}" {head} comment="{OWNER}:forward-in"',
                 f'/ip firewall filter add chain=forward action=drop out-interface="{iface}" {head} comment="{OWNER}:forward-out"',
                 f'/ip firewall filter add chain=input action=drop in-interface="{iface}" {head} comment="{OWNER}:input-deny"',
                 f'/ip firewall filter add chain=input action=accept protocol=icmp in-interface="{iface}" src-address={remote}/32 dst-address={local}/32 {head} comment="{OWNER}:icmp"']
    if site == 'fethiye':
        commands += [f'/ip firewall filter add chain=input action=accept protocol=tcp in-interface="{iface}" src-address={remote}/32 dst-address={local}/32 dst-port=80 {head} comment="{OWNER}:http"',
                     f'/ip firewall filter add chain=input action=accept protocol=tcp in-interface=ether1 dst-port=5443 {head} comment="{OWNER}:outer"',
                     f'/ip firewall raw add chain=prerouting action=passthrough protocol=tcp dst-port=443,5443 tcp-flags=syn limit=5/1s,10:packet log=yes log-prefix="STP-SYN " comment="{OWNER}:observe"']
    else:
        commands += [f'/ip firewall filter add chain=input action=accept protocol=tcp in-interface="{iface}" src-address={remote}/32 dst-address={local}/32 src-port=80 connection-state=established {head} comment="{OWNER}:http"']
    return commands


def enable_server(port=5443):
    if port not in (443, 5443):
        raise ValueError('unapproved_listener')
    return (f'/interface sstp-server server set enabled=yes port={port} certificate="{SERVER_CERT}" authentication=mschap2 '
            f'default-profile="{PROFILE}" tls-version=only-1.2 ciphers=aes256-gcm-sha384 verify-client-certificate=yes '
            'pfs=required max-mtu=1400 max-mru=1400 keepalive-timeout=10')


def restore_server(state):
    if set(state) != set(SERVER_FIELDS) or state['enabled'] is not False:
        raise ValueError('unqualified_server_baseline')
    def value(v):
        if type(v) is bool:
            return 'yes' if v else 'no'
        if type(v) in (int, float) and int(v) == v:
            return str(int(v))
        if isinstance(v, list):
            return quote(','.join(map(str, v)))
        return quote(v)
    return '/interface sstp-server server set ' + ' '.join(k + '=' + value(state[k]) for k in SERVER_FIELDS)


def http_probe():
    return (f'/tool netwatch add name="{OWNER}-http" comment="{OWNER}:http-probe" type=http-get '
            'host=10.60.64.1 src-address=10.60.64.2 port=80 interval=5s timeout=3s '
            'start-delay=1s startup-delay=0s http-codes=200-399 '
            'up-script="" down-script="" test-script=""')


def ping_command(site, size=56):
    if type(size) is not int or size not in (56, 1400):
        raise ValueError('unsupported_size')
    remote = SITES['fethiye' if site == 'nakhimova' else 'nakhimova'][1]
    iface = CLIENT if site == 'nakhimova' else SERVER
    return f'/ping address={remote} src-address={SITES[site][1]} interface={iface} count=5 interval=200ms size={size} do-not-fragment'


def cleanup_commands(site):
    commands = [f'/tool netwatch remove [find where comment="{OWNER}:http-probe"]']
    if site == 'nakhimova':
        commands += [f'/interface sstp-client remove [find where name="{CLIENT}" and comment="{OWNER}:interface"]']
    else:
        commands += [f'/ppp active remove [find where name="{USER}" and service=sstp]',
                     f'/interface sstp-server remove [find where name="{SERVER}" and comment="{OWNER}:interface"]',
                     f'/ppp secret remove [find where name="{USER}" and comment="{OWNER}:secret"]']
    for suffix in ('forward-in', 'forward-out', 'input-deny', 'icmp', 'http', 'outer'):
        commands.append(f'/ip firewall filter remove [find where comment="{OWNER}:{suffix}"]')
    commands += [f'/ip firewall raw remove [find where comment="{OWNER}:observe"]',
                 f'/ppp profile remove [find where name="{PROFILE}"]']
    return commands
