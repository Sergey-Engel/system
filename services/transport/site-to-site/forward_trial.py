"""Oct18 isolated transport trial using the owner-created Deco UDP forward."""
import ipaddress
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("direct_trial", Path(__file__).with_name("direct_trial.py"))
_helpers = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_helpers)
public_ip, public_key, quote = _helpers.public_ip, _helpers.public_key, _helpers.quote
remote_site, safe_mode_confirmed = _helpers.remote_site, _helpers.safe_mode_confirmed

OWNER = "s2s-forward-trial-20261018"
IFACE = "wg-forward-trial"
NETWORK = ipaddress.ip_network("10.60.62.0/30")
SITES = {"nakhimova": ("HKM0BDXYG74", "10.60.62.1", 51971),
         "fethiye": ("HM20B6QXS8H", "10.60.62.2", 51972)}
FILTERS = ("udp", "icmp", "input-deny", "forward-in-deny", "forward-out-deny")


def assert_free(snapshot):
    for path, rows in snapshot.items():
        for row in rows:
            if row.get("name") in (IFACE, OWNER) or row.get("comment", "").startswith(OWNER):
                raise ValueError("trial_namespace_occupied")
            if path == "/interface wireguard" and int(row.get("listen-port", 0)) in (51971, 51972):
                raise ValueError("trial_port_occupied")
            if path in ("/ip firewall filter", "/ip firewall nat", "/ip firewall raw"):
                if any(str(row.get(prop, "")) in ("51971", "51972") for prop in ("dst-port", "src-port", "to-ports")):
                    raise ValueError("trial_port_rule_occupied")
            candidates = []
            if path == "/ip address":
                candidates.append(row.get("address", ""))
            if path == "/ip route":
                candidates.append(row.get("dst-address", ""))
            if path == "/interface wireguard peers":
                allowed = row.get("allowed-address", [])
                candidates.extend(allowed.split(",") if isinstance(allowed, str) else allowed)
            for value in candidates:
                if not value:
                    continue
                network = ipaddress.ip_network(value, strict=False)
                # A default route does not reserve this test subnet; other overlaps do.
                if network.version == 4 and network.prefixlen and NETWORK.overlaps(network):
                    raise ValueError("trial_network_occupied")


def stage_commands(site, other_public_ip):
    _, local, port = SITES[site]
    remote = SITES[remote_site(site)][1]
    endpoint = public_ip(other_public_ip)
    head = "place-before=([find where dynamic=no]->0)"
    return [
        f'/interface wireguard add disabled=yes name="{IFACE}" listen-port={port} mtu=1380 comment="{OWNER}:interface"',
        f'/ip address add address={local}/30 interface="{IFACE}" comment="{OWNER}:address"',
        f'/ip firewall filter add chain=forward action=drop in-interface="{IFACE}" {head} comment="{OWNER}:forward-in-deny"',
        f'/ip firewall filter add chain=forward action=drop out-interface="{IFACE}" {head} comment="{OWNER}:forward-out-deny"',
        f'/ip firewall filter add chain=input action=drop in-interface="{IFACE}" {head} comment="{OWNER}:input-deny"',
        f'/ip firewall filter add chain=input action=accept protocol=icmp in-interface="{IFACE}" src-address={remote}/32 dst-address={local}/32 {head} comment="{OWNER}:icmp"',
        f'/ip firewall filter add chain=input action=accept protocol=udp in-interface=ether1 src-address={endpoint}/32 dst-port={port} {head} comment="{OWNER}:udp"',
    ]


def peer_command(site, other_public_key, fethiye_public_ip):
    remote = SITES[remote_site(site)][1]
    endpoint = public_ip(fethiye_public_ip)
    base = (f'/interface wireguard peers add interface="{IFACE}" public-key={quote(public_key(other_public_key))} '
            f'allowed-address={remote}/32 comment="{OWNER}:peer"')
    if site == "nakhimova":
        return base + f" endpoint-address={endpoint} endpoint-port=51972 persistent-keepalive=25s"
    # Fethiye learns the initiator's translated port from authenticated packets.
    return base


def ping_command(site, size=56):
    if type(size) is not int or size not in (56, 1380):
        raise ValueError("unsupported_test_size")
    local, remote = SITES[site][1], SITES[remote_site(site)][1]
    return (f'/ping address={remote} src-address={local} interface={IFACE} '
            f'count=5 interval=200ms size={size} do-not-fragment')


def cleanup_commands():
    commands = [f'/interface wireguard peers remove [find where comment="{OWNER}:peer"]',
                f'/ip address remove [find where comment="{OWNER}:address"]']
    commands.extend(f'/ip firewall filter remove [find where comment="{OWNER}:{suffix}"]' for suffix in FILTERS)
    commands.append(f'/interface wireguard remove [find where name="{IFACE}" and comment="{OWNER}:interface"]')
    return commands
