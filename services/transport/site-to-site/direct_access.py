"""Local, strict existing-identity RouterOS access with bounded commands."""
import json
import os
from pathlib import Path
import re
import shlex

import paramiko

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / '.local/config/sstp-direct'
ERROR = re.compile(rb'(?im)^(failure:|syntax error|bad command name|bad parameter|expected end|invalid value|Script Error|not enough permissions|no such item|input does not match)')
SERIAL = {'fethiye': 'HM20B6QXS8H', 'nakhimova': 'HKM0BDXYG74'}


def private_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o077:
        raise ValueError('unsafe_private_file')
    return json.loads(path.read_text())


class RouterUnavailable(RuntimeError):
    def __init__(self, site, reason):
        self.reason = reason
        super().__init__('router_unavailable:' + site)


def connect(site, interactive=False):
    # Retry only the initial, read-only connection/identity handshake, never commands.
    for attempt in range(2):
        try:
            return _connect_once(site, interactive)
        except RouterUnavailable:
            if attempt == 1:
                raise


def _connect_once(site, interactive=False):
    if site not in SERIAL:
        raise ValueError('unknown_site')
    suffix = '+ct160w40h' if interactive else ''
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    proxy = None
    if site == 'fethiye':
        c.load_host_keys(str(ROOT / '.local/ssh/known_hosts_fethiye'))
        host, user = '192.168.68.117', 'admin'
        key = paramiko.RSAKey.from_private_key_file(str(ROOT / '.local/ssh/fethiye_admin_rsa'))
    else:
        c.load_host_keys(str(ROOT / '.local/ssh/known_hosts'))
        host, user = '192.168.88.1', 'codex'
        key = paramiko.PKey.from_path(ROOT / '.local/ssh/codex_mikrotik_20260704')
        cached = Path.home() / '.local/state/system-project/ssh/config'
        ssh_config = cached if cached.is_file() else ROOT / '.local/ssh/config'
        proxy = paramiko.ProxyCommand(shlex.join(['ssh', '-F', str(ssh_config),
            '-o', 'ClearAllForwardings=yes', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', 'PermitLocalCommand=no', 'timeweb', 'docker exec -i wg-relay nc -w 60 10.30.30.2 22']))
    try:
        if not c.get_host_keys().lookup(host):
            raise RuntimeError('router_host_key_not_pinned')
        c.connect(host, username=user + suffix, pkey=key, sock=proxy, allow_agent=False,
                  look_for_keys=False, timeout=10, banner_timeout=15, auth_timeout=15)
        c.get_transport().set_keepalive(0)
        if run(c, ':put [/system routerboard get serial-number]').decode().strip() != SERIAL[site]:
            raise RuntimeError('router_identity_mismatch')
        return c
    except Exception as exc:
        c.close()
        if proxy:
            proxy.close()
        if isinstance(exc, (paramiko.AuthenticationException, paramiko.BadHostKeyException)):
            raise RuntimeError('router_access_rejected:' + site) from None
        if isinstance(exc, (OSError, EOFError, paramiko.SSHException)):
            raise RouterUnavailable(site, 'timeout' if isinstance(exc, TimeoutError) else 'connection') from None
        raise RuntimeError('router_validation_failed:' + site) from None


def run(c, command):
    _, out, err = c.exec_command(command, timeout=35)
    data, errors = out.read(), err.read()
    if out.channel.recv_exit_status() or errors or ERROR.search(data) or len(data) > 8_000_000:
        raise RuntimeError('router_command_failed')
    return data


def get(c, expression):
    return json.loads(run(c, ':put [:serialize to=json ' + expression + ']'))


def rows(c, path):
    return get(c, '[' + path + ' print as-value]')


def value(c, path, selector, prop):
    return get(c, '[' + path + ' get ' + selector + ' ' + prop + ']')


def mutate(c, command):
    if run(c, command).strip():
        raise RuntimeError('unexpected_router_write_output')
