"""Isolated, reversible direct-WireGuard feasibility trial; never a LAN writer."""
import base64
from datetime import datetime, timedelta
import ipaddress
import re

OWNER = "s2s-direct-trial-20261017"
IFACE = "wg-direct-trial"
NETWORK = ipaddress.ip_network("10.60.62.0/30")
SITES = {"nakhimova": ("HKM0BDXYG74", "10.60.62.1", 51971),
         "fethiye": ("HM20B6QXS8H", "10.60.62.2", 51972)}
FILTERS = ("udp", "icmp", "input-deny", "forward-in-deny", "forward-out-deny")


def safe_mode_confirmed(transcript):
    if b'Hijacking Safe Mode' in transcript:
        return False
    return (b'Safe Mode taken' in transcript or b'Taking Safe Mode session... Success!' in transcript) and b'<SAFE>' in transcript


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


def public_ip(value):
    address = ipaddress.IPv4Address(value)
    if not address.is_global:
        raise ValueError("non_public_endpoint")
    return str(address)


def public_key(value):
    if not isinstance(value, str) or len(value) != 44 or len(base64.b64decode(value, validate=True)) != 32:
        raise ValueError("invalid_public_key")
    return value


def remote_site(site):
    if site not in SITES:
        raise ValueError("unknown_site")
    return next(s for s in SITES if s != site)


def assert_free(snapshot):
    for path, rows in snapshot.items():
        for row in rows:
            if row.get("name") == IFACE or row.get("name") == OWNER or row.get("comment", "").startswith(OWNER):
                raise ValueError("trial_namespace_occupied")
            if path == "/interface wireguard" and int(row.get("listen-port", 0)) in (51971, 51972):
                raise ValueError("trial_port_occupied")
            candidates = []
            if path == "/ip address": candidates.append(row.get("address", ""))
            if path == "/ip route": candidates.append(row.get("dst-address", ""))
            if path == "/interface wireguard peers":
                allowed = row.get("allowed-address", [])
                candidates.extend(allowed.split(",") if isinstance(allowed, str) else allowed)
            for value in candidates:
                if not value: continue
                network = ipaddress.ip_network(value, strict=False)
                # Default/private aggregates do not reserve this specific test subnet.
                if network.version == 4 and network.prefixlen >= 24 and NETWORK.overlaps(network):
                    raise ValueError("trial_network_occupied")


def cleanup_commands():
    commands = [f'/interface wireguard disable [find where name="{IFACE}" and comment="{OWNER}:interface"]',
                f'/interface wireguard peers remove [find where comment="{OWNER}:peer"]',
                f'/ip address remove [find where comment="{OWNER}:address"]']
    commands.extend(f'/ip firewall filter remove [find where comment="{OWNER}:{suffix}"]' for suffix in FILTERS)
    commands.extend([f'/interface wireguard remove [find where name="{IFACE}" and comment="{OWNER}:interface"]',
                     f'/system scheduler remove [find where name="{OWNER}" and comment="{OWNER}:expiry"]'])
    return commands


def guard_command(date, clock, seconds=720):
    if seconds not in (60, 720):
        raise ValueError("unbounded_expiry")
    when = datetime.fromisoformat(date + "T" + clock) + timedelta(seconds=seconds)
    event = "; ".join(cleanup_commands())
    return (f'/system scheduler add name="{OWNER}" comment="{OWNER}:expiry" '
            f'start-date={when:%Y-%m-%d} start-time={when:%H:%M:%S} interval=0s '
            'policy=read,write,policy,test on-event=' + quote(event))


