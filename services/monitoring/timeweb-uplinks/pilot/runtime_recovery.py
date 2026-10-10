"""Versioned, fail-closed recovery of reviewed wg-relay runtime policy."""
import argparse
from collections import Counter
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import rebind_after_reboot as rebind

ROOT = Path('/opt/vpn-runtime-recovery')
POLICY = ROOT / 'policy.json'
STATE = Path('/var/lib/vpn-runtime-recovery/state.json')
CONTROLLER = '/usr/local/sbin/timeweb-flex-macbook'
FLEET = '/usr/local/sbin/timeweb-flex-fleet'
BASE_RULES = {180, 181, 190}
FLEX_RULES = {184, 185, 186, 187, 188, 189, 239, 240, 241, 242, 243, 244}
ENDPOINTS = {'89.252.153.129', '103.75.126.143'}
FORWARD = [
    '-A FORWARD -s 10.10.100.0/24 -o eth0 -j ACCEPT',
    '-A FORWARD -i wg0 -o wg1 -j ACCEPT',
    '-A FORWARD -i wg1 -o wg0 -j ACCEPT',
]
NAT = [
    '-A POSTROUTING -s 10.10.100.0/24 -o eth0 -j MASQUERADE',
    '-A POSTROUTING -s 10.10.10.0/24 -o wg1 -j MASQUERADE',
]


def run(*args, input_text=None, timeout=60):
    return subprocess.check_output(args, input=input_text, text=True, timeout=timeout).strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def container():
    value = json.loads(run('docker', 'inspect', 'wg-relay'))[0]
    assert value['State']['Running'], 'wg-relay is not running'
    return value


