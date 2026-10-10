"""Rebind monitoring after a reviewed reboot; refuse any network-policy drift."""
import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

MANIFEST = Path('/opt/vpn-monitoring/guards/guard-manifest.json')
STATE = Path('/var/lib/vpn-uplink-guards/state.json')
HELPER = '/opt/vpn-monitoring/pilot/candidate/guardctl-batch.sh'


def run(*args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def normalized(snapshot):
    value = copy.deepcopy(snapshot)
    value['links'] = sorted(
        [{k: v for k, v in link.items() if k != 'ifindex'} for link in value['links']],
        key=lambda link: link['ifname'])
    value['routes'] = sorted(
        [route for route in value['routes'] if route.get('table') not in ('410', '412', '414')],
        key=lambda route: json.dumps(route, sort_keys=True))
    if 'nat' in value:
        lines = value['nat'].splitlines()
        for protocol in ('tcp', 'udp'):
            dnat = re.compile(rf'-A DOCKER_OUTPUT -d 127\.0\.0\.11/32 -p {protocol} -m {protocol} --dport 53 -j DNAT --to-destination 127\.0\.0\.11:(\d+)')
            snat = re.compile(rf'-A DOCKER_POSTROUTING -s 127\.0\.0\.11/32 -p {protocol} -m {protocol} --sport (\d+) -j SNAT --to-source :53')
            first = [(i, dnat.fullmatch(line)) for i, line in enumerate(lines) if dnat.fullmatch(line)]
            second = [(i, snat.fullmatch(line)) for i, line in enumerate(lines) if snat.fullmatch(line)]
            assert len(first) == len(second) == 1, 'Docker DNS rule shape drift'
            port = first[0][1].group(1)
            assert port == second[0][1].group(1) and 1024 <= int(port) <= 65535, 'Docker DNS port mismatch'
            lines[first[0][0]] = lines[first[0][0]].replace('127.0.0.11:' + port, '127.0.0.11:EPHEMERAL')
            lines[second[0][0]] = lines[second[0][0]].replace('--sport ' + port, '--sport EPHEMERAL')
        value['nat'] = '\n'.join(lines)
    return value


def compare(manifest, snapshot):
    owned = [rule for rule in snapshot['rules'] if 31000 <= rule['priority'] <= 31021]
    assert owned in ([], manifest['expected_rules']), 'foreign/partial monitoring rules'
    baseline = copy.deepcopy(snapshot)
    baseline['rules'] = [rule for rule in baseline['rules'] if not 31000 <= rule['priority'] <= 31021]
    for table in ('410', '412', '414'):
        routes = [route for route in baseline['routes'] if route.get('table') == table]
        assert routes in ([{'dst': 'default', 'gateway': '10.20.0.2', 'dev': 'wg1',
                            'table': table, 'flags': []}],
                          [{'dst': 'default', 'dev': 'wg-up-cenuta', 'table': table,
                            'scope': 'link', 'flags': []}]), 'unexpected FLEX route'
    current, previous = normalized(baseline), normalized(manifest['baseline'])
    changed = [key for key in set(current) | set(previous) if current.get(key) != previous.get(key)]
    assert not changed, 'network-policy drift: ' + ','.join(sorted(changed))
    return baseline


def write(path, data):
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.reboot-rebind-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        assert subprocess.run(['systemctl', 'is-active', '--quiet', 'vpn-uplink-pilot.service']).returncode != 0
    raw = MANIFEST.read_bytes()
    manifest = json.loads(raw)
    state = json.loads(STATE.read_text())
    assert state['manifest_sha256'] == hashlib.sha256(raw).hexdigest(), 'ownership mismatch'
    container = json.loads(run('docker', 'inspect', 'wg-relay'))[0]
    assert container['Id'] == manifest['target']['container']['Id'], 'container recreated'
    assert container['Image'] == args.image, 'image changed'
    assert container['State']['Running'] is True
    pid = container['State']['Pid']

    def ns(*command):
        return run('nsenter', '-t', str(pid), '-n', *command)

    links = json.loads(ns('ip', '-j', '-4', 'address', 'show'))
    snapshot = {
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
    baseline = compare(manifest, snapshot)
    run('bash', '/opt/timeweb-reality/bth-recovery/bth_recover.sh', '--check')
    fleet = json.loads(run('/usr/local/sbin/timeweb-flex-fleet', 'status'))
    assert fleet['counts']['route_ready'] == fleet['counts']['total'] == len(fleet['devices']) > 0
    current = json.loads(run('docker', 'inspect', 'wg-relay'))[0]
    assert current['State']['Pid'] == pid and current['State']['StartedAt'] == container['State']['StartedAt']
    if not args.apply:
        print('REBOOT_REBIND_CHECK_PASSED')
        return
    backup = Path('/var/backups') / ('monitoring-rebind-' + run('date', '-u', '+%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    for path in (MANIFEST, STATE):
        (backup / path.name).write_bytes(path.read_bytes())
        (backup / path.name).chmod(0o600)
    manifest['baseline'] = baseline
    manifest['target'].update(
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        namespace=run('readlink', f'/proc/{pid}/ns/net'),
        start=Path(f'/proc/{pid}/stat').read_text().split()[21],
        container={'Id': container['Id'], 'State': {key: container['State'][key]
                   for key in ('Pid', 'StartedAt', 'Running')}})
    contents = (json.dumps(manifest, indent=2) + '\n').encode()
    state.update(manifest_sha256=hashlib.sha256(contents).hexdigest(),
                 generation=state['generation'] + 1, status='rebound')
    write(MANIFEST, contents)
    write(STATE, (json.dumps(state, indent=2) + '\n').encode())
    run('bash', HELPER, str(MANIFEST), 'apply')
    print(run('bash', HELPER, str(MANIFEST), 'check'))
    print(json.dumps({'backup': str(backup), 'result': 'REBOUND'}))


if __name__ == '__main__':
    main()
