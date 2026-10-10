"""Retired initial preparation; shared helpers remain available for build/verify."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'timeweb-reality'))

ROOT = Path(__file__).resolve().parent

def retired(entrypoint):
    raise SystemExit(
        f'RETIRED: {entrypoint} is a completed one-shot operation, kept for reference only. '
        'The current AWG31 release has 11 peers; historical scripts must not regenerate it. '
        'AWG2 has been removed; this is not an AWG2 rollback or a current backup tool. '
        'Review README.md, take a fresh backup of the current release, and review a scoped '
        'runtime/persistent/credentials/fleet/exports diff before writing a new change procedure. '
        'No bypass flag is supported.'
    )

# Load remote helpers only for explicit build/verify calls, never for a retired gate.
def call(host, command, data=None, timeout=60):
    from stage8_cenuta import call as remote_call
    return remote_call(host, command, data, timeout=timeout)

def put(path, data):
    from stage8_cenuta import put as write_artifact
    return write_artifact(path, data)

def ssh_args(host):
    from run_backup import ssh_args as remote_args
    return remote_args(host)

def main():
    retired('prepare.py')
    # Historical implementation below is intentionally unreachable.
    os.umask(0o077)
    ROOT.chmod(0o700)
    backup = ROOT / 'backup'
    if '--sources' in sys.argv:
        fetch(backup)
        return
    backup.mkdir(mode=0o700, exist_ok=False)
    for name, command in {
        'containers.json': 'docker inspect amnezia-awg2 wg-exit',
        'networks.json': 'docker network inspect bridge amnezia-dns-net',
        'firewall.v4': 'iptables-save',
        'routes.txt': 'ip route show table all',
        'awg.tar': 'docker exec amnezia-awg2 tar -C /opt/amnezia -cf - awg start.sh',
    }.items():
        put(backup / name, call('fornex', command))
    with (backup / 'container.tar').open('wb') as out:
        subprocess.run(ssh_args('fornex') + ['docker export amnezia-awg2'], stdout=out, check=True, timeout=240)
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in backup.iterdir()}
    put(backup / 'sha256.json', json.dumps(manifest, indent=2))
    fetch(backup)

def fetch(backup):
    retired('prepare.py fetch')
    source = ROOT / 'source'
    source.mkdir(mode=0o700, exist_ok=True)
    for path in ['client/server_scripts/awg/Dockerfile', 'client/server_scripts/awg/start.sh',
                 'client/server_scripts/awg/template.conf', 'client/server_scripts/awg/configure_container.sh',
                 'client/core/utils/constants/protocolConstants.h']:
        data = subprocess.check_output(['curl', '-fsSL', '--max-time', '30', 'https://raw.githubusercontent.com/amnezia-vpn/amnezia-client/5.0.1.5/' + path])
        put(source / path.rsplit('/', 1)[1], data)
    print('Legacy backup complete:', sum(p.stat().st_size for p in backup.iterdir()), 'bytes', flush=True)
    print(call('fornex', 'docker pull amneziavpn/amneziawg-go:latest', timeout=180).decode(), flush=True)
    image = json.loads(call('fornex', 'docker image inspect amneziavpn/amneziawg-go:latest'))[0]
    put(ROOT / 'base-image.json', json.dumps(image, indent=2))
    print('Pinned base:', image['RepoDigests'], flush=True)
    print(call('fornex', 'docker run --rm --entrypoint amneziawg-go ' + image['Id'] + ' --version').decode())

if __name__ == '__main__':
    main()
