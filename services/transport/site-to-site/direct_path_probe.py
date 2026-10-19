"""Tuple-rotation and independent UDP control, only on isolated test objects."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("direct_diagnostics", Path(__file__).with_name("direct_diagnostics.py"))
d = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(d)
OWNER, IFACE = "s2s-direct-path-20261018", "wg-direct-path"
SITES = dict(d.SITES, nakhimova=(d.SITES['nakhimova'][0], '10.60.62.1', 51973))
NETWORK = d.NETWORK
quote, public_ip, public_key = d.quote, d.public_ip, d.public_key
remote_site, safe_mode_confirmed = d.remote_site, d.safe_mode_confirmed


def assert_free(snapshot):
    d.assert_free(snapshot)
    for path, rows in snapshot.items():
        for r in rows:
            if r.get('name') in (IFACE, OWNER) or r.get('comment', '').startswith(OWNER):
                raise ValueError('path_probe_namespace_occupied')
            if path == '/interface wireguard' and int(r.get('listen-port', 0)) in (51973, 51974):
                raise ValueError('path_probe_port_occupied')
            if path in ('/ip firewall filter', '/ip firewall nat', '/ip firewall raw', '/ip firewall mangle'):
                if any(str(r.get(p, '')) in ('51973', '51974') for p in ('src-port', 'dst-port', 'to-ports')):
                    raise ValueError('path_probe_rule_occupied')


def _owned(c):
    return c.replace(d.OWNER, OWNER).replace(d.IFACE, IFACE).replace('DD-', 'DP-')


def stage_commands(site, ip):
    commands = [_owned(c) for c in d.stage_commands(site, ip)]
    if site == 'nakhimova':
        commands = [c.replace('listen-port=51971', 'listen-port=51973')
                     .replace('dst-port=51971', 'dst-port=51973,51974')
                     .replace('src-port=51971', 'src-port=51973,51974') for c in commands]
    return commands


def peer_command(site, key, endpoint):
    return _owned(d.peer_command(site, key, endpoint))


def ping_command(site, size=56):
    return _owned(d.ping_command(site, size))


def cleanup_commands():
    return [_owned(c) for c in d.cleanup_commands()]


def rotate_command():
    return f'/interface wireguard set [find where name="{IFACE}" and comment="{OWNER}:interface"] listen-port=51974'
