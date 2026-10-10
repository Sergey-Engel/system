"""Review only the additive Mac Mini FLEX delta; never accept unrelated drift."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

MANIFEST = Path('/opt/vpn-monitoring/guards/guard-manifest.json')
STATE = Path('/var/lib/vpn-uplink-guards/state.json')
EXPECTED = [
    {'priority': 184, 'src': 'all', 'fwmark': '0x41', 'table': '411'},
    {'priority': 185, 'src': 'all', 'fwmark': '0x41', 'action': 'prohibit'},
    {'priority': 243, 'src': '10.50.50.41', 'table': '414'},
    {'priority': 244, 'src': '10.50.50.41', 'action': 'prohibit'},
]


def run(*args):
    return subprocess.check_output(args, text=True, timeout=15).strip()


def audit():
    raw = MANIFEST.read_bytes()
    manifest = json.loads(raw)
    state = json.loads(STATE.read_text())
    assert state['manifest_sha256'] == hashlib.sha256(raw).hexdigest()
    pid = manifest['target']['container']['State']['Pid']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == manifest['target']['boot']
    assert run('readlink', f'/proc/{pid}/ns/net') == manifest['target']['namespace']
    live_container = json.loads(run('docker', 'inspect', 'wg-relay'))[0]
    expected_container = manifest['target']['container']
    assert live_container['Id'] == expected_container['Id']
    assert live_container['State']['Pid'] == pid

    def ns(*args):
        return run('nsenter', '-t', str(pid), '-n', *args)

    rules = json.loads(ns('ip', '-j', '-4', 'rule', 'show'))
    routes = json.loads(ns('ip', '-j', '-4', 'route', 'show', 'table', 'all'))
    addresses = json.loads(ns('ip', '-j', '-4', 'address', 'show'))
    links = [{key: item[key] for key in ('ifindex', 'ifname', 'flags', 'mtu')} |
             {'addr_info': [{key: addr[key] for key in ('local', 'prefixlen')}
                            for addr in item['addr_info']]} for item in addresses]
    baseline = manifest['baseline']
    live_other = dict(links=links,
                      peers={'fornex': ns('wg', 'show', 'wg1', 'allowed-ips'),
                             'cenuta': ns('wg', 'show', 'wg-up-cenuta', 'allowed-ips')},
                      filter=ns('iptables', '-S'), nat=ns('iptables', '-t', 'nat', '-S'),
                      mangle=ns('iptables', '-t', 'mangle', '-S'))
    assert live_other == {k: v for k, v in baseline.items() if k not in ('rules', 'routes')}, 'unrelated snapshot drift'
    priorities = {r['priority'] for r in EXPECTED}
    assert [r for r in rules if r['priority'] in priorities] == EXPECTED, 'unexpected new rules'
    assert [r for r in rules if r['priority'] not in priorities and
            not 31000 <= r['priority'] <= 31021] == baseline['rules'], 'unrelated RPDB drift'
    assert [r for r in rules if 31000 <= r['priority'] <= 31021] == manifest['expected_rules'], 'owned guard drift'
    flex_tables = {'410', '412', '414'}
    for table in flex_tables:
        found = [r for r in routes if r.get('table') == table]
        assert found in ([{'dst': 'default', 'gateway': '10.20.0.2', 'dev': 'wg1', 'table': table, 'flags': []}],
                         [{'dst': 'default', 'dev': 'wg-up-cenuta', 'table': table, 'scope': 'link', 'flags': []}]), 'unexpected FLEX route'
    canonical = lambda value: sorted((json.dumps(r, sort_keys=True) for r in value))
    assert canonical([r for r in routes if r.get('table') not in flex_tables]) == canonical(
        [r for r in baseline['routes'] if r.get('table') not in flex_tables]), 'unrelated route drift'
    candidate = json.loads(raw)
    candidate['baseline']['rules'] = [r for r in rules if not 31000 <= r['priority'] <= 31021]
    candidate['baseline']['routes'] = baseline['routes'] + [r for r in routes if r.get('table') == '414']
    return candidate, state


def write_atomic(path, contents):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.macmini-manifest-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply(stage):
    helpers = [Path('/opt/vpn-monitoring/pilot/candidate/guardctl-batch.sh')]
    config_path = Path('/opt/vpn-monitoring/pilot/config.json')
    replacements = {}
    for helper in helpers:
        old = helper.read_text()
        expected = old.replace('["410","412"]', '["410","412","414"]')
        expected = expected.replace('and .table!="412"', 'and .table!="412" and .table!="414"')
        proposed = (stage / helper.name).read_text()
        assert proposed == expected and proposed != old, 'unreviewed helper delta'
        replacements[helper] = proposed.encode()
    config = json.loads(config_path.read_text())
    assert config['helper_sha256']['guardctl-batch.sh'] == hashlib.sha256(helpers[0].read_bytes()).hexdigest()
    backup = Path('/var/backups') / ('vpn-monitoring-manifest-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    paths = [MANIFEST, STATE, config_path, *helpers]
    for path in paths:
        target = backup / path.relative_to('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    subprocess.run(['systemctl', 'stop', 'vpn-uplink-pilot.service'], check=True)
    try:
        candidate, state = audit()
        contents = (json.dumps(candidate, indent=2) + '\n').encode()
        state['manifest_sha256'] = hashlib.sha256(contents).hexdigest()
        state['generation'] += 1
        config['helper_sha256']['guardctl-batch.sh'] = hashlib.sha256(replacements[helpers[0]]).hexdigest()
        replacements.update({MANIFEST: contents,
                             STATE: (json.dumps(state, indent=2) + '\n').encode(),
                             config_path: (json.dumps(config, indent=2) + '\n').encode()})
        for path, data in replacements.items():
            write_atomic(path, data)
        subprocess.run(['bash', str(helpers[0]), str(MANIFEST), 'check'], check=True)
    except Exception:
        for path in paths:
            shutil.copy2(backup / path.relative_to('/'), path)
        raise
    finally:
        subprocess.run(['systemctl', 'start', 'vpn-uplink-pilot.service'], check=True)
    subprocess.run(['systemctl', 'restart', 'vpn-uplink-exporter.service'], check=True)
    print(json.dumps({'result': 'APPLIED', 'generation': state['generation'], 'backup': str(backup)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply-stage', type=Path)
    args = parser.parse_args()
    if args.apply_stage:
        apply(args.apply_stage)
    else:
        candidate, state = audit()
        print(json.dumps({'result': 'REVIEWED_MACMINI_DELTA', 'generation': state['generation'],
                          'new_rules': EXPECTED, 'new_route_table': '414'}))
