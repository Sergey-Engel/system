import copy
import unittest
from unittest.mock import patch

from runtime_recovery import BASE_RULES, FORWARD, NAT, base_nft, restore_transports, validate_partial


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        dns = [line for proto in ('tcp', 'udp') for line in (
            f'-A DOCKER_OUTPUT -d 127.0.0.11/32 -p {proto} -m {proto} --dport 53 -j DNAT --to-destination 127.0.0.11:34567',
            f'-A DOCKER_POSTROUTING -s 127.0.0.11/32 -p {proto} -m {proto} --sport 34567 -j SNAT --to-source :53')]
        self.baseline = {
            'rules': [{'priority': 0, 'table': 'local'}] + [
                {'priority': p, 'table': 'main'} for p in sorted(BASE_RULES)],
            'routes': [{'dst': 'default', 'dev': 'eth0'}] + [
                {'dst': dst, 'gateway': '172.19.0.1', 'dev': 'eth0', 'flags': []}
                for dst in ('89.252.153.129', '103.75.126.143')] + [
                {'dst': 'default', 'table': '411', 'gateway': '172.19.0.1', 'dev': 'eth0'}],
            'links': [{'ifindex': 1, 'ifname': 'eth0'}],
            'peers': {'fornex': 'peer1', 'cenuta': 'peer2'},
            'filter': '\n'.join(FORWARD + ['-A FORWARD -i wg-clients -j ACCEPT']),
            'nat': '\n'.join(NAT + dns), 'mangle': '-P PREROUTING ACCEPT',
        }
        self.policy = {'baseline': self.baseline, 'monitor_rules': [], 'peers': ['10.50.50.39/32']}

    def test_restart_losses_are_allowed(self):
        current = copy.deepcopy(self.baseline)
        current['rules'] = current['rules'][:1]
        current['routes'] = current['routes'][:1]
        current['links'][0]['ifindex'] = 22
        current['filter'] = '\n'.join([
            '-A FORWARD -s 10.50.50.39/32 -i wg-clients -j DROP',
            '-A FORWARD -i wg-clients -j ACCEPT', *FORWARD])
        current['nat'] = current['nat'].replace('34567', '45678')
        validate_partial(self.policy, current)

    def test_conflicts_and_foreign_changes_refused(self):
        for key in ('filter', 'nat', 'mangle', 'peers', 'links'):
            current = copy.deepcopy(self.baseline)
            current[key] = 'foreign' if isinstance(current[key], str) else []
            with self.assertRaises(AssertionError):
                validate_partial(self.policy, current)
        current = copy.deepcopy(self.baseline)
        current['rules'].append({'priority': 180, 'table': '666'})
        with self.assertRaises(AssertionError):
            validate_partial(self.policy, current)

    def test_unexpected_missing_baseline_rule_refused(self):
        current = copy.deepcopy(self.baseline)
        current['rules'] = current['rules'][1:]
        with self.assertRaises(AssertionError):
            validate_partial(self.policy, current)

    def test_endpoint_conflict_refused(self):
        current = copy.deepcopy(self.baseline)
        current['routes'][1]['gateway'] = '172.19.0.99'
        with self.assertRaises(AssertionError):
            validate_partial(self.policy, current)

    def test_duplicate_baseline_rule_refused(self):
        current = copy.deepcopy(self.baseline)
        current['rules'].append(copy.deepcopy(current['rules'][1]))
        with self.assertRaises(AssertionError):
            validate_partial(self.policy, current)

    def test_selected_wss_carriers_started_without_changing_selection(self):
        saved = {'version': 1, 'upstreams': {'fornex': {'mode': 'backup'},
                                           'cenuta': {'mode': 'native'}}}
        import json
        calls = []

        def run(*args):
            calls.append(args)
            if args[-1] == 'status':
                return 'mode=' + ('backup' if 'fornex' in args[0] else 'native')
            return ''

        with patch('runtime_recovery.Path.read_text', return_value=json.dumps(saved)), \
             patch('runtime_recovery.run', side_effect=run):
            restore_transports()
        self.assertEqual(calls[0], ('systemctl', 'start',
            'wstunnel-timeweb-fornex-wg-fallback.service',
            'wstunnel-timeweb-fornex-xray-fallback.service'))
        self.assertFalse(any('switch' in call for call in calls))

    def test_dns_ports_must_remain_paired(self):
        current = copy.deepcopy(self.baseline)
        current['nat'] = current['nat'].replace('--sport 34567', '--sport 45678')
        with self.assertRaises(AssertionError):
            validate_partial(self.policy, current)

    def test_nft_counters_are_not_policy(self):
        rule = {'family': 'inet', 'table': 'ru_bth', 'chain': 'forward',
                'handle': 7, 'expr': [{'counter': {'packets': 8, 'bytes': 100}}]}
        first = base_nft({'nftables': [{'rule': rule}]})
        rule['handle'] = 17
        rule['expr'][0]['counter']['bytes'] = 999
        self.assertEqual(first, base_nft({'nftables': [{'rule': rule}]}))


if __name__ == '__main__':
    unittest.main()
