"""Isolated direct WG diagnostics: passive header logs, never TimeWeb edits."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("forward_trial", Path(__file__).with_name("forward_trial.py"))
f = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(f)
OWNER = "s2s-direct-diag-20261018"
IFACE = "wg-direct-diag"
SITES, NETWORK = f.SITES, f.NETWORK
quote, public_ip, public_key = f.quote, f.public_ip, f.public_key
remote_site, safe_mode_confirmed = f.remote_site, f.safe_mode_confirmed


def assert_free(snapshot):
    f.assert_free(snapshot)
    for rows in snapshot.values():
        if any(r.get("name") in (IFACE, OWNER) or r.get("comment", "").startswith(OWNER) for r in rows):
            raise ValueError("diagnostic_namespace_occupied")
    if any(r.get("action") not in (None, "passthrough") for r in snapshot.get("/ip firewall raw", [])):
        raise ValueError("raw_chain_requires_separate_review")


def _owned(command):
    return command.replace(f.OWNER, OWNER).replace(f.IFACE, IFACE)


def stage_commands(site, other_public_ip):
    commands = [_owned(c) for c in f.stage_commands(site, other_public_ip)]
    tag = "N" if site == "nakhimova" else "F"
    port = SITES[site][2]
    commands[-2] += f' log=yes log-prefix="DD-IN{tag} "'
    commands.extend([
        f'/ip firewall raw add chain=prerouting action=passthrough protocol=udp dst-port={port} limit=10/1s,20:packet log=yes log-prefix="DD-RX{tag} " comment="{OWNER}:outer-rx"',
        f'/ip firewall mangle add chain=postrouting action=passthrough protocol=udp src-port={port} limit=10/1s,20:packet log=yes log-prefix="DD-TX{tag} " comment="{OWNER}:outer-tx"',
    ])
    return commands


def peer_command(site, key, endpoint):
    return _owned(f.peer_command(site, key, endpoint))


def ping_command(site, size=56):
    return _owned(f.ping_command(site, size))


def cleanup_commands():
    return [_owned(c) for c in f.cleanup_commands()] + [
        f'/ip firewall raw remove [find where comment="{OWNER}:outer-rx"]',
        f'/ip firewall mangle remove [find where comment="{OWNER}:outer-tx"]',
    ]
