"""Pure device policy for the Fethiye-to-Nakhimova console controller."""
import hashlib
import ipaddress
import json
import math
import re
import shlex

import egress

OWNER = "s2s-console-v1"
SITES = {"fethiye": "HM20B6QXS8H", "nakhimova": "HKM0BDXYG74"}
PATHS = ("/ip firewall filter", "/ipv6 firewall filter", "/ip firewall nat",
         "/routing rule", "/ip route")
GUARDS = ("wan-guard", "ipv6-forward", "ipv6-dns-udp", "ipv6-dns-tcp")
DNS = ("dns-udp", "dns-tcp")
RULES = ("bypass-68", "bypass-88", "bypass-89", "client-route")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def mac(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", value):
        raise ValueError("invalid_device")
    if int(value[:2], 16) & 1 or value in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"):
        raise ValueError("invalid_device")
    return value


def address(value, subnet="192.168.89.0/24"):
    if subnet not in ("192.168.89.0/24", "192.168.88.0/24"):
        raise ValueError("invalid_device_subnet")
    parsed = ipaddress.ip_address(value)
    if parsed not in ipaddress.ip_network(subnet) or parsed.packed[-1] in (0, 1, 255):
        raise ValueError("invalid_device_address")
    return str(parsed)


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"\*[0-9A-Fa-f]+", value):
        raise ValueError("invalid_router_object")
    return value


def owner(client):
    return egress.OWNER if client["mac"] == egress.MAC and client["ip"] == egress.CLIENT else OWNER + ":" + mac(client["mac"]).replace(":", "").lower()


def leases(rows, server, subnet="192.168.89.0/24"):
    result = {}
    addresses = set()
    for row in rows:
        if row.get("server") != server:
            continue
        try:
            key = mac(row.get("mac-address"))
            ip = address(row.get("address"), subnet)
        except (ValueError, TypeError):
            continue
        if key in result or ip in addresses:
            raise ValueError("ambiguous_device_lease")
        addresses.add(ip)
        label = "".join(c if ord(c) >= 32 else " " for c in str(row.get("host-name") or key))[:120]
        result[key] = {"mac": key, "ip": ip, "label": label,
                       "online": row.get("status") == "bound", "lease": identity(row[".id"])}
    return result


