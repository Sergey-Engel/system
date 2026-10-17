"""Pure, fail-closed plan for the approved ICMP-only Fethiye pilot.

This module never connects to a host. The operator must provide a fresh pinned
baseline and persist the returned bundle privately before deploying it.
"""
import hashlib
import ipaddress
import json
import re

NETWORK = ipaddress.ip_network("10.60.60.0/29")
OWNER = "s2s-pilot-20261016"


def fingerprint(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(state, expected):
    if fingerprint(state) != expected:
        raise ValueError("baseline changed")
    if state["serial"] != "HM20B6QXS8H" or not state["trusted"] or not state["contracts_ok"]:
        raise ValueError("identity, trust or protected contract failed")
    if {"wg-s2s", "wg-s2s-tw"}.intersection(state["interfaces"]):
        raise ValueError("interface occupied; rerun prohibited")
    if state["owned_files"] or state["owned_table"]:
        raise ValueError("owned scope not empty; inspect before rerun")
    text = re.sub(r"\\\s*\n\s*", " ", state["router_export"])
    if re.search(r'(?:name|interface)="?wg-s2s(?:-tw)?(?:"|\s|$)', text) or OWNER in text:
        raise ValueError("router pilot scope occupied")
    if "s2s-pilot-input" in text:
        raise ValueError("foreign input chain occupied")
    if text.count('comment="Allow admin Mac from Deco LAN"') != 1:
        raise ValueError("static firewall anchor missing or ambiguous")
    if 51860 in state["ports"] or re.search(r"(?:\.)?listen-port=51860\b", text):
        raise ValueError("port occupied")
    networks = list(state["networks"])
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("/"):
            section = line.split(" add ", 1)[0].split(" set ", 1)[0]
        field = ("address" if section == "/ip address" else
                 "allowed-address" if section == "/interface wireguard peers" else None)
        if field:
            for value in re.findall(r"(?<![\w.])(?:\.)?" + field + r"=([^\s]+)", line):
                networks.extend(value.strip('"').split(","))
    for value in networks:
        try:
            candidate = ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError("unparsed network in baseline") from exc
        # A default is not an allocation; all other overlaps require review.
        if candidate.version == 4 and candidate.prefixlen > 0 and NETWORK.overlaps(candidate):
            raise ValueError("network occupied")


def guard_rules():
    return '''table inet s2s_pilot {
 chain input {
  type filter hook input priority -50; policy accept;
  iifname "wg-s2s" ip saddr 10.60.60.3 ip daddr 10.60.60.1 icmp type { echo-request, echo-reply } counter accept
  iifname "wg-s2s" counter drop
 }
 chain output {
  type filter hook output priority -50; policy accept;
  oifname "wg-s2s" ip saddr 10.60.60.1 ip daddr 10.60.60.3 icmp type { echo-request, echo-reply } counter accept
  oifname "wg-s2s" counter drop
 }
 chain forward {
  type filter hook forward priority -50; policy accept;
  iifname "wg-s2s" counter drop
  oifname "wg-s2s" counter drop
 }
}
'''


def bundle(server_private, router_public, guard):
    if guard != guard_rules():
        raise ValueError("guard differs from reviewed policy")
    for value in (server_private, router_public):
        if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", value):
            raise ValueError("invalid key encoding")
    return {
        "/etc/wireguard/wg-s2s.conf": f'''[Interface]
PrivateKey = {server_private}
Address = 10.60.60.1/29
ListenPort = 51860
MTU = 1420

[Peer]
PublicKey = {router_public}
AllowedIPs = 10.60.60.3/32
''',
        "/etc/wireguard/s2s-pilot/guard.nft": guard,
        "/etc/systemd/system/s2s-pilot-guard.service": '''[Unit]
Description=Fail-closed ICMP-only S2S pilot guard
Before=wg-quick@wg-s2s.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /etc/wireguard/s2s-pilot/guard.py load
RemainAfterExit=yes
''',
        "/etc/systemd/system/wg-quick@wg-s2s.service.d/pilot.conf": '''[Unit]
Requires=s2s-pilot-guard.service
After=s2s-pilot-guard.service
BindsTo=s2s-pilot-guard.service

[Service]
ExecStartPre=/usr/bin/python3 /etc/wireguard/s2s-pilot/guard.py check
''',
    }


def router_commands(private, server_public):
    for value in (private, server_public):
        if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", value):
            raise ValueError("invalid key encoding")
    anchor='[/ip firewall filter find where comment="Allow admin Mac from Deco LAN"]'
    return [
        f'/interface wireguard add disabled=yes name=wg-s2s-tw mtu=1420 listen-port=51860 private-key="{private}" comment="{OWNER}"',
        f'/ip firewall filter add chain=forward action=drop in-interface=wg-s2s-tw place-before={anchor} comment="{OWNER}:forward-in"',
        f'/ip firewall filter add chain=forward action=drop out-interface=wg-s2s-tw place-before={anchor} comment="{OWNER}:forward-out"',
        f'/ip firewall filter add chain=s2s-pilot-input action=accept protocol=icmp src-address=10.60.60.1/32 dst-address=10.60.60.3/32 in-interface=wg-s2s-tw comment="{OWNER}:icmp"',
        f'/ip firewall filter add chain=s2s-pilot-input action=drop comment="{OWNER}:input-deny"',
        f'/ip firewall filter add chain=input action=jump jump-target=s2s-pilot-input in-interface=wg-s2s-tw place-before={anchor} comment="{OWNER}:input-jump"',
        f'/ip address add address=10.60.60.3/29 interface=wg-s2s-tw comment="{OWNER}"',
        f'/interface wireguard peers add interface=wg-s2s-tw public-key="{server_public}" allowed-address=10.60.60.1/32 endpoint-address=94.241.171.65 endpoint-port=51860 persistent-keepalive=25s comment="{OWNER}"',
        '/interface wireguard enable [/interface wireguard find where name="wg-s2s-tw"]',
    ]
