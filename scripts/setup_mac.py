#!/usr/bin/env python3
"""Install existing project identities and local monitoring bindings on a Mac."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess

from private_store import ROOT, load, local_root, materialize, write_private

HOST_INVENTORY = json.loads((ROOT / 'config/inventory/hosts.json').read_text())['hosts']
KEYS = {entry['id']: entry['key'] for entry in HOST_INVENTORY}
HOSTS = {entry['id']: (entry['hostname'], entry['user']) for entry in HOST_INVENTORY}


def render_ssh(private=None):
    private = private or local_root()
    blocks = []
    for host, (address, user) in HOSTS.items():
        aliases = {'timeweb': 'timeweb timeweb-console', 'nakhimova': 'mikrotik-nakhimova',
                   'orekhovo': 'mikrotik-orekhovo'}.get(host, host)
        trust = 'known_hosts_' + host if host in {'cenuta', 'orekhovo'} else 'known_hosts'
        lines = [f'Host {aliases}', f'  HostName {address}', f'  User {user}',
                 f'  IdentityFile "{private / "ssh" / KEYS[host]}"',
                 f'  UserKnownHostsFile "{private / "ssh" / trust}"',
                 '  IdentitiesOnly yes', '  BatchMode yes', '  StrictHostKeyChecking yes',
                 '  UpdateHostKeys no', '  PasswordAuthentication no',
                 '  KbdInteractiveAuthentication no', '  ForwardAgent no',
                 '  ConnectTimeout 10', '  ServerAliveInterval 15', '  ServerAliveCountMax 2']
        if host == 'orekhovo':
            lines.append('  PubkeyAcceptedAlgorithms +ssh-rsa')
        if host == 'nakhimova':
            proxy = shlex.join(['ssh', '-F', str(private / 'ssh/config'), '-o', 'ClearAllForwardings=yes',
                                '-o', 'PermitLocalCommand=no', 'timeweb',
                                'docker exec -i wg-relay nc -w 60 10.30.30.2 22'])
            lines.extend(['  HostKeyAlias 192.168.88.1', '  ProxyCommand ' + proxy])
        blocks.append('\n'.join(lines))
    blocks.append('Host timeweb-console\n  LocalForward 19118 127.0.0.1:19108\n  ExitOnForwardFailure yes\n  PermitLocalCommand no')
    write_private(private / 'ssh/config', ('\n\n'.join(blocks) + '\n').encode())


def materialize_ssh_cache():
    """launchd's direct SSH cannot read macOS-protected Documents on this Mac."""
    cache = Path.home() / '.local/state/system-project'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.chmod(0o700)
    for record in load()['files']:
        if record['path'].startswith('ssh/'):
            write_private(cache / record['path'], base64.b64decode(record['value'], validate=True))
    render_ssh(cache)
    return cache / 'ssh/config'


def install():
    if not (ROOT / '.venv/bin/python').exists():
        raise ValueError('Create .venv and install requirements before setup')
    uid = str(os.getuid())
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = local_root() / 'backups/local' / (stamp + '-integration-before')
    backup.mkdir(parents=True, mode=0o700)
    ssh_home = Path.home() / '.ssh'
    ssh_home.mkdir(mode=0o700, exist_ok=True)
    config = ssh_home / 'config'
    original = config.read_bytes() if config.exists() else b''
    write_private(backup / 'ssh-config.before', original)
    runtime_ssh_config = materialize_ssh_cache()
    include = b'Include ~/.ssh/system-project.conf\n'
    if include not in original:
        write_private(config, include + original)
    write_private(ssh_home / 'system-project.conf', ('Include "' + str(runtime_ssh_config) + '"\n').encode())
    bin_dir = Path.home() / '.local/bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / 'timeweb-vpn'
    if launcher.exists() or launcher.is_symlink():
        write_private(backup / 'launcher.before.json', json.dumps(dict(
            symlink=os.readlink(launcher) if launcher.is_symlink() else None,
            content=None if launcher.is_symlink() else launcher.read_text())).encode())
        launcher.unlink()
    launcher.symlink_to(ROOT / 'services/monitoring/timeweb-uplinks/pilot/open_console.sh')
    agent_dir = Path.home() / 'Library/LaunchAgents'
    logs = local_root() / 'runtime/logs'
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    probe_dir = ROOT / 'services/monitoring/vpn-connectivity/probe'
    specs = {
        'com.sergey.wg-peer-probe': [str(ROOT / '.venv/bin/python'), '-B', str(probe_dir / 'wg_peer_probe.py')],
        'com.sergey.vpn-host-probe': [str(ROOT / '.venv/bin/python'), '-B', str(probe_dir / 'host_probe.py')],
        'com.sergey.timeweb-uplink-tunnel': ['/usr/bin/ssh', '-F', str(runtime_ssh_config), '-N', '-T',
                                          '-o', 'ExitOnForwardFailure=yes', '-L', '127.0.0.1:19106:127.0.0.1:19106', 'timeweb'],
    }
    for label, args in specs.items():
        path = agent_dir / (label + '.plist')
        existing = plistlib.loads(path.read_bytes()) if path.exists() else {}
        if path.exists():
            write_private(backup / path.name, path.read_bytes())
        spec = dict(Label=label, ProgramArguments=args, RunAtLoad=True, KeepAlive=True, ThrottleInterval=30,
                    WorkingDirectory=str(ROOT), StandardOutPath=str(logs / (label + '.log')),
                    StandardErrorPath=str(logs / (label + '.error.log')))
        if 'EnvironmentVariables' in existing:
            spec['EnvironmentVariables'] = existing['EnvironmentVariables']
        subprocess.run(['launchctl', 'bootout', 'gui/' + uid, str(path)], capture_output=True)
        write_private(path, plistlib.dumps(spec))
        subprocess.run(['launchctl', 'bootstrap', 'gui/' + uid, str(path)], check=True, capture_output=True)
    print(json.dumps(dict(status='INSTALLED', agents=list(specs), rollback=str(backup.relative_to(ROOT)))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Switch local launcher, SSH include and LaunchAgents')
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(materialize()))
    render_ssh()
    if args.install:
        install()