def stage_commands(site, other_public_ip):
    _, local, port = SITES[site]
    remote = SITES[remote_site(site)][1]
    endpoint = public_ip(other_public_ip)
    head = 'place-before=([find where dynamic=no]->0)'
    return [
        f'/interface wireguard add disabled=yes name="{IFACE}" listen-port={port} mtu=1380 comment="{OWNER}:interface"',
        f'/ip address add address={local}/30 interface="{IFACE}" comment="{OWNER}:address"',
        f'/ip firewall filter add chain=forward action=drop in-interface="{IFACE}" {head} comment="{OWNER}:forward-in-deny"',
        f'/ip firewall filter add chain=forward action=drop out-interface="{IFACE}" {head} comment="{OWNER}:forward-out-deny"',
        f'/ip firewall filter add chain=input action=drop in-interface="{IFACE}" {head} comment="{OWNER}:input-deny"',
        f'/ip firewall filter add chain=input action=accept protocol=icmp in-interface="{IFACE}" src-address={remote}/32 dst-address={local}/32 {head} comment="{OWNER}:icmp"',
        f'/ip firewall filter add chain=input action=accept protocol=udp in-interface=ether1 src-address={endpoint}/32 dst-port={port} {head} comment="{OWNER}:udp"',
    ]


def peer_command(site, other_public_key, endpoint, port):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid_endpoint_port")
    remote = SITES[remote_site(site)][1]
    return (f'/interface wireguard peers add interface="{IFACE}" public-key={quote(public_key(other_public_key))} '
            f'allowed-address={remote}/32 endpoint-address={public_ip(endpoint)} endpoint-port={port} '
            f'persistent-keepalive=5s comment="{OWNER}:peer"')


def shared_stage_commands(site, other_public_ip, listen_port):
    if type(listen_port) is not int or not 1 <= listen_port <= 65535:
        raise ValueError("invalid_listener")
    local, remote = SITES[site][1], SITES[remote_site(site)][1]
    endpoint = public_ip(other_public_ip)
    head = 'place-before=([find where dynamic=no]->0)'
    iface = 'wg-s2s-tw'
    return [
        f'/ip address add address={local}/30 interface={iface} comment="{OWNER}:address"',
        f'/ip firewall filter add chain=forward action=drop in-interface={iface} src-address=10.60.62.0/30 {head} comment="{OWNER}:forward-in-deny"',
        f'/ip firewall filter add chain=forward action=drop out-interface={iface} dst-address=10.60.62.0/30 {head} comment="{OWNER}:forward-out-deny"',
        f'/ip firewall filter add chain=input action=drop in-interface={iface} src-address=10.60.62.0/30 {head} comment="{OWNER}:input-deny"',
        f'/ip firewall filter add chain=input action=accept protocol=icmp in-interface={iface} src-address={remote}/32 dst-address={local}/32 {head} comment="{OWNER}:icmp"',
        f'/ip firewall filter add chain=input action=accept protocol=udp in-interface=ether1 src-address={endpoint}/32 dst-port={listen_port} {head} comment="{OWNER}:udp"',
    ]


def shared_peer_command(site, other_public_key, endpoint, port):
    return peer_command(site, other_public_key, endpoint, port).replace(f'interface="{IFACE}"', 'disabled=yes interface="wg-s2s-tw"')


def ping_command(site, size=56, *, shared=False):
    if type(size) is not int or size not in (56, 1380):
        raise ValueError("unsupported_test_size")
    local, remote = SITES[site][1], SITES[remote_site(site)][1]
    iface = 'wg-s2s-tw' if shared else IFACE
    return (f'/ping address={remote} src-address={local} interface={iface} '
            f'count=5 interval=200ms size={size} do-not-fragment')


def captured_endpoints(text, expected_ip, excluded):
    expected_ip = public_ip(expected_ip)
    pattern = r'IP (\d+\.\d+\.\d+\.\d+)\.(\d+) > 94\.241\.171\.65\.51860: UDP, length 148'
    values = {(ip, int(port)) for ip, port in re.findall(pattern, text) if ip == expected_ip}
    values -= set(excluded)
    if len(values) != 1:
        raise ValueError("ambiguous_nat_observation")
    return next(iter(values))
