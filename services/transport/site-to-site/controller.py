#!/usr/bin/env python3
"""Persistent, serialized site-to-site device controller; no automatic fallback."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

import egress
import managed
from router import Router

CONFIG = Path("/etc/vpn-s2s/config.json")
STATE = Path("/var/lib/vpn-s2s/state.json")
LOCK = Path("/run/lock/timeweb-s2s.lock")


def private_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o077:
        raise ValueError("unsafe_controller_file")
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("invalid_controller_schema")
    return value


def write(path, value):
    fd, name = tempfile.mkstemp(prefix=".s2s-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(value, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Controller:
    def __init__(self, config, state_path=STATE, *, routers=None, clock=time.time):
        self.config, self.path, self.clock = config, Path(state_path), clock
        self.routers = routers or {site: Router(site) for site in managed.SITES}
        self.state = private_json(self.path)
        if not isinstance(self.state.get("clients"), dict) or len(self.state["clients"]) > 64:
            raise ValueError("invalid_client_state")
        if type(self.state.get("generation")) is not int or self.state["generation"] < 0:
            raise ValueError("invalid_state_generation")
        for key, client in self.state["clients"].items():
            if managed.mac(key) != client["mac"] or managed.address(client["ip"]) != client["ip"]:
                raise ValueError("invalid_client_identity")
            if type(client.get("selected")) is not bool or type(client.get("pending")) is not bool:
                raise ValueError("invalid_client_mode")

    def save(self):
        self.state["generation"] += 1
        write(self.path, self.state)

    def audit(self, action, device, success, error=None):
        entry = dict(timestamp=self.clock(), action=action, device=device, success=success,
                     generation=self.state["generation"], error=error)
        fd = os.open(self.path.with_name("actions.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(entry, separators=(",", ":")) + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)

    def validate_site(self, site, snapshot):
        clients = self.state["clients"].values()
        if managed.outside_hash(snapshot["export"], clients) != self.config["baseline"][site]:
            raise ValueError("router_configuration_drift:" + site)
        known = set()
        for client in self.state["clients"].values():
            prefix = managed.owner(client)
            if prefix != egress.OWNER:
                known.update(spec["values"]["comment"] for spec in managed.policy(client) if spec["site"] == site)
                if site == "fethiye":
                    known.add(prefix + ":binding")
            expected = client.get("hashes", {}).get(site)
            if expected is not None and managed.owned_hash(snapshot["export"], client, clients) != expected:
                raise ValueError("client_configuration_drift:" + site)
        for path in managed.PATHS:
            for row in snapshot[path]:
                comment = row.get("comment", "")
                if comment.startswith(managed.OWNER + ":") and comment not in known:
                    raise ValueError("unregistered_controller_object:" + site)
        legacy = dict(ip=egress.CLIENT, mac=egress.MAC)
        if managed.owned_hash(snapshot["export"], legacy) != self.config["legacy_hashes"][site]:
            raise ValueError("legacy_transport_drift:" + site)
        if site == "fethiye":
            servers = [r for r in snapshot["servers"] if r.get("name") == self.config["dhcp_server"]]
            if len(servers) != 1 or servers[0].get("interface") != "bridge":
                raise ValueError("dhcp_server_drift")
            observed = managed.leases(snapshot["leases"], self.config["dhcp_server"])
            for key, client in self.state["clients"].items():
                if client.get("hashes") and (key not in observed or observed[key]["ip"] != client["ip"]):
                    raise ValueError("selected_lease_identity_changed")
                binding = client.get("binding")
                if binding and key in observed and not self.unapplied(client, snapshot):
                    row = next(r for r in snapshot["leases"] if r[".id"] == observed[key]["lease"])
                    if managed.lease_persistent(row) != binding["before"]:
                        raise ValueError("client_lease_properties_changed")
                if client.get("hashes") and not client["pending"]:
                    controls = managed.control_rows({site: snapshot}, client)
                    if any(c["row"]["disabled"] != (not client["selected"]) for c in controls):
                        raise ValueError("device_mode_drift")
            flows = [r for r in snapshot["/ip firewall filter"] if r.get("comment") == egress.OWNER + ":flow-0"]
            if len(flows) != 1 or flows[0].get("src-mac-address") != egress.MAC:
                raise ValueError("legacy_mac_enforcement_missing")
            if egress.MAC not in self.state["clients"]:
                if any(not x["row"]["disabled"] for x in managed.control_rows({site: snapshot}, legacy)):
                    raise ValueError("unmanaged_legacy_remote_mode")

    def inspect(self):
        snapshots, errors = {}, {}
        for site, router in self.routers.items():
            try:
                snapshot = router.snapshot()
                self.validate_site(site, snapshot)
                snapshots[site] = snapshot
            except (RuntimeError, ValueError, KeyError, TypeError):
                errors[site] = "Router unavailable or configuration requires review: " + site
        current = managed.leases(snapshots["fethiye"]["leases"], self.config["dhcp_server"]) if "fethiye" in snapshots else {}
        ready = transport_up = False
        if len(snapshots) == 2:
            try:
                tunnels = [[r for r in snapshots[site]["tunnels"] if r.get("name") == egress.TUNNEL] for site in managed.SITES]
                transport_up = all(len(items) == 1 and items[0].get("running") is True and items[0].get("disabled") is False for items in tunnels)
                active = self.routers["fethiye"].json('[/routing route print as-value where routing-table="s2s_remote" and active=yes]')
                expected = [r for r in snapshots["fethiye"]["/ip route"] if r.get("comment") == egress.OWNER + ":remote-default"]
                ready = transport_up and len(expected) == 1 and len(active) == 1 and active[0].get(".id") == expected[0][".id"]
            except (RuntimeError, ValueError, TypeError, KeyError):
                ready = False
        devices = []
        for key in sorted(set(current) | {k for k, c in self.state["clients"].items() if c["selected"]}):
            saved = self.state["clients"].get(key)
            live = current.get(key)
            if not (saved and saved["selected"]) and (not live or not live["online"]):
                continue
            item = live or saved
            selected = bool(saved and saved["selected"])
            status = "local"
            if selected:
                status = "unknown"
                if saved["pending"]:
                    status = "pending"
                elif "fethiye" in snapshots:
                    try:
                        controls = managed.control_rows(snapshots, saved)
                        status = ("remote" if ready else "unknown" if errors else "blocked") if all(not x["row"]["disabled"] for x in controls) else "pending"
                    except ValueError:
                        status = "pending"
            devices.append(dict(id=key, label=item["label"], ip=item["ip"], online=bool(live and live["online"]), selected=selected, status=status))
        revision = managed.digest(dict(state=self.state, leases={key: dict(ip=v["ip"], lease=v["lease"], online=v["online"]) for key, v in sorted(current.items())}, validated=sorted(snapshots)))
        pending = any(c["pending"] for c in self.state["clients"].values())
        warning = "Selection is pending; local internet may still be in use. Remove or retry the operation." if pending else None
        result = dict(available=len(snapshots) == 2 and ready and not pending, can_remove="fethiye" in snapshots, revision=revision, checked_at=self.clock(),
                      tunnel=dict(state="up" if transport_up else "unknown" if errors else "down", path="TimeWeb",
                                  egress="route-ready" if ready else "unknown" if errors else "blocked",
                                  detail="Route readiness, not client HTTPS acceptance"),
                      devices=devices, error="; ".join(errors.values()) or warning)
        return result, snapshots, current

    def find(self, snapshot, spec):
        found = [r for r in snapshot[spec["path"]] if r.get("comment") == spec["values"]["comment"]]
        if len(found) > 1 or found and not managed.matches(found[0], spec):
            raise ValueError("client_object_conflict")
        if found:
            managed.exact_object(snapshot["export"], spec, found[0])
            managed.anchor_order(snapshot["export"], spec)
            if spec["anchor"] is not None:
                anchor = spec["anchor"]
                anchors = [r for r in snapshot[spec["path"]] if r.get("comment") == (anchor[1] if isinstance(anchor, tuple) else anchor)
                           and (not isinstance(anchor, tuple) or r.get("chain") == anchor[0])]
                if len(anchors) != 1 or snapshot[spec["path"]].index(found[0]) >= snapshot[spec["path"]].index(anchors[0]):
                    raise ValueError("client_object_anchor_order_changed")
        return found[0] if found else None

    def unapplied(self, client, snapshot):
        if client.get("hashes") or managed.owner(client) == egress.OWNER:
            return False
        prefix = managed.owner(client) + ":"
        return not any(r.get("comment", "").startswith(prefix) for p in managed.PATHS for r in snapshot[p])

    def prepare(self, client, snapshots):
        if managed.owner(client) == egress.OWNER:
            return snapshots
        f = self.routers["fethiye"]
        fresh = managed.leases(f.rows("/ip dhcp-server lease"), self.config["dhcp_server"])
        selected = fresh.get(client["mac"])
        if not selected or not selected["online"] or selected["ip"] != client["ip"]:
            raise ValueError("lease_changed_before_binding")
        client["lease"] = selected["lease"]
        leases = f.rows("/ip dhcp-server lease")
        candidates = [r for r in leases if r.get(".id") == client["lease"] and r.get("mac-address") == client["mac"]
                      and r.get("address") == client["ip"] and r.get("server") == self.config["dhcp_server"]]
        if len(candidates) != 1:
            raise ValueError("lease_changed_before_binding")
        lease = candidates[0]
        dynamic = f.json('[/ip dhcp-server lease get ' + managed.identity(lease[".id"]) + ' dynamic]')
        if type(dynamic) is not bool:
            raise ValueError("untyped_lease_flag")
        if "binding" not in client:
            client["binding"] = dict(converted=dynamic, before=managed.lease_persistent(lease), server=self.config["dhcp_server"])
            self.save()
        if dynamic:
            f.mutate(managed.make_static(client, self.config["dhcp_server"]))
        for spec in managed.policy(client):
            snapshot = snapshots[spec["site"]]
            if self.find(snapshot, spec):
                continue
            anchor_id = None
            if spec["anchor"] is not None:
                anchor = spec["anchor"]
                candidates = [r for r in snapshot[spec["path"]] if r.get("comment") == (anchor[1] if isinstance(anchor, tuple) else anchor)
                              and (not isinstance(anchor, tuple) or r.get("chain") == anchor[0])]
                if len(candidates) != 1:
                    raise ValueError("ambiguous_client_anchor")
                anchor_id = managed.identity(candidates[0][".id"])
            self.routers[spec["site"]].mutate(managed.add_command(spec, anchor_id))
        snapshots = {site: router.snapshot() for site, router in self.routers.items()}
        for spec in managed.policy(client):
            if not self.find(snapshots[spec["site"]], spec):
                raise ValueError("client_preparation_not_confirmed")
        rule_rows = snapshots["fethiye"]["/routing rule"]
        prefix = managed.owner(client) + ":"
        positions = [next(i for i, r in enumerate(rule_rows) if r.get("comment") == prefix + suffix) for suffix in managed.RULES]
        if positions != sorted(positions):
            raise ValueError("client_bypass_order_changed")
        managed.rule_order(snapshots["fethiye"]["export"], client)
        return snapshots

    def action(self, action, device, revision):
        if action not in ("add", "remove"):
            raise ValueError("invalid_action")
        managed.mac(device)
        before, snapshots, current = self.inspect()
        if not isinstance(revision, str) or not secrets.compare_digest(revision, before["revision"]):
            raise ValueError("device_list_changed_refresh_and_retry")
        resuming = bool(self.state["clients"].get(device, {}).get("pending"))
        if not before["can_remove"] or action == "add" and not (before["available"] or resuming and len(snapshots) == 2 and before["tunnel"]["state"] == "up"):
            raise ValueError("validated_route_unavailable")
        client = self.state["clients"].get(device)
        if action == "add":
            if device not in current or not current[device]["online"]:
                raise ValueError("device_not_online")
            if client and client["selected"] and not client["pending"]:
                raise ValueError("device_already_selected")
            if not client:
                if len(self.state["clients"]) >= 64:
                    raise ValueError("device_limit_reached")
                client = dict(current[device], selected=False, pending=False)
                self.state["clients"][device] = client
            elif client["ip"] != current[device]["ip"]:
                raise ValueError("pinned_device_address_changed")
            client["lease"] = current[device]["lease"]
        elif not client or not client["selected"]:
            raise ValueError("device_not_selected")
        if action == "remove" and self.unapplied(client, snapshots["fethiye"]):
            live = current.get(device)
            dynamic = (self.routers["fethiye"].json('[/ip dhcp-server lease get ' + managed.identity(live["lease"]) + ' dynamic]') if live else True)
            if type(dynamic) is not bool:
                raise ValueError("untyped_lease_flag")
            if dynamic:
                # No rule was installed and no static binding applied: don't flush
                # an old address that may now belong to a different device.
                del self.state["clients"][device]
                self.save()
                self.audit(action, device, True)
                return dict(self.inspect()[0], success=True)
        # A pending removal remains visible until Local is positively observed.
        client.update(selected=True, pending=True, operation=action)
        self.save()
        try:
            if action == "add":
                snapshots = self.prepare(client, snapshots)
                for site, snapshot in snapshots.items():
                    if managed.outside_hash(snapshot["export"], self.state["clients"].values()) != self.config["baseline"][site]:
                        raise ValueError("unexpected_preparation_delta")
                client["hashes"] = {site: managed.owned_hash(s["export"], client, self.state["clients"].values()) for site, s in snapshots.items()}
                self.save()
            controls = managed.control_rows(snapshots, client, partial=action == "remove" and not client.get("hashes"))
            for command in managed.mode_commands(client, controls, action == "add"):
                self.routers["fethiye"].mutate(command)
            after = self.routers["fethiye"].snapshot()
            self.validate_site("fethiye", after)
            observed = managed.control_rows({"fethiye": after}, client, partial=action == "remove" and not client.get("hashes"))
            if any(item["row"]["disabled"] != (action == "remove") for item in observed):
                raise ValueError("device_mode_not_confirmed")
            client.update(selected=action == "add", pending=False, operation=None)
            self.save()
            self.audit(action, device, True)
        except (RuntimeError, ValueError, KeyError, TypeError):
            if action == "remove":
                client["selected"] = True
            self.save()
            self.audit(action, device, False, "Device operation incomplete; inspect controller state")
            result = self.inspect()[0]
            return dict(result, success=False, error="Device operation incomplete; selection retained for review")
        return dict(self.inspect()[0], success=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "add", "remove"))
    parser.add_argument("device", nargs="?")
    parser.add_argument("revision", nargs="?")
    args = parser.parse_args()
    os.umask(0o077)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        controller = Controller(private_json(CONFIG))
        if args.action == "status":
            if args.device is not None or args.revision is not None:
                raise ValueError("invalid_status_arguments")
            result = controller.inspect()[0]
        else:
            try:
                result = controller.action(args.action, args.device, args.revision)
            except ValueError as exc:
                messages = {
                    "device_list_changed_refresh_and_retry": "Device list changed. Refresh and retry.",
                    "validated_route_unavailable": "Validated route unavailable. No device settings were changed.",
                    "device_not_online": "Device is not online. Refresh the device list.",
                    "device_already_selected": "Device is already selected.",
                    "device_not_selected": "Device is not selected.",
                    "pinned_device_address_changed": "Device address changed. Operator review is required.",
                    "device_limit_reached": "Device limit reached.",
                }
                if str(exc) not in messages:
                    raise
                result = dict(controller.inspect()[0], success=False, error=messages[str(exc)])
        print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, TypeError):
        print(json.dumps(dict(success=False, error="Controller unavailable or request rejected; refresh and inspect state")))
        raise SystemExit(1)
