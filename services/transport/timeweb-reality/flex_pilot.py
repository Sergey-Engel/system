#!/usr/bin/env python3
"""Isolated per-peer routing controller for SOCKS-TW-FLEX."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


PEER = "10.50.50.39"
STATE = Path("/var/lib/vpn-uplink-pilot/flex-macbook.json")
AUDIT = Path("/var/lib/vpn-uplink-pilot/flex-macbook-actions.jsonl")
LOCK = Path("/run/lock/timeweb-flex-macbook.lock")
TARGETS = {"fx": ("wg1", "default via 10.20.0.2 dev wg1"),
           "cen": ("wg-up-cenuta", "default dev wg-up-cenuta")}
RU_COMMENT = "timeweb-flex-macbook-ru"
TABLE = "410"
MARK = "0x39"
SRC_PRIORITY = 239
MARK_PRIORITY = 188
FIREWALL_TABLE = "flex_macbook"


def select_device(device):
    global PEER, STATE, AUDIT, LOCK, RU_COMMENT, TABLE, MARK
    global SRC_PRIORITY, MARK_PRIORITY, FIREWALL_TABLE
    if device == "macbook":
        return
    if device == "macmini":
        PEER = "10.50.50.41"
        STATE = Path("/var/lib/vpn-uplink-pilot/flex-macmini.json")
        AUDIT = Path("/var/lib/vpn-uplink-pilot/flex-macmini-actions.jsonl")
        LOCK = Path("/run/lock/timeweb-flex-macmini.lock")
        RU_COMMENT = "timeweb-flex-macmini-ru"
        TABLE = "414"
        MARK = "0x41"
        SRC_PRIORITY = 243
        MARK_PRIORITY = 184
        FIREWALL_TABLE = "flex_macmini"
        return
    if device != "iphone12":
        raise ValueError("Unknown FLEX device")
    PEER = "10.50.50.40"
    STATE = Path("/var/lib/vpn-uplink-pilot/flex-iphone12.json")
    AUDIT = Path("/var/lib/vpn-uplink-pilot/flex-iphone12-actions.jsonl")
    LOCK = Path("/run/lock/timeweb-flex-iphone12.lock")
    RU_COMMENT = "timeweb-flex-iphone12-ru"
    TABLE = "412"
    MARK = "0x40"
    SRC_PRIORITY = 241
    MARK_PRIORITY = 186
    FIREWALL_TABLE = "flex_iphone12"


def run(*args, input_text=None, check=True):
    result = subprocess.run(args, input=input_text, text=True, capture_output=True,
                            timeout=20, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Command failed: {args[:3]} (exit {result.returncode})")
    return result


def net(*args, input_text=None, check=True):
    return run("docker", "exec", "-i", "wg-relay", *args,
               input_text=input_text, check=check)


def read_state():
    value = json.loads(STATE.read_text())
    if value.get("exit") not in TARGETS or type(value.get("ru_direct")) is not bool:
        raise ValueError("Invalid FLEX state")
    return value


def save_state(value):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".flex-state-", dir=STATE.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, STATE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def audit(before, after, ok, reason):
    record = {"time": time.time(), "before": before, "after": after,
              "success": ok, "reason": reason}
    fd = os.open(AUDIT, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(record, sort_keys=True) + "\n").encode())
    finally:
        os.close(fd)


def rule_present(priority, *, src=None, fwmark=None, table=None, action=None):
    rules = json.loads(net("ip", "-j", "rule", "show").stdout)
    return any(rule.get("priority") == priority and
               (src is None or rule.get("src") == src) and
               (fwmark is None or rule.get("fwmark") == fwmark) and
               (table is None or str(rule.get("table")) == str(table)) and
               (action is None or rule.get("action") == action) for rule in rules)


def ensure_rule(priority, args, **expected):
    if not rule_present(priority, **expected):
        if any(rule.get("priority") == priority for rule in
               json.loads(net("ip", "-j", "rule", "show").stdout)):
            raise RuntimeError(f"Unexpected policy rule at priority {priority}")
        net("ip", "rule", "add", *args, "priority", str(priority))


def ru_rule_handles():
    result = net("nft", "-j", "-a", "list", "chain", "inet", "ru_bth", "prerouting", check=False)
    if result.returncode:
        return None
    data = json.loads(result.stdout)
    return [item["rule"]["handle"] for item in data["nftables"] if "rule" in item and
            item["rule"].get("comment") == RU_COMMENT]


def guard_rules():
    return f'''table inet {FIREWALL_TABLE} {{
 chain forward {{
  type filter hook forward priority -10; policy accept;
  iifname "wg-clients" ip saddr {PEER} oifname "wg1" counter accept
  iifname "wg-clients" ip saddr {PEER} oifname "wg-up-cenuta" counter accept
  iifname "wg-clients" ip saddr {PEER} oifname "eth0" meta mark {MARK} counter accept
  iifname "wg-clients" ip saddr {PEER} counter drop
  oifname "wg-clients" ip daddr {PEER} ct state established counter accept
  oifname "wg-clients" ip daddr {PEER} counter drop
 }}
 chain postrouting {{
  type nat hook postrouting priority srcnat; policy accept;
  ip saddr {PEER} oifname "wg1" counter masquerade
  ip saddr {PEER} oifname "wg-up-cenuta" counter masquerade
  ip saddr {PEER} oifname "eth0" meta mark {MARK} counter masquerade
 }}
}}
'''


def ensure_guard():
    if net("nft", "list", "table", "inet", FIREWALL_TABLE, check=False).returncode:
        net("nft", "-f", "-", input_text=guard_rules())


def check_guard():
    current = net("nft", "-s", "list", "table", "inet", FIREWALL_TABLE).stdout
    expanded_mark = f'0x{int(MARK, 16):08x}'
    expected = (
        f'iifname "wg-clients" ip saddr {PEER} oifname "wg1" counter accept',
        f'iifname "wg-clients" ip saddr {PEER} oifname "wg-up-cenuta" counter accept',
        f'iifname "wg-clients" ip saddr {PEER} oifname "eth0" meta mark {expanded_mark} counter accept',
        f'iifname "wg-clients" ip saddr {PEER} counter drop',
        f'oifname "wg-clients" ip daddr {PEER} ct state established counter accept',
        f'oifname "wg-clients" ip daddr {PEER} counter drop',
        f'ip saddr {PEER} oifname "wg1" counter masquerade',
        f'ip saddr {PEER} oifname "wg-up-cenuta" counter masquerade',
        f'ip saddr {PEER} oifname "eth0" meta mark {expanded_mark} counter masquerade',
    )
    if any(current.count(item) != 1 for item in expected):
        raise RuntimeError("FLEX guard is not the expected ruleset")
    rules = json.loads(net("nft", "-j", "list", "table", "inet", FIREWALL_TABLE).stdout)
    if sum("rule" in item for item in rules["nftables"]) != len(expected):
        raise RuntimeError("Unexpected extra FLEX firewall rule")


def peer_present():
    output = net("wg", "show", "wg-clients", "allowed-ips").stdout
    return any(line.endswith(f"{PEER}/32") for line in output.splitlines())


def apply(value):
    if not peer_present():
        raise RuntimeError("FLEX peer is not present")
    target, route = TARGETS[value["exit"]]
    if net("ip", "link", "show", target, check=False).returncode != 0:
        raise RuntimeError("Selected uplink interface is absent")
    ensure_guard()
    check_guard()
    net("ip", "route", "replace", "table", TABLE, *route.split())
    net("ip", "route", "replace", "table", "411", "default", "via", "172.19.0.1", "dev", "eth0")
    ensure_rule(MARK_PRIORITY, ("fwmark", MARK, "table", "411"), fwmark=MARK, table="411")
    ensure_rule(MARK_PRIORITY + 1, ("fwmark", MARK, "prohibit"), fwmark=MARK, action="prohibit")
    ensure_rule(SRC_PRIORITY, ("from", PEER, "table", TABLE), src=PEER, table=TABLE)
    ensure_rule(SRC_PRIORITY + 1, ("from", PEER, "prohibit"), src=PEER, action="prohibit")
    handles = ru_rule_handles()
    if handles is None:
        if value["ru_direct"]:
            raise RuntimeError("RU address set is unavailable")
        handles = []
    for handle in handles[1:]:
        net("nft", "delete", "rule", "inet", "ru_bth", "prerouting", "handle", str(handle))
    handles = handles[:1]
    if value["ru_direct"] and not handles:
        net("nft", "add", "rule", "inet", "ru_bth", "prerouting",
            "iifname", "wg-clients", "ip", "saddr", PEER, "ip", "daddr", "@ru_networks_v4",
            "meta", "mark", "set", MARK, "comment", RU_COMMENT)
    if not value["ru_direct"]:
        for handle in handles:
            net("nft", "delete", "rule", "inet", "ru_bth", "prerouting", "handle", str(handle))
    # An interface PostUp quarantine is lifted only after routing and guard exist.
    quarantine = ("FORWARD", "-i", "wg-clients", "-s", f"{PEER}/32", "-j", "DROP")
    result = verify(value, allow_quarantine=True)
    for _ in range(256):
        if net("iptables", "-C", *quarantine, check=False).returncode != 0:
            break
        net("iptables", "-D", *quarantine)
    else:
        raise RuntimeError("Too many FLEX quarantine rules")
    if net("iptables", "-C", *quarantine, check=False).returncode == 0:
        raise RuntimeError("FLEX quarantine remains active")
    return result


def verify(value, allow_quarantine=False):
    if not peer_present():
        raise RuntimeError("FLEX peer is not present")
    check_guard()
    routes = net("ip", "route", "show", "table", TABLE).stdout
    direct = net("ip", "route", "show", "table", "411").stdout
    if TARGETS[value["exit"]][1] not in routes:
        raise RuntimeError("Selected route did not take effect")
    if "default via 172.19.0.1 dev eth0" not in direct:
        raise RuntimeError("RU-direct table is absent")
    if not (rule_present(MARK_PRIORITY, fwmark=MARK, table="411") and
            rule_present(MARK_PRIORITY + 1, fwmark=MARK, action="prohibit") and
            rule_present(SRC_PRIORITY, src=PEER, table=TABLE) and
            rule_present(SRC_PRIORITY + 1, src=PEER, action="prohibit")):
        raise RuntimeError("FLEX source policy is absent")
    handles = ru_rule_handles()
    if value["ru_direct"] and handles is None:
        raise RuntimeError("RU address set is unavailable")
    if bool(handles) != value["ru_direct"]:
        raise RuntimeError("RU-direct marker differs from requested state")
    if not allow_quarantine and net("iptables", "-C", "FORWARD", "-i", "wg-clients", "-s", f"{PEER}/32", "-j", "DROP", check=False).returncode == 0:
        raise RuntimeError("FLEX quarantine remains active")
    return {"exit": value["exit"], "ru_direct": value["ru_direct"], "observed": "ready"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=("macbook", "iphone12", "macmini"), default="macbook")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("reconcile")
    switch = sub.add_parser("switch")
    switch.add_argument("exit", choices=TARGETS)
    switch.add_argument("ru_direct", choices=("on", "off"))
    args = parser.parse_args()
    select_device(args.device)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = read_state()
        if args.command == "status":
            print(json.dumps(verify(before)))
            return
        desired = before if args.command == "reconcile" else {
            "exit": args.exit, "ru_direct": args.ru_direct == "on"}
        try:
            result = apply(desired)
            if args.command == "switch":
                save_state(desired)
            audit(before, desired, True, "verified")
            print(json.dumps(result))
        except Exception as error:
            quarantine = ("FORWARD", "-i", "wg-clients", "-s", f"{PEER}/32", "-j", "DROP")
            if net("iptables", "-C", *quarantine, check=False).returncode != 0:
                net("iptables", "-I", *quarantine, check=False)
            if args.command == "switch":
                try:
                    apply(before)
                except Exception:
                    pass
            audit(before, desired, False, type(error).__name__)
            raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"FLEX unavailable: {error}", file=sys.stderr)
        sys.exit(1)