def identity(value):
    pid = value['State']['Pid']
    return {'id': value['Id'], 'image': value['Image'], 'pid': pid,
            'started': value['State']['StartedAt'],
            'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'namespace': run('readlink', f'/proc/{pid}/ns/net')}


def namespace(value):
    pid = str(value['State']['Pid'])
    token = identity(value)

    def ns(*args, input_text=None):
        assert identity(container()) == token, 'namespace changed during recovery'
        return run('nsenter', '-t', pid, '-n', *args, input_text=input_text)
    return ns


def snapshot(ns):
    links = json.loads(ns('ip', '-j', '-4', 'address', 'show'))
    return {
        'rules': json.loads(ns('ip', '-j', '-4', 'rule', 'show')),
        'routes': json.loads(ns('ip', '-j', '-4', 'route', 'show', 'table', 'all')),
        'links': [{k: link[k] for k in ('ifindex', 'ifname', 'flags', 'mtu')} |
                  {'addr_info': [{k: addr[k] for k in ('local', 'prefixlen')}
                                 for addr in link['addr_info']]} for link in links],
        'peers': {'fornex': ns('wg', 'show', 'wg1', 'allowed-ips'),
                  'cenuta': ns('wg', 'show', 'wg-up-cenuta', 'allowed-ips')},
        'filter': ns('iptables', '-S'), 'nat': ns('iptables', '-t', 'nat', '-S'),
        'mangle': ns('iptables', '-t', 'mangle', '-S'),
    }


def base_nft(document):
    """Ignore counters/handles and only FLEX-owned, controller-generated marks."""
    result = []
    for entry in document['nftables']:
        if 'metainfo' in entry:
            continue
        item = copy.deepcopy(entry)
        kind, value = next(iter(item.items()))
        assert value.get('family') == 'inet', 'unexpected nft family'
        assert value.get('table', value.get('name') if kind == 'table' else None) == 'ru_bth'
        if kind == 'rule' and value.get('comment') in {
                'timeweb-flex-macbook-ru', 'timeweb-flex-iphone12-ru', 'timeweb-flex-macmini-ru'}:
            continue
        value.pop('handle', None)
        if kind == 'rule':
            for expression in value['expr']:
                if 'counter' in expression:
                    expression['counter'] = {'packets': 0, 'bytes': 0}
        result.append(item)
    return result


def fingerprints():
    paths = list(Path('/opt/wg/config/wg_confs').glob('*.conf')) + [
        Path('/opt/wg/docker-compose.yml'),
        Path('/opt/wg-router/state/clients.tsv'),
        Path('/opt/wg-router/state/ru_bth_clients.tsv'),
        Path('/opt/wg-router/state/legacy_ru_bth_clients.tsv'),
        Path('/opt/wg-router/state/ru_networks_v4.txt'),
        Path('/opt/timeweb-reality/bth-recovery/contract.json'),
        Path(CONTROLLER), Path(FLEET),
    ]
    result = {}
    for path in paths:
        raw = path.read_bytes()
        # Transport controllers own these two endpoint values, not topology.
        if path.name in ('wg1.conf', 'wg-up-cenuta.conf'):
            raw = '\n'.join('Endpoint = TRANSPORT_CONTROLLER' if line.strip().startswith('Endpoint')
                            else line for line in raw.decode().splitlines()).encode()
        result[str(path)] = hashlib.sha256(raw).hexdigest()
    return result


def validate_partial(policy, current):
    """Permit only the specific restart losses and owned FLEX quarantines."""
    expected = copy.deepcopy(policy['baseline'])
    current = copy.deepcopy(current)
    own = [rule for rule in current['rules'] if 31000 <= rule['priority'] <= 31021]
    assert own in ([], policy['monitor_rules']), 'foreign/partial monitoring rules'
    current['rules'] = [rule for rule in current['rules'] if not 31000 <= rule['priority'] <= 31021]
    for rule in current['rules']:
        assert rule in expected['rules'], 'foreign RPDB rule'
    counts = lambda rules: Counter(json.dumps(rule, sort_keys=True) for rule in rules)
    assert not counts(current['rules']) - counts(expected['rules']), 'duplicate RPDB rule'
    missing = [rule for rule in expected['rules'] if rule not in current['rules']]
    assert all(rule['priority'] in BASE_RULES | FLEX_RULES for rule in missing), 'unexpected missing RPDB rule'
    current['rules'] = expected['rules']
    for address in ENDPOINTS:
        target = [route for route in expected['routes'] if route['dst'] == address]
        assert len(target) == 1, 'endpoint baseline missing'
        live = [route for route in current['routes'] if route['dst'] in (address, address + '/32')]
        assert live in ([], target), 'conflicting endpoint route'
        if not live:
            current['routes'] += target
    for key, rules in [('filter', FORWARD), ('nat', NAT)]:
        live_text, expected_text = current[key], expected[key]
        if key == 'nat':
            live_text = rebind.normalized({'links': [], 'routes': [], 'nat': live_text})['nat']
            expected_text = rebind.normalized({'links': [], 'routes': [], 'nat': expected_text})['nat']
        lines = live_text.splitlines()
        if key == 'filter':
            owned = {f'-A FORWARD -s {peer} -i wg-clients -j DROP' for peer in policy['peers']}
            assert sum(line in owned for line in lines) <= 256, 'too many quarantines'
            lines = [line for line in lines if line not in owned]
        assert all(lines.count(rule) == 1 for rule in rules), 'legacy rule missing/duplicated'
        previous = expected_text.splitlines()
        assert [x for x in lines if x not in rules] == [x for x in previous if x not in rules], 'foreign firewall drift'
        current[key] = expected[key]
    # FLEX routes are owned and verified by the per-device controllers later.
    current['routes'] = [route for route in current['routes'] if route.get('table') not in ('410', '412', '414')]
    expected['routes'] = [route for route in expected['routes'] if route.get('table') not in ('410', '412', '414')]
    direct = [route for route in expected['routes'] if route.get('table') == '411']
    live_direct = [route for route in current['routes'] if route.get('table') == '411']
    assert live_direct in ([], direct), 'RU-direct route drift'
    if not live_direct:
        current['routes'] += direct
    assert rebind.normalized(current) == rebind.normalized(expected), 'unreviewed network-policy drift'


def restore_base(policy, ns, current):
    validate_partial(policy, current)
    tables = json.loads(ns('nft', '-j', 'list', 'tables'))['nftables']
    present = any(x.get('table', {}).get('family') == 'inet' and
                  x.get('table', {}).get('name') == 'ru_bth' for x in tables)
    if present:
        assert base_nft(json.loads(ns('nft', '-j', 'list', 'table', 'inet', 'ru_bth'))) == policy['nft'], 'RU policy drift'
    else:
        document = json.dumps({'nftables': [{'add': x} for x in policy['nft']]})
        ns('nft', '-c', '-j', '-f', '-', input_text=document)
        ns('nft', '-j', '-f', '-', input_text=document)
    for rule in policy['baseline']['rules']:
        if rule['priority'] in BASE_RULES and rule not in current['rules']:
            selector = ['to', rule['dst'] + '/' + str(rule['dstlen'])] if 'dst' in rule else ['fwmark', rule['fwmark']]
            ns('ip', 'rule', 'add', 'priority', str(rule['priority']), *selector, 'lookup', rule['table'])
    for route in policy['baseline']['routes']:
        if route['dst'] in ENDPOINTS and route not in current['routes']:
            ns('ip', 'route', 'add', route['dst'] + '/32', 'via', route['gateway'], 'dev', route['dev'])
    for key, rules, chain, offset in [('filter', FORWARD, 'FORWARD', 1),
                                      ('nat', NAT, 'POSTROUTING', 2)]:
        if current[key] == policy['baseline'][key]:
            continue
        prefix = ['iptables'] + (['-t', 'nat'] if key == 'nat' else [])
        for rule in rules:
            ns(*prefix, '-D', *rule.split()[1:])
        for index, rule in enumerate(rules, offset):
            ns(*prefix, '-I', chain, str(index), *rule.split()[2:])


def fleet_ready():
    fleet = json.loads(run(FLEET, 'status'))
    assert fleet['counts']['route_ready'] == fleet['counts']['total'] == len(fleet['devices']) > 0
    return fleet


def restore_transports():
    saved = json.loads(Path('/var/lib/vpn-uplink-pilot/transport-state.json').read_text())
    assert saved['version'] == 1
    for upstream in ('fornex', 'cenuta'):
        mode = saved['upstreams'][upstream]['mode']
        assert mode in ('native', 'backup'), 'unknown selected transport'
        if mode == 'backup':
            run('systemctl', 'start', f'wstunnel-timeweb-{upstream}-wg-fallback.service',
                f'wstunnel-timeweb-{upstream}-xray-fallback.service')
        status = dict(token.split('=', 1) for token in run(
            f'/usr/local/sbin/timeweb-{upstream}-wg-transport', 'status').split())
        assert status['mode'] == mode, 'saved/observed transport mismatch'
    current = json.loads(Path('/var/lib/vpn-uplink-pilot/transport-state.json').read_text())
    assert current == saved, 'transport changed during recovery'


def publish():
    value = container()
    run('python3', str(ROOT / 'rebind_after_reboot.py'), '--image', value['Image'])
    fleet = fleet_ready()
    manifest = json.loads(rebind.MANIFEST.read_text())
    ns = namespace(value)
    baseline = rebind.compare(manifest, snapshot(ns))
    policy = {'schema': 1, 'container_id': value['Id'], 'image': value['Image'],
              'bindings': fingerprints(), 'baseline': baseline,
              'nft': base_nft(json.loads(ns('nft', '-j', 'list', 'table', 'inet', 'ru_bth'))),
              'devices': sorted(fleet['devices']),
              'peers': sorted(device['peer'] for device in fleet['devices'].values()),
              'monitor_rules': manifest['expected_rules'], 'published': int(time.time())}
    assert identity(container()) == identity(value), 'container changed during publication'
    if POLICY.exists():
        atomic(ROOT / 'previous-policy.json', json.loads(POLICY.read_text()))
    atomic(POLICY, policy)
    atomic(STATE, {'identity': identity(value), 'policy_hash': digest(policy), 'status': 'ready'})
    print('RUNTIME_POLICY_PUBLISHED ' + digest(policy))


def recover(force=False):
    policy = json.loads(POLICY.read_text())
    value = container()
    assert value['Id'] == policy['container_id'] and value['Image'] == policy['image'], 'container/image not approved'
    assert fingerprints() == policy['bindings'], 'configuration changed: publish reviewed policy first'
    token = identity(value)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not force and state.get('identity') == token and state.get('policy_hash') == digest(policy) and state.get('status') == 'ready':
        return
    required_links = {link['ifname'] for link in policy['baseline']['links']}
    for _ in range(60):
        assert identity(container()) == token, 'namespace changed during startup'
        names = {link['ifname'] for link in json.loads(run(
            'nsenter', '-t', str(value['State']['Pid']), '-n', 'ip', '-j', 'link', 'show'))}
        if required_links <= names:
            break
        time.sleep(1)
    else:
        raise RuntimeError('WireGuard startup readiness timeout')
    devices = policy['devices']
    services = [f'timeweb-flex-{device}.service' for device in devices] + ['bth-recovery.service']
    timers = [f'timeweb-flex-{device}.timer' for device in devices] + ['bth-recovery.timer']
    # Timers and collectors must not race a multi-stage namespace recovery.
    run('systemctl', 'stop', *timers)
    run('systemctl', 'stop', *services, 'vpn-uplink-pilot.service', 'vpn-uplink-console.service')
    atomic(STATE, {'identity': token, 'policy_hash': digest(policy), 'status': 'recovering'})
    try:
        ns = namespace(value)
        current = snapshot(ns)
        restore_base(policy, ns, current)
        restore_transports()
        for device in devices:
            run(CONTROLLER, '--device', device, 'reconcile')
        run('bash', '/opt/timeweb-reality/bth-recovery/bth_recover.sh')
        fleet = fleet_ready()
        assert sorted(fleet['devices']) == devices, 'fleet inventory drift'
        run('python3', str(ROOT / 'rebind_after_reboot.py'), '--image', policy['image'], '--apply')
        assert identity(container()) == token, 'container changed during recovery'
        atomic(STATE, {'identity': token, 'policy_hash': digest(policy), 'status': 'ready', 'recovered': int(time.time())})
        run('systemctl', 'start', '--no-block', *timers, 'vpn-uplink-pilot.service',
            'vpn-uplink-exporter.service', 'vpn-uplink-console.service')
        print('RUNTIME_RECOVERY_VERIFIED')
    except Exception:
        atomic(STATE, {'identity': token, 'policy_hash': digest(policy), 'status': 'failed'})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['publish', 'recover', 'check'])
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    with open('/run/lock/timeweb-runtime-recovery.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'publish':
            publish()
        elif args.command == 'recover':
            recover(args.force)
        else:
            policy = json.loads(POLICY.read_text())
            assert fingerprints() == policy['bindings'], 'configuration binding drift'
            ns = namespace(container())
            assert base_nft(json.loads(ns('nft', '-j', 'list', 'table', 'inet', 'ru_bth'))) == policy['nft']
            rebind.compare(json.loads(rebind.MANIFEST.read_text()), snapshot(ns))
            run('bash', '/opt/timeweb-reality/bth-recovery/bth_recover.sh', '--check')
            fleet_ready()
            print('RUNTIME_RECOVERY_CHECK_PASSED')


if __name__ == '__main__':
    main()
