"""Install and control only the local direct-SSTP panel LaunchAgents."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from private_store import write_private
from setup_mac import materialize_ssh_cache

LABELS = ('com.sergey.sstp-panel-forward', 'com.sergey.sstp-panel')
AGENTS = Path.home() / 'Library/LaunchAgents'
RUNTIME = ROOT / '.local/runtime/sstp-panel'


def control(action):
    os.umask(0o077)
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    domain = 'gui/' + str(os.getuid())
    if action == 'install':
        if not (ROOT / '.local/config/sstp-direct/config.json').exists():
            raise ValueError('Permanent direct configuration is missing')
        ssh_config = materialize_ssh_cache()
        commands = [
            ['/usr/bin/ssh', '-F', str(ssh_config), '-N', '-T',
             '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=10',
             '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
             '-L', '127.0.0.1:19119:127.0.0.1:19108', 'timeweb'],
            [str(ROOT / '.venv/bin/python'), '-B', str(Path(__file__).with_name('direct_panel.py'))],
        ]
        for label, args in zip(LABELS, commands):
            path = AGENTS / (label + '.plist')
            if path.exists():
                raise ValueError('Existing local agent requires explicit reviewed update')
            value = dict(Label=label, ProgramArguments=args, RunAtLoad=True, KeepAlive=True, Umask=0o077,
                         ThrottleInterval=20, WorkingDirectory=str(ROOT),
                         StandardOutPath=str(RUNTIME / (label + '.log')),
                         StandardErrorPath=str(RUNTIME / (label + '.error.log')))
            write_private(path, plistlib.dumps(value))
            subprocess.run(['launchctl', 'bootstrap', domain, str(path)], check=True, capture_output=True)
    elif action == 'start':
        for label in LABELS:
            path = AGENTS / (label + '.plist')
            result = subprocess.run(['launchctl', 'print', domain + '/' + label], capture_output=True)
            if result.returncode:
                subprocess.run(['launchctl', 'bootstrap', domain, str(path)], check=True, capture_output=True)
        subprocess.run(['open', 'http://127.0.0.1:19118/'], check=True)
    elif action == 'stop':
        for label in reversed(LABELS):
            subprocess.run(['launchctl', 'bootout', domain + '/' + label], capture_output=True)
    elif action == 'status':
        for label in LABELS:
            result = subprocess.run(['launchctl', 'print', domain + '/' + label], capture_output=True)
            print(label + ': ' + ('loaded' if result.returncode == 0 else 'stopped'))
    elif action == 'logs':
        for path in sorted(RUNTIME.glob('*.log')):
            print(path.name)
            print(path.read_text()[-4000:])
    else:
        raise ValueError('Unknown local panel action')


if __name__ == '__main__':
    control(sys.argv[1] if len(sys.argv) > 1 else 'start')
