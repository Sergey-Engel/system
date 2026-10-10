"""Offline invariants for staging; does not install or connect anywhere."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prepare', ROOT / 'prepare_stage3.py')
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class StagingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = json.loads((ROOT / 'staging/fornex/server.loopback.json').read_text())
        cls.keys = json.loads((ROOT / 'staging/fornex/secrets.json').read_text())
        cls.labkeys = json.loads((ROOT / 'lab/input/secrets.json').read_text())

    def test_first_and_final_blackhole(self):
        self.assertEqual(self.server['outbounds'][0], {'tag': 'blocked', 'protocol': 'blackhole'})
        self.assertEqual(self.server['routing']['rules'][-1]['outboundTag'], 'blocked')
        self.assertEqual({x['protocol'] for x in self.server['outbounds']}, {'blackhole', 'wireguard'})

    def test_staging_is_loopback_only(self):
        self.assertEqual(self.server['inbounds'][0]['listen'], '127.0.0.1')

    def test_userspace_ipv4(self):
        wg = self.server['outbounds'][1]['settings']
        self.assertIs(wg['noKernelTun'], True)
        self.assertEqual(wg['address'], ['10.20.0.3/32'])
        self.assertEqual(wg['domainStrategy'], 'ForceIPv4')
        self.assertEqual(wg['peers'][0]['allowedIPs'], ['0.0.0.0/0'])

    def test_independent_keys_and_device_ids(self):
        for name in ('reality', 'wg_client'):
            self.assertNotEqual(self.keys[name]['private'], self.labkeys[name]['private'])
        self.assertNotEqual(self.keys['psk'], self.labkeys['psk'])
        ids = [keys[device + '_uuid'] for keys in (self.keys, self.labkeys) for device in ('macbook', 'iphone')]
        self.assertEqual(len(set(ids)), 4)

    def test_public_private_key_correspondence(self):
        for keys in (self.keys, self.labkeys):
            for name in ('reality', 'wg_client'):
                encoded = keys[name]['private']
                decode = base64.urlsafe_b64decode if name == 'reality' else base64.b64decode
                encode = base64.urlsafe_b64encode if name == 'reality' else base64.b64encode
                key = X25519PrivateKey.from_private_bytes(decode(encoded + '=' * (-len(encoded) % 4)))
                public = encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
                self.assertEqual(public.rstrip('='), keys[name]['public'].rstrip('='))

    def test_client_ids_routed_by_server(self):
        clients = self.server['inbounds'][0]['settings']['clients']
        users = self.server['routing']['rules'][2]['user']
        self.assertEqual(sorted(users), sorted(x['email'] for x in clients))
        for device in ('macbook', 'iphone'):
            config = json.loads((ROOT / f'staging/fornex/client-{device}.json').read_text())
            outbound = config['outbounds'][1]
            self.assertIn(outbound['settings']['vnext'][0]['users'][0]['id'], [x['id'] for x in clients])
            self.assertEqual(outbound['streamSettings']['realitySettings']['publicKey'], self.keys['reality']['public'])

    def test_dns_exact_routing_no_local_or_fallback(self):
        self.assertEqual(self.server['dns']['servers'], ['https://1.1.1.1/dns-query'])
        self.assertIs(self.server['dns']['disableFallback'], True)
        self.assertEqual(self.server['routing']['rules'][1], {'type': 'field', 'inboundTag': ['dns-fornex'],
            'ip': ['1.1.1.1/32'], 'port': '443', 'network': 'tcp', 'outboundTag': 'wg-fornex'})

    def test_private_ipv6_and_management_deny(self):
        blocked = self.server['routing']['rules'][0]['ip']
        for network in PREPARE.PRIVATE + ['94.241.171.65/32', '103.75.126.143/32', '89.252.153.129/32']:
            self.assertIn(network, blocked)

    def test_validated_release_binaries_unchanged(self):
        meta = json.loads((ROOT / 'vendor/artifacts.json').read_text())
        for arch in ('amd64', 'arm64'):
            self.assertEqual(meta[arch]['archive_sha256'], PREPARE.ASSETS[arch][1])
            self.assertEqual(meta[arch]['binary_sha256'], hashlib.sha256((ROOT / 'vendor' / arch / 'xray').read_bytes()).hexdigest())

    def test_no_tls_verification_bypass(self):
        content = json.dumps(self.server).lower()
        self.assertNotIn('allowinsecure', content)
        self.assertNotIn('https+local://', content)
        self.assertEqual(self.server['inbounds'][0]['streamSettings']['realitySettings']['show'], False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
