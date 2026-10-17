"""Pure changeset for the second ICMP-only leg; no connection or write APIs."""
import hashlib
import ipaddress
import json
import re

OWNER = "s2s-nakhimova-20261016"
NETWORK = ipaddress.ip_network("10.60.60.0/29")
CONFIG = "/etc/wireguard/wg-s2s.conf"
GUARD = "/etc/wireguard/s2s-pilot/guard.nft"
MANIFEST = "/etc/wireguard/s2s-pilot/manifest.json"
CHANGED = {CONFIG, GUARD, MANIFEST}


def fingerprint(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(state, expected):
    if fingerprint(state) != expected:
        raise ValueError("baseline changed")
    if state["serial"] != "HKM0BDXYG74" or not all(state[k] for k in
            ("trusted", "contracts_ok", "hub_files_ok", "hub_guard_ok")):
        raise ValueError("identity, trust or protected contract failed")
    if "wg-s2s-tw" in state["interfaces"] or 51860 in state["ports"]:
        raise ValueError("new router scope occupied")
    for value in state["networks"]:
        candidate = ipaddress.ip_network(value, strict=False)
        if candidate.version == 4 and candidate.prefixlen and NETWORK.overlaps(candidate):
            raise ValueError("router network occupied")
    if len(state["hub_peers"]) != 1 or list(state["hub_peers"].values()) != ["10.60.60.3/32"]:
        raise ValueError("unexpected hub peer scope")
    filters = state["filters"]
    anchors = [r for r in filters if r.get("comment") == "REALITY-B5-input"]
    if len(anchors) != 1 or anchors[0].get("dynamic") or anchors[0].get("chain") != "input" or anchors[0].get("action") != "drop":
        raise ValueError("static firewall anchor missing or ambiguous")
    if not re.fullmatch(r"\*[0-9A-F]+", anchors[0].get(".id", "")):
        raise ValueError("invalid static anchor identity")
    if any(r.get("chain") == "s2s-pilot-input" or r.get("jump-target") == "s2s-pilot-input"
           or OWNER in r.get("comment", "") for r in filters):
        raise ValueError("foreign input chain occupied")


def key(value):
    if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", value):
        raise ValueError("invalid key encoding")
    return value


def initial_config(private, fethiye_public):
    return (f"[Interface]\nPrivateKey = {key(private)}\nAddress = 10.60.60.1/29\n"
            f"ListenPort = 51860\nMTU = 1420\n\n[Peer]\nPublicKey = {key(fethiye_public)}\n"
            "AllowedIPs = 10.60.60.3/32\n")


def hub_config(before, private, fethiye_public, nakhimova_public):
    if before != initial_config(private, fethiye_public):
        raise ValueError("hub config differs from pinned first pilot")
    if key(nakhimova_public) in {private, fethiye_public}:
        raise ValueError("key identity collision")
    return before + f"\n[Peer]\nPublicKey = {nakhimova_public}\nAllowedIPs = 10.60.60.2/32\n"


def guard_rules():
    def allow(direction, src, dst):
        iface = "iifname" if direction == "input" else "oifname"
        return f'  {iface} "wg-s2s" ip saddr {src} ip daddr {dst} icmp type {{ echo-request, echo-reply }} counter accept\n'
    return ('table inet s2s_pilot {\n chain input {\n'
            '  type filter hook input priority -50; policy accept;\n' +
            ''.join(allow("input", f"10.60.60.{n}", "10.60.60.1") for n in (3, 2)) +
            '  iifname "wg-s2s" counter drop\n }\n chain output {\n'
            '  type filter hook output priority -50; policy accept;\n' +
            ''.join(allow("output", "10.60.60.1", f"10.60.60.{n}") for n in (3, 2)) +
            '  oifname "wg-s2s" counter drop\n }\n chain forward {\n'
            '  type filter hook forward priority -50; policy accept;\n'
            '  iifname "wg-s2s" counter drop\n  oifname "wg-s2s" counter drop\n }\n}\n')


def router_commands(private, hub_public):
    anchor = '[/ip firewall filter find where comment="REALITY-B5-input"]'
    return [
        f'/interface wireguard add disabled=yes name=wg-s2s-tw mtu=1420 listen-port=51860 private-key="{key(private)}" comment="{OWNER}"',
        f'/ip firewall filter add chain=forward action=drop in-interface=wg-s2s-tw place-before={anchor} comment="{OWNER}:forward-in"',
        f'/ip firewall filter add chain=forward action=drop out-interface=wg-s2s-tw place-before={anchor} comment="{OWNER}:forward-out"',
        f'/ip firewall filter add chain=s2s-pilot-input action=accept protocol=icmp src-address=10.60.60.1/32 dst-address=10.60.60.2/32 in-interface=wg-s2s-tw comment="{OWNER}:icmp"',
        f'/ip firewall filter add chain=s2s-pilot-input action=drop comment="{OWNER}:input-deny"',
        f'/ip firewall filter add chain=input action=jump jump-target=s2s-pilot-input in-interface=wg-s2s-tw place-before={anchor} comment="{OWNER}:input-jump"',
        f'/ip address add address=10.60.60.2/29 interface=wg-s2s-tw comment="{OWNER}"',
        f'/interface wireguard peers add interface=wg-s2s-tw public-key="{key(hub_public)}" allowed-address=10.60.60.1/32 endpoint-address=94.241.171.65 endpoint-port=51860 persistent-keepalive=25s comment="{OWNER}"',
        '/interface wireguard enable [/interface wireguard find where name="wg-s2s-tw"]',
    ]


def changed_paths(before, after, allowed=CHANGED):
    if before.keys() != after.keys():
        raise ValueError("file scope changed")
    changed = {p for p in before if before[p] != after[p]}
    if not changed.issubset(allowed):
        raise ValueError("unapproved file delta")
    return changed
