"""Retired eleven-device migration and AWG2 removal; reference only."""
import base64
import hashlib
import json
import re
import secrets
import subprocess
import tarfile
from prepare import ROOT, call, put, ssh_args, retired

NAMES = ['MacBook-Sergey', 'iPhone-Sergey', 'Mac-Mini-M4', 'iPad-Pro-Sergey',
         'iPad-9.7-Sergey', 'MacBook-M3-Sveta', 'iPhone-16-Sveta', 'iPad-9.7-Sveta',
         'DigitalRazor-PC', 'Engel-Samsung-Pad', 'Win-Orekhovo']
REMOTE = '/opt/fornex-awg31/'

def sync(filename):
    retired('expand_fleet.py sync')
    call('fornex', "docker exec fornex-awg31 bash -c 'set -euo pipefail; awg syncconf awg0 <(awg-quick strip " + REMOTE + filename + ")'")

def main():
    retired('expand_fleet.py')
    # Historical implementation below is intentionally unreachable.
    from prepare_stage3 import keypair
    archive = ROOT / 'retirement-backup'
    archive.mkdir(mode=0o700, exist_ok=False)
    all_before = json.loads(call('fornex', 'docker inspect $(docker ps -aq)'))
    put(archive / 'containers.json', json.dumps(all_before))
    legacy = next(x for x in all_before if x['Name'] == '/amnezia-awg2')
    assert legacy['Id'] == '1145ba70bf7135222e795c9a522a5a2426e7ff0a2577fed8d54b0e515a881b8f'
    before = call('fornex', 'cat ' + REMOTE + 'awg0.conf')
    assert before == (ROOT / 'release/awg0.conf').read_bytes()
    put(archive / 'awg31.before.conf', before)
    put(archive / 'credentials.before.json', (ROOT / 'credentials.json').read_bytes())
    put(archive / 'awg2.tar', call('fornex', 'docker exec ' + legacy['Id'] + ' tar -C /opt/amnezia -cf - awg start.sh'))
    with (archive / 'container.tar').open('wb') as f:
        subprocess.run(ssh_args('fornex') + ['docker export ' + legacy['Id']], stdout=f, check=True, timeout=240)
    with tarfile.open(archive / 'container.tar') as t:
        assert any(m.name.endswith('/awg0.conf') for m in t.getmembers())
    put(archive / 'sha256.json', json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in archive.iterdir()}, indent=2))
    print('Fresh legacy backup complete', flush=True)
    keys = json.loads((ROOT / 'credentials.json').read_text())
    keys['clients'] = {n: keys['clients'][n] for n in NAMES[:2]}
    config = before.decode().rstrip() + '\n'
    template = (ROOT / 'Fornex-AWG31-MacBook-Sergey.conf').read_text()
    clients = ROOT.parent.parent / 'clients'
    generated = {}
    for i, name in enumerate(NAMES[2:], 4):
        k = dict(keypair(), psk=base64.b64encode(secrets.token_bytes(32)).decode())
        keys['clients'][name] = k
        conf = re.sub(r'^Address = .*$', f'Address = 10.83.1.{i}/32', template, flags=re.M)
        conf = re.sub(r'^PrivateKey = .*$', 'PrivateKey = ' + k['private'], conf, flags=re.M)
        conf = re.sub(r'^PresharedKey = .*$', 'PresharedKey = ' + k['psk'], conf, flags=re.M)
        filename = 'Fornex-AWG31-' + name + '.conf'
        assert not (clients / filename).exists()
        generated[filename] = conf
        config += '\n[Peer]\nPublicKey = ' + k['public'] + '\nPresharedKey = ' + k['psk'] + f'\nAllowedIPs = 10.83.1.{i}/32\n'
    expected = {k['public'] for k in keys['clients'].values()}
    assert len(expected) == 11
    # Staged files are in the same bind-mounted directory; no container restart.
    for filename, content in [('fleet-before.conf', before), ('fleet-next.conf', config.encode())]:
        call('fornex', 'sh -c "umask 077; cat > ' + REMOTE + filename + '"', content)
    try:
        sync('fleet-next.conf')
        assert set(call('fornex', 'docker exec fornex-awg31 awg show awg0 peers').decode().splitlines()) == expected
        call('fornex', 'mv ' + REMOTE + 'fleet-next.conf ' + REMOTE + 'awg0.conf')
        assert call('fornex', 'cat ' + REMOTE + 'awg0.conf') == config.encode()
    except Exception:
        sync('fleet-before.conf')
        call('fornex', 'cp ' + REMOTE + 'fleet-before.conf ' + REMOTE + 'awg0.conf')
        raise
    put(ROOT / 'credentials.json', json.dumps(keys, indent=2))
    put(ROOT / 'release/awg0.conf', config)
    for filename, content in generated.items():
        put(ROOT / filename, content)
        put(clients / filename, content)
    put(ROOT / 'fleet.json', json.dumps([{'device': n, 'file': 'Fornex-AWG31-' + n + '.conf',
        'address': re.search(r'^Address = (.+)$', (clients / ('Fornex-AWG31-' + n + '.conf')).read_text(), re.M)[1]} for n in NAMES], indent=2))
    print('Eleven peers installed; nine new profiles published; existing keys preserved', flush=True)
    call('fornex', 'docker stop --time 10 ' + legacy['Id'])
    call('fornex', 'docker rm ' + legacy['Id'])
    after = json.loads(call('fornex', 'docker inspect $(docker ps -aq)'))
    by_id = {x['Id']: x for x in after}
    assert legacy['Id'] not in by_id
    for old in all_before:
        if old['Id'] == legacy['Id']:
            continue
        assert old['Id'] in by_id
        assert old['State']['StartedAt'] == by_id[old['Id']]['State']['StartedAt']
        assert old['State']['Running'] == by_id[old['Id']]['State']['Running']
    assert '46055' not in call('fornex', 'ss -H -lun').decode()
    put(ROOT / 'retirement-status.json', json.dumps({'removed': legacy['Id'], 'peers': 11, 'other_containers_unchanged': True}, indent=2))
    test = ROOT / 'Fornex-AWG31-test.conf'
    if test.exists():
        test.rename(archive / test.name)
    put(ROOT / 'release-sha256.json', json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'release').iterdir()}, indent=2))
    print('AWG2 removed; UDP46055 closed; all other containers unchanged', flush=True)

if __name__ == '__main__':
    main()
