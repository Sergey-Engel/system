"""Pure, scoped IPIP-over-WireGuard egress plan for one test client."""
import hashlib
import importlib.util
import ipaddress
import json
from pathlib import Path
import re

OWNER = "s2s-egress-20261016"
TUNNEL = "ipip-s2s-egress"
CLIENT = "192.168.89.197"
MAC = "A2:C1:5E:29:F5:8E"
DNS = "9.9.9.9"
NETWORK = ipaddress.ip_network("10.60.61.0/30")
SITES = {
    "nakhimova": dict(serial="HKM0BDXYG74", outer="10.60.60.2", peer="10.60.60.3", inner="10.60.61.1", inner_peer="10.60.61.2",
        old="s2s-nakhimova-20261016", before_allowed="10.60.60.1/32,192.168.89.0/24", after_allowed="10.60.60.1/32,10.60.60.3/32,192.168.89.0/24"),
    "fethiye": dict(serial="HM20B6QXS8H", outer="10.60.60.3", peer="10.60.60.2", inner="10.60.61.2", inner_peer="10.60.61.1",
        old="s2s-pilot-20261016", before_allowed="10.60.60.1/32,192.168.88.0/24", after_allowed="10.60.60.1/32,10.60.60.2/32,192.168.88.0/24"),
}
NOT_INTERNET = ("0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
                "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24", "192.168.0.0/16", "198.18.0.0/15",
                "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def client_lease(lease, dynamic):
    client = dict(ip=lease.get("address"), mac=lease.get("mac-address"), bound=lease.get("status") == "bound")
    if dynamic is not True or client != dict(ip=CLIENT, mac=MAC, bound=True):
        raise ValueError("current dynamic client lease identity failed")
    return client


def validate(state, expected):
    if fingerprint(state) != expected or not all(state[k] for k in ("trusted", "contracts_ok", "files_ok", "guard_ok")):
        raise ValueError("baseline, trust or protected contract failed")
    if state["client"] != dict(ip=CLIENT, mac=MAC, bound=True):
        raise ValueError("test client identity changed")
    if set(state["sites"]) != set(SITES):
        raise ValueError("site scope changed")
    for name, spec in SITES.items():
        site = state["sites"][name]
        if site["serial"] != spec["serial"] or not all(site[k] for k in ("ipip_available", "owner_empty", "anchors_ok")):
            raise ValueError("router identity or owned scope failed")
        if TUNNEL in site["interfaces"] or {"s2s_remote", "s2s_return"}.intersection(site["tables"]):
            raise ValueError("interface or routing table occupied")
        if site["peer_allowed"] != spec["before_allowed"]:
            raise ValueError("peer scope changed")
        for value in site["networks"]:
            candidate = ipaddress.ip_network(value, strict=False)
            if candidate.version == 4 and candidate.prefixlen and NETWORK.overlaps(candidate):
                raise ValueError("inner tunnel network occupied")


def lan_guard():
    spec = importlib.util.spec_from_file_location("s2s_lan_guard", Path(__file__).with_name("lan.py"))
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj.guard_rules()


def guard_rules(before):
    if before != lan_guard():
        raise ValueError("host guard baseline drift")
    anchor = '  iifname "wg-s2s" counter drop\n  oifname "wg-s2s" counter drop\n'
    extra = ''.join(f'  iifname "wg-s2s" oifname "wg-s2s" ip saddr {s["outer"]} ip daddr {s["peer"]} ip protocol 4 counter accept\n' for s in SITES.values())
    if before.count(anchor) != 1:
        raise ValueError("host forward anchor ambiguous")
    return before.replace(anchor, extra + anchor)


def transport_commands(site):
    s = SITES[site]
    anchor = f'[/ip firewall filter find where comment="{s["old"]}:forward-in"]'
    icmp = f'[/ip firewall filter find where comment="{s["old"]}:icmp"]'
    commands = [
        f'/interface ipip add disabled=yes name={TUNNEL} local-address={s["outer"]} remote-address={s["peer"]} mtu=1400 clamp-tcp-mss=yes keepalive=10s,3 comment="{OWNER}:tunnel"',
        f'/ip address add address={s["inner"]}/30 interface={TUNNEL} comment="{OWNER}:address"',
        f'/ip firewall filter add chain=s2s-pilot-input action=accept protocol=4 in-interface=wg-s2s-tw src-address={s["peer"]}/32 dst-address={s["outer"]}/32 place-before={icmp} comment="{OWNER}:outer-ipip"',
        f'/ip firewall filter add chain=s2s-egress-input action=accept protocol=icmp in-interface={TUNNEL} src-address={s["inner_peer"]}/32 dst-address={s["inner"]}/32 comment="{OWNER}:inner-icmp"',
        f'/ip firewall filter add chain=s2s-egress-input action=drop comment="{OWNER}:input-deny"',
        f'/ip firewall filter add chain=input action=jump jump-target=s2s-egress-input in-interface={TUNNEL} place-before={anchor} comment="{OWNER}:input-jump"',
    ]
    if site == "fethiye":
        rules = [f'in-interface=bridge out-interface={TUNNEL} src-address={CLIENT}/32 connection-state=new,established,related',
                 f'in-interface={TUNNEL} out-interface=bridge dst-address={CLIENT}/32 connection-state=established,related']
    else:
        commands += [f'/ip firewall address-list add list=s2s-egress-not-internet address={net} comment="{OWNER}:bogon"' for net in NOT_INTERNET]
        rules = [f'in-interface={TUNNEL} out-interface=ether1 src-address={CLIENT}/32 dst-address-list=!s2s-egress-not-internet connection-state=new,established,related',
                 f'in-interface=ether1 out-interface={TUNNEL} dst-address={CLIENT}/32 connection-state=established,related']
    commands += [f'/ip firewall filter add chain=s2s-egress-forward action=accept {rule} comment="{OWNER}:flow-{i}"' for i, rule in enumerate(rules)]
    commands += [f'/ip firewall filter add chain=s2s-egress-forward action=drop comment="{OWNER}:forward-deny"',
        f'/ip firewall filter add chain=forward action=jump jump-target=s2s-egress-forward in-interface={TUNNEL} place-before={anchor} comment="{OWNER}:forward-in"',
        f'/ip firewall filter add chain=forward action=jump jump-target=s2s-egress-forward out-interface={TUNNEL} place-before={anchor} comment="{OWNER}:forward-out"',
        f'/interface wireguard peers set [find where interface="wg-s2s-tw"] allowed-address={s["after_allowed"]}']
    return commands


def client_commands():
    anchor = '[/ip firewall filter find where comment="s2s-pilot-20261016:forward-in"]'
    v6forward = '[/ipv6 firewall filter find where chain=forward and comment="defconf: accept established,related,untracked"]'
    v6input = '[/ipv6 firewall filter find where chain=input and comment="defconf: accept established,related,untracked"]'
    commands = [
        f'/routing table add fib name=s2s_remote comment="{OWNER}:table"',
        f'/ip route add dst-address=0.0.0.0/0 gateway=10.60.61.1@main routing-table=s2s_remote distance=1 comment="{OWNER}:remote-default"',
        f'/ip route add blackhole dst-address=0.0.0.0/0 routing-table=s2s_remote distance=254 comment="{OWNER}:remote-blackhole"',
        f'/ip firewall filter add disabled=yes chain=forward action=drop in-interface=bridge src-mac-address={MAC} out-interface=ether1 dst-address=!192.168.68.0/24 place-before={anchor} comment="{OWNER}:wan-guard"',
        f'/ipv6 firewall filter add disabled=yes chain=forward action=drop in-interface=bridge src-mac-address={MAC} place-before={v6forward} comment="{OWNER}:ipv6-forward"',
    ]
    for protocol in ("udp", "tcp"):
        commands += [f'/ipv6 firewall filter add disabled=yes chain=input action=drop in-interface=bridge src-mac-address={MAC} protocol={protocol} dst-port=53 place-before={v6input} comment="{OWNER}:ipv6-dns-{protocol}"',
            f'/ip firewall nat add disabled=yes chain=dstnat action=dst-nat in-interface=bridge src-mac-address={MAC} protocol={protocol} dst-port=53 to-addresses={DNS} to-ports=53 comment="{OWNER}:dns-{protocol}"']
    for net in ("192.168.68.0/24", "192.168.88.0/24", "192.168.89.0/24"):
        commands.append(f'/routing rule add disabled=yes src-address={CLIENT}/32 dst-address={net} action=lookup-only-in-table table=main comment="{OWNER}:bypass-{net.split(".")[2]}"')
    commands.append(f'/routing rule add disabled=yes src-address={CLIENT}/32 action=lookup-only-in-table table=s2s_remote comment="{OWNER}:client-route"')
    return commands


def return_commands():
    anchor = '[/routing rule find where comment="GLOBAL: Local bypass for ALL"]'
    return [f'/routing table add fib name=s2s_return comment="{OWNER}:table"',
        f'/ip route add dst-address={CLIENT}/32 gateway=10.60.61.2@main routing-table=s2s_return distance=1 comment="{OWNER}:return-route"',
        f'/ip route add blackhole dst-address={CLIENT}/32 routing-table=s2s_return distance=254 comment="{OWNER}:return-blackhole"',
        f'/routing rule add interface=ether1 dst-address={CLIENT}/32 action=lookup-only-in-table table=s2s_return place-before={anchor} comment="{OWNER}:return-rule"']


def mode_commands(mode):
    kill = f'[/ip firewall filter find where comment="{OWNER}:wan-guard"]'
    v6 = f'[/ipv6 firewall filter find where comment~"^{OWNER}:ipv6-"]'
    dns = f'[/ip firewall nat find where comment~"^{OWNER}:dns-"]'
    rules = f'[/routing rule find where comment~"^{OWNER}:"]'
    pattern = '"^192[.]168[.]89[.]197(:|\\$)"'
    clear = [f'/ip firewall connection remove [find where src-address~{pattern}]',
             f'/ip firewall connection remove [find where dst-address~{pattern}]']
    if mode == "remote":
        return [f'/ip firewall filter enable {kill}', f'/ipv6 firewall filter enable {v6}', *clear,
                f'/ip firewall nat enable {dns}', f'/routing rule enable {rules}', *clear]
    if mode == "local":
        return [f'/routing rule disable {rules}', f'/ip firewall nat disable {dns}', *clear,
                f'/ipv6 firewall filter disable {v6}', f'/ip firewall filter disable {kill}']
    raise ValueError("unsupported egress mode")


CONTROL_PATHS = {
    "wan-guard": "/ip firewall filter",
    **{name: "/ipv6 firewall filter" for name in ("ipv6-forward", "ipv6-dns-udp", "ipv6-dns-tcp")},
    **{name: "/ip firewall nat" for name in ("dns-udp", "dns-tcp")},
    **{name: "/routing rule" for name in ("bypass-68", "bypass-88", "bypass-89", "client-route")},
}


def control_ids(controls):
    """Pin exactly ten typed controls; reject ambiguous RouterOS selections."""
    result = {}
    identities = set()
    for item in controls:
        path, row = item["path"], item["row"]
        comment = row.get("comment", "")
        suffix = comment.removeprefix(OWNER + ":")
        identity = row.get(".id", "")
        if (comment != OWNER + ":" + suffix or CONTROL_PATHS.get(suffix) != path
                or suffix in result or not re.fullmatch(r"\*[0-9A-Fa-f]+", identity)
                or (path, identity) in identities or type(row.get("disabled")) is not bool):
            raise ValueError("mode control identity, scope or flag differs")
        identities.add((path, identity))
        result[suffix] = identity
    if set(result) != set(CONTROL_PATHS):
        raise ValueError("mode controls incomplete")
    return result


def pinned_mode_commands(mode, controls):
    ids = control_ids(controls)
    clear = [c for c in mode_commands("local") if c.startswith("/ip firewall connection remove ")]
    def change(names, verb):
        return [f"{CONTROL_PATHS[name]} {verb} {ids[name]}" for name in names]
    guards = ("wan-guard", "ipv6-forward", "ipv6-dns-udp", "ipv6-dns-tcp")
    dns = ("dns-udp", "dns-tcp")
    rules = ("bypass-68", "bypass-88", "bypass-89", "client-route")
    if mode == "remote":
        return change(guards, "enable") + clear + change(dns + rules, "enable") + clear
    if mode == "local":
        return change(rules + dns, "disable") + clear + change(guards[1:] + guards[:1], "disable")
    raise ValueError("unsupported egress mode")


def mode_export(text):
    """Ignore only approved mode flags and the separately verified lease binding."""
    result = []
    seen = set()
    binding = False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.search(r'(?<![\w-])comment="?' + re.escape(OWNER) + r':([\w-]+)"?(?=\s|$)', line)
        if match:
            name = match[1]
            if name in CONTROL_PATHS:
                if name in seen or not line.startswith(CONTROL_PATHS[name] + " add "):
                    raise ValueError("mode export control ambiguous")
                seen.add(name)
                line = re.sub(r"(?<![\w-])disabled=(?:yes|no)\s*", "", line)
            elif name == "client-binding":
                if binding or not line.startswith("/ip dhcp-server lease add "):
                    raise ValueError("mode export binding ambiguous")
                binding = True
                continue
        result.append(line.rstrip())
    if seen != set(CONTROL_PATHS):
        raise ValueError("mode export controls incomplete")
    return "\n".join(result)


def profile(before, site):
    s = SITES[site]
    old = 'AllowedIPs = ' + s['before_allowed'].replace(',', ', ') + '\n'
    if before.count(old) != 1:
        raise ValueError("profile baseline drift")
    return before.replace(old, 'AllowedIPs = ' + s['after_allowed'].replace(',', ', ') + '\n')