def policy(client):
    """Return exact per-client objects; shared transport remains immutable."""
    ip, key = address(client["ip"]), mac(client["mac"])
    prefix = owner(client)
    if prefix == egress.OWNER:
        return []
    objects = []

    def add(site, path, suffix, values, anchor=None, control=False):
        values = dict(values, comment=prefix + ":" + suffix)
        objects.append(dict(site=site, path=path, suffix=suffix, values=values,
                            anchor=anchor, control=control))

    anchor = egress.OWNER + ":forward-deny"
    for site in SITES:
        if site == "fethiye":
            first = dict(chain="s2s-egress-forward", action="accept", **{"in-interface": "bridge", "out-interface": egress.TUNNEL,
                         "src-address": ip + "/32", "src-mac-address": key, "connection-state": "new,established,related"})
            second = dict(chain="s2s-egress-forward", action="accept", **{"in-interface": egress.TUNNEL, "out-interface": "bridge",
                          "dst-address": ip + "/32", "connection-state": "established,related"})
        else:
            first = dict(chain="s2s-egress-forward", action="accept", **{"in-interface": egress.TUNNEL, "out-interface": "ether1",
                         "src-address": ip + "/32", "dst-address-list": "!s2s-egress-not-internet", "connection-state": "new,established,related"})
            second = dict(chain="s2s-egress-forward", action="accept", **{"in-interface": "ether1", "out-interface": egress.TUNNEL,
                          "dst-address": ip + "/32", "connection-state": "established,related"})
        add(site, "/ip firewall filter", "flow-0", first, anchor)
        add(site, "/ip firewall filter", "flow-1", second, anchor)
    fanchor = "s2s-pilot-20261016:forward-in"
    add("fethiye", "/ip firewall filter", "wan-guard", dict(chain="forward", action="drop", **{
        "in-interface": "bridge", "out-interface": "ether1", "src-mac-address": key,
        "dst-address": "!192.168.68.0/24"}), fanchor, True)
    add("fethiye", "/ipv6 firewall filter", "ipv6-forward", dict(chain="forward", action="drop", **{
        "in-interface": "bridge", "src-mac-address": key}), ("forward", "defconf: accept established,related,untracked"), True)
    for protocol in ("udp", "tcp"):
        add("fethiye", "/ipv6 firewall filter", "ipv6-dns-" + protocol, dict(chain="input", action="drop", protocol=protocol, **{
            "in-interface": "bridge", "src-mac-address": key, "dst-port": "53"}), ("input", "defconf: accept established,related,untracked"), True)
        add("fethiye", "/ip firewall nat", "dns-" + protocol, dict(chain="dstnat", action="dst-nat", protocol=protocol, **{
            "in-interface": "bridge", "src-mac-address": key, "dst-port": "53", "to-addresses": egress.DNS, "to-ports": "53"}), None, True)
    for subnet in (68, 88, 89):
        add("fethiye", "/routing rule", "bypass-" + str(subnet), dict(action="lookup-only-in-table", table="main", **{
            "src-address": ip + "/32", "dst-address": f"192.168.{subnet}.0/24"}), None, True)
    add("fethiye", "/routing rule", "client-route", dict(action="lookup-only-in-table", table="s2s_remote", **{"src-address": ip + "/32"}), None, True)
    add("nakhimova", "/ip route", "return-route", dict(gateway="10.60.61.2@main", distance="1", **{"dst-address": ip + "/32", "routing-table": "s2s_return"}))
    add("nakhimova", "/ip route", "return-blackhole", dict(blackhole=True, distance="254", **{"dst-address": ip + "/32", "routing-table": "s2s_return"}))
    add("nakhimova", "/routing rule", "return-rule", dict(interface="ether1", action="lookup-only-in-table", table="s2s_return", **{
        "dst-address": ip + "/32"}), "GLOBAL: Local bypass for ALL")
    return objects


