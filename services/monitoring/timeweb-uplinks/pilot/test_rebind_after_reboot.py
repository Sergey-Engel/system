import copy
import unittest

from rebind_after_reboot import compare, normalized


class RebindTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            'rules': [{'priority': 0, 'table': 'local'}],
            'routes': [{'dst': 'default', 'dev': 'eth0'}] + [
                {'dst': 'default', 'dev': 'wg-up-cenuta', 'table': table,
                 'scope': 'link', 'flags': []} for table in ('410', '412', '414')],
            'links': [{'ifindex': 7, 'ifname': 'eth0', 'mtu': 1500}],
            'peers': {'fornex': 'peer'}, 'filter': 'policy',
        }
        self.manifest = {'baseline': self.baseline,
                         'expected_rules': [{'priority': 31000, 'action': 'prohibit'}]}

    def test_only_ifindex_can_change(self):
        live = copy.deepcopy(self.baseline)
        live['links'][0]['ifindex'] = 22
        compare(self.manifest, live)

    def test_own_rules_can_be_present(self):
        live = copy.deepcopy(self.baseline)
        live['rules'] += self.manifest['expected_rules']
        compare(self.manifest, live)

    def test_unknown_policy_drift_refused(self):
        for field in ('filter', 'peers', 'rules', 'routes', 'links'):
            live = copy.deepcopy(self.baseline)
            live[field] = 'foreign' if field == 'filter' else []
            with self.assertRaises(AssertionError):
                compare(self.manifest, live)

    def test_foreign_owned_rule_refused(self):
        live = copy.deepcopy(self.baseline)
        live['rules'].append({'priority': 31001, 'table': 'main'})
        with self.assertRaises(AssertionError):
            compare(self.manifest, live)

    def test_exact_docker_dns_port_pairs(self):
        nat = '\n'.join(line for proto in ('tcp', 'udp') for line in (
            f'-A DOCKER_OUTPUT -d 127.0.0.11/32 -p {proto} -m {proto} --dport 53 -j DNAT --to-destination 127.0.0.11:34567',
            f'-A DOCKER_POSTROUTING -s 127.0.0.11/32 -p {proto} -m {proto} --sport 34567 -j SNAT --to-source :53'))
        first = copy.deepcopy(self.baseline) | {'nat': nat}
        second = copy.deepcopy(first)
        second['nat'] = nat.replace('34567', '45678')
        self.assertEqual(normalized(first), normalized(second))
        second['nat'] = nat.replace('--sport 34567', '--sport 45678')
        with self.assertRaises(AssertionError):
            normalized(second)


if __name__ == '__main__':
    unittest.main()
