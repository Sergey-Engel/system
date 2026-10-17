"""Pure, bounded IPv4 LAN-pair changeset; no key generation or live I/O."""
import hashlib
import ipaddress
import json

OWNER = "s2s-lan-20261016"
SITES = {
    "nakhimova": dict(serial="HKM0BDXYG74", local="192.168.88.0/24", remote="192.168.89.0/24", ip="192.168.88.1", old="s2s-nakhimova-20261016"),
    "fethiye": dict(serial="HM20B6QXS8H", local="192.168.89.0/24", remote="192.168.88.0/24", ip="192.168.89.1", old="s2s-pilot-20261016"),
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def occupied(routes, target):
    target = ipaddress.ip_network(target)
    for value in routes:
        candidate = ipaddress.ip_network("0.0.0.0/0" if value == "default" else value, strict=False)
        if candidate.version == 4 and candidate.prefixlen and candidate.overlaps(target):
            raise ValueError("remote LAN route occupied")


def validate(state, expected):
    if fingerprint(state) != expected:
        raise ValueError("baseline changed")
    if not all(state[k] for k in ("contracts_ok", "files_ok", "guard_ok")):
        raise ValueError("protected state or file drift")
    if sorted(state["hub_allowed"]) != ["10.60.60.2/32", "10.60.60.3/32"]:
        raise ValueError("unexpected hub peer scope")
    if set(state["sites"]) != set(SITES):
        raise ValueError("site identity mismatch")
    for name, spec in SITES.items():
        site = state["sites"][name]
        if site["serial"] != spec["serial"] or not site["trusted"]:
            raise ValueError("router identity mismatch")
        if site["peer_allowed"] != "10.60.60.1/32":
            raise ValueError("router peer drift")
        occupied(site["routes"], spec["remote"])
        occupied(state["hub_routes"], spec["local"])
        for suffix, chain, action in ((":forward-in", "forward", "drop"), (":icmp", "s2s-pilot-input", "accept")):
            rows = [r for r in site["filters"] if r.get("comment") == spec["old"] + suffix]
            if len(rows) != 1 or rows[0].get("dynamic") or rows[0].get("chain") != chain or rows[0].get("action") != action:
                raise ValueError("static firewall anchor missing or ambiguous")
        if any(OWNER in r.get("comment", "") for r in site["filters"]):
            raise ValueError("owned scope already occupied")


def hub_config(before, expected):
    if before != expected or "192.168." in before:
        raise ValueError("hub baseline drift")
    after = before
    for address, subnet in (("10.60.60.2/32", "192.168.88.0/24"), ("10.60.60.3/32", "192.168.89.0/24")):
        line = f"AllowedIPs = {address}\n"
        if before.count(line) != 1:
            raise ValueError("hub peer mapping ambiguous")
        after = after.replace(line, f"AllowedIPs = {address}, {subnet}\n")
    return after


def guard_rules():
    parts = ['table inet s2s_pilot {\n']
    for direction, iface in (("input", "iifname"), ("output", "oifname")):
        parts.append(f' chain {direction} {{\n  type filter hook {direction} priority -50; policy accept;\n')
        for peer in (3, 2):
            src, dst = (f"10.60.60.{peer}", "10.60.60.1") if direction == "input" else ("10.60.60.1", f"10.60.60.{peer}")
            parts.append(f'  {iface} "wg-s2s" ip saddr {src} ip daddr {dst} icmp type {{ echo-request, echo-reply }} counter accept\n')
        parts.append(f'  {iface} "wg-s2s" counter drop\n }}\n')
    parts.append(' chain forward {\n  type filter hook forward priority -50; policy accept;\n'
                 '  iifname "wg-s2s" ct state invalid counter drop\n')
    for spec in SITES.values():
        parts.append(f'  iifname "wg-s2s" oifname "wg-s2s" ip saddr {spec["local"]} ip daddr {spec["remote"]} counter accept\n')
    parts.append('  iifname "wg-s2s" counter drop\n  oifname "wg-s2s" counter drop\n }\n}\n')
    return ''.join(parts)


def router_prepare(site):
    spec = SITES[site]
    anchor = f'[/ip firewall filter find where comment="{spec["old"]}:forward-in"]'
    icmp = f'[/ip firewall filter find where comment="{spec["old"]}:icmp"]'
    states = "connection-state=new,established,related,untracked"
    return [
        f'/ip route add disabled=yes dst-address={spec["remote"]} gateway=wg-s2s-tw routing-table=main distance=1 comment="{OWNER}:route"',
        f'/ip firewall filter add disabled=yes chain=forward action=accept in-interface=wg-s2s-tw out-interface=bridge src-address={spec["remote"]} dst-address={spec["local"]} {states} place-before={anchor} comment="{OWNER}:from-remote"',
        f'/ip firewall filter add disabled=yes chain=forward action=accept in-interface=bridge out-interface=wg-s2s-tw src-address={spec["local"]} dst-address={spec["remote"]} {states} place-before={anchor} comment="{OWNER}:to-remote"',
        f'/ip firewall filter add disabled=yes chain=s2s-pilot-input action=accept in-interface=wg-s2s-tw protocol=icmp src-address={spec["remote"]} dst-address={spec["ip"]}/32 {states} place-before={icmp} comment="{OWNER}:router-ping"',
        f'/interface wireguard peers set [find where interface="wg-s2s-tw"] allowed-address=10.60.60.1/32,{spec["remote"]}',
    ]


def router_activate():
    return [f'/ip firewall filter enable [find where comment~"^{OWNER}:"]',
            f'/ip route enable [find where comment="{OWNER}:route"]']


def profile(before, site):
    line = "AllowedIPs = 10.60.60.1/32\n"
    if before.count(line) != 1:
        raise ValueError("profile baseline drift")
    return before.replace(line, f'AllowedIPs = 10.60.60.1/32, {SITES[site]["remote"]}\n')


def disabled_flag(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value in {"true", "false"}:
        return value == "true"
    raise ValueError("missing or invalid disabled flag; read explicit RouterOS get")