def field(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError("invalid_property")
    return value


def quote(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_:.@/!, -]+", value):
        raise ValueError("unsafe_router_value")
    return '"' + value + '"'


def add_command(spec, anchor_id=None):
    command = spec["path"] + " add "
    if spec["control"]:
        command += "disabled=yes "
    for key, value in spec["values"].items():
        command += field(key) + "=" + ("yes" if value is True else quote(value)) + " "
    if spec["anchor"] is not None:
        command += "place-before=" + identity(anchor_id)
    return command.rstrip()


def norm(value, key):
    if key in ("blackhole", "disabled"):
        if type(value) is bool:
            return value
        if value in ("yes", "true", "no", "false"):
            return value in ("yes", "true")
        raise ValueError("invalid_boolean_field")
    if key.endswith("address") or key in ("src-address", "dst-address"):
        negated = str(value).startswith("!")
        try:
            return ("!" if negated else "") + str(ipaddress.ip_network(str(value).lstrip("!"), strict=False))
        except ValueError:
            return str(value)
    if key == "connection-state":
        return sorted(value if isinstance(value, list) else value.split(","))
    if key in ("distance", "dst-port", "to-ports"):
        if type(value) in (int, float) and math.isfinite(value) and int(value) == value:
            return str(int(value))
        if isinstance(value, str) and re.fullmatch(r"[0-9]+(?:[.]0+)?", value):
            return str(int(float(value)))
    if isinstance(value, bool):
        return value
    return str(value)


def matches(row, spec):
    return all(norm(row.get(k), k) == norm(v, k) for k, v in spec["values"].items())


def tokens(line):
    path, marker, tail = line.partition(" add ")
    if not marker:
        return path, {}
    values = {}
    for token in shlex.split(tail):
        key, equal, value = token.partition("=")
        if key in values:
            raise ValueError("duplicate_export_property")
        values[key] = value if equal else True
    return path, values


def exact_object(text, spec, row):
    found = [line for line in export_lines(text) if line_comment(line) == spec["values"]["comment"]]
    if len(found) != 1 or not matches(row, spec) or type(row.get("disabled")) is not bool:
        raise ValueError("client_object_not_exact")
    path, values = tokens(found[0])
    defaults = {"log": "no", "log-prefix": ""}
    if path == "/ip route":
        defaults = {"scope": "30", "target-scope": "10", "suppress-hw-offload": "no", "check-gateway": "none"}
    allowed = dict(spec["values"], disabled="yes" if row["disabled"] else "no")
    if path != spec["path"] or any(key not in allowed and defaults.get(key) != value for key, value in values.items()):
        raise ValueError("unexpected_client_object_selector")
    if not spec["control"] and row["disabled"]:
        raise ValueError("disabled_client_infrastructure")
    implicit = {"action": "accept", "distance": "1", "disabled": "no"}
    if any(norm(values.get(key, implicit.get(key)), key) != norm(value, key) for key, value in allowed.items()):
        raise ValueError("client_export_value_differs_from_rows")


LEASE_RUNTIME = {".id", "dynamic", "status", "expires-after", "last-seen", "host-name", "active-address",
                 "active-mac-address", "active-client-id", "active-server", "radius", "blocked"}


def lease_persistent(row):
    return {k: v for k, v in row.items() if k not in LEASE_RUNTIME}


def make_static(client, server):
    lease = identity(client["lease"])
    expected = {"mac-address": mac(client["mac"]), "address": address(client["ip"]), "server": server, "status": "bound"}
    checks = " or ".join('([:tostr [/ip dhcp-server lease get ' + lease + ' ' + key + ']] != ' + quote(value) + ')' for key, value in expected.items())
    return ':if (' + checks + ') do={:error "lease_identity_changed"}; /ip dhcp-server lease make-static ' + lease


def anchor_order(text, spec):
    if spec["anchor"] is None:
        return
    anchor = spec["anchor"]
    comment = anchor[1] if isinstance(anchor, tuple) else anchor
    entries = [tokens(line) for line in export_lines(text)]
    own = [i for i, (path, values) in enumerate(entries) if path == spec["path"] and values.get("comment") == spec["values"]["comment"]]
    anchors = [i for i, (path, values) in enumerate(entries) if path == spec["path"] and values.get("comment") == comment
               and (not isinstance(anchor, tuple) or values.get("chain") == anchor[0])]
    if len(own) != 1 or len(anchors) != 1 or own[0] >= anchors[0]:
        raise ValueError("client_export_anchor_order_changed")


def rule_order(text, client):
    prefix = owner(client) + ":"
    comments = [values.get("comment") for path, values in (tokens(line) for line in export_lines(text)) if path == "/routing rule"]
    positions = []
    for suffix in RULES:
        if comments.count(prefix + suffix) != 1:
            raise ValueError("ambiguous_client_export_rule")
        positions.append(comments.index(prefix + suffix))
    if positions != sorted(positions):
        raise ValueError("client_export_bypass_order_changed")


def control_rows(snapshots, client, partial=False):
    prefix = owner(client)
    result = []
    for suffix, path in egress.CONTROL_PATHS.items():
        found = [r for r in snapshots["fethiye"][path] if r.get("comment") == prefix + ":" + suffix]
        if partial and not found:
            continue
        if len(found) != 1 or type(found[0].get("disabled")) is not bool:
            raise ValueError("ambiguous_or_untyped_control")
        identity(found[0][".id"])
        result.append(dict(path=path, suffix=suffix, row=found[0]))
    return result


def mode_commands(client, controls, remote):
    """Guards first on entry and last on exit; never flush global conntrack."""
    ip = address(client["ip"])
    by_name = {item["suffix"]: item for item in controls}
    if remote and set(by_name) != set(egress.CONTROL_PATHS):
        raise ValueError("incomplete_remote_controls")
    pattern = '"^' + ip.replace(".", "[.]") + '(:|\\$)"'
    clear = [f'/ip firewall connection remove [find where {name}~{pattern}]' for name in ("src-address", "dst-address")]

    def change(names, verb):
        return [by_name[name]["path"] + " " + verb + " " + identity(by_name[name]["row"][".id"])
                for name in names if name in by_name]
    if remote:
        return change(GUARDS, "enable") + clear + change(DNS + RULES, "enable") + clear
    return change(RULES + DNS, "disable") + clear + change(GUARDS[1:] + GUARDS[:1], "disable")


def export_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def line_comment(line):
    try:
        return next((s.split("=", 1)[1] for s in shlex.split(line) if s.startswith("comment=")), "")
    except ValueError as exc:
        raise ValueError("unparseable_router_export") from exc


def projection(text, clients=()):
    """Reject unknown namespace use and preserve each owned rule's baseline rank."""
    registry = {s["values"]["comment"]: s["path"] for c in clients for s in policy(c)}
    converted = {(c["mac"], c["ip"]): c for c in clients if c.get("binding", {}).get("converted")}
    lines, owned = [], []
    for line in export_lines(text):
        path, values = tokens(line)
        comment = values.get("comment", "")
        if comment.startswith(OWNER + ":"):
            if registry.get(comment) != path:
                raise ValueError("unregistered_controller_export_object")
            normalized = re.sub(r"(?<![\w-])disabled=(yes|no)\s*", "", line) if comment.rsplit(":", 1)[-1] in egress.CONTROL_PATHS else line
            owned.append((comment, len(lines), normalized.rstrip()))
            continue
        if path == "/ip dhcp-server lease" and (values.get("mac-address"), values.get("address")) in converted:
            client = converted[values["mac-address"], values["address"]]
            if values.get("server") != client["binding"]["server"]:
                raise ValueError("converted_lease_server_drift")
            owned.append((owner(client) + ":binding", len(lines), line))
            continue
        if comment.startswith(egress.OWNER + ":") and comment.removeprefix(egress.OWNER + ":") in egress.CONTROL_PATHS:
            line = re.sub(r"(?<![\w-])disabled=(yes|no)\s*", "", line)
        lines.append(line.rstrip())
    return lines, owned


def outside_hash(text, clients=()):
    return digest(projection(text, clients)[0])


def owned_hash(text, client, clients=()):
    prefix = owner(client) + ":"
    if owner(client) != egress.OWNER:
        return digest([item for item in projection(text, clients or (client,))[1] if item[0].startswith(prefix)])
    result = []
    for line in export_lines(text):
        comment = line_comment(line)
        if comment.startswith(prefix):
            if comment.removeprefix(prefix) in egress.CONTROL_PATHS:
                line = re.sub(r"(?<![\w-])disabled=(yes|no)\s*", "", line)
            result.append(line.rstrip())
    return digest(result)


def management_guard(before):
    if before != egress.guard_rules(egress.lan_guard()):
        raise ValueError("unknown_hub_guard_baseline")
    after, boundary, forward = before.partition(' chain forward')
    if not boundary:
        raise ValueError("missing_hub_forward_boundary")
    for chain, iface in (("input", "iifname"), ("output", "oifname")):
        anchor = f'  {iface} "wg-s2s" counter drop\n'
        if after.count(anchor) != 1:
            raise ValueError("ambiguous_hub_management_anchor")
        additions = ""
        for peer in (2, 3):
            if chain == "output":
                selector = f'ip saddr 10.60.60.1 ip daddr 10.60.60.{peer} tcp dport 22 ct state {{ new, established }}'
            else:
                selector = f'ip saddr 10.60.60.{peer} ip daddr 10.60.60.1 tcp sport 22 ct state established'
            additions += f'  {iface} "wg-s2s" {selector} counter accept\n'
        after = after.replace(anchor, additions + anchor)
    return after + boundary + forward
