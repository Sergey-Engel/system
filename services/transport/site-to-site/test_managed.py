import copy
import importlib.util
import json
import shlex
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import egress
import managed
from controller import Controller, write
from router import Router

CLIENT = dict(mac="02:11:22:33:44:66", ip="192.168.89.150", label="Test laptop", lease="*99", online=True)


@pytest.mark.parametrize("value", ["ff:ff:ff:ff:ff:ff", "FF:FF:FF:FF:FF:FF", "01:11:22:33:44:55", "02:11:22:33:44:66; reboot", None])
def test_device_mac_is_strict_unicast(value):
    with pytest.raises(ValueError): managed.mac(value)


@pytest.mark.parametrize("value", ["192.168.68.150", "192.168.89.1", "192.168.89.255", "::1"])
def test_device_address_stays_in_managed_lan(value):
    with pytest.raises(ValueError): managed.address(value)


def test_policy_has_ten_controls_and_narrow_forward_and_return_rules():
    policy = managed.policy(CLIENT)
    controls = [s for s in policy if s["control"]]
    assert len(controls) == 10
    assert {s["suffix"] for s in controls} == set(egress.CONTROL_PATHS)
    assert len(policy) == 17
    assert not any(s["path"] == "/routing table" for s in policy)
    for spec in policy:
        values = spec["values"]
        assert values["comment"].startswith(managed.OWNER)
        if spec["site"] == "nakhimova" and spec["path"] == "/routing rule":
            assert values["interface"] == "ether1" and values["dst-address"] == CLIENT["ip"] + "/32"
    assert managed.policy(dict(mac=egress.MAC, ip=egress.CLIENT)) == []


def test_mode_order_and_conntrack_are_client_scoped():
    controls = [dict(path=path, suffix=name, row={".id": "*" + format(i + 1, "x"), "disabled": True}) for i, (name, path) in enumerate(egress.CONTROL_PATHS.items())]
    add = managed.mode_commands(CLIENT, controls, True)
    remove = managed.mode_commands(CLIENT, controls, False)
    assert all(" enable " in c for c in add[:4])
    assert " disable " in remove[0] and remove[-1].startswith("/ip firewall filter disable")
    for command in add + remove:
        if "connection remove" in command:
            assert '"^192[.]168[.]89[.]150(:|\\$)"' in command
    with pytest.raises(ValueError): managed.mode_commands(CLIENT, controls[:-1], True)


def test_management_access_is_exact_ssh_pair_not_general_transit():
    before = egress.guard_rules(egress.lan_guard())
    after = managed.management_guard(before)
    assert after.count("tcp dport 22") == 2 and after.count("tcp sport 22") == 2
    assert after.split(" chain forward")[1] == before.split(" chain forward")[1]
    assert "ct state established counter accept" in after
    with pytest.raises(ValueError): managed.management_guard(before.replace("priority -50", "priority -40"))


def test_export_ownership_does_not_hide_unrelated_config_or_legacy_attributes():
    outside = '/ip address add address=192.168.89.1/24 interface=bridge'
    line = f'/ip firewall filter add action=drop comment={egress.OWNER}:wan-guard disabled=yes'
    ours = f'/ip firewall filter add action=drop comment={managed.owner(CLIENT)}:wan-guard disabled=yes'
    assert managed.outside_hash(outside + "\n" + line) == managed.outside_hash(outside + "\n" + line.replace("disabled=yes", "") + "\n" + ours, [CLIENT])
    with pytest.raises(ValueError): managed.outside_hash(outside + "\n" + ours)
    assert managed.outside_hash(outside + "\n" + line) != managed.outside_hash(outside + "\n" + line.replace("drop", "accept"))
    assert managed.outside_hash(outside) != managed.outside_hash(outside.replace("89.1", "89.2"))


def test_leases_refuse_duplicate_ip_or_mac_and_exclude_deco():
    row = {".id": "*1", "server": "defconf", "address": CLIENT["ip"], "mac-address": CLIENT["mac"], "status": "bound"}
    assert list(managed.leases([row], "defconf")) == [CLIENT["mac"]]
    assert managed.leases([{**row, "address": "192.168.68.115"}], "defconf") == {}
    with pytest.raises(ValueError): managed.leases([row, row], "defconf")
    with pytest.raises(ValueError): managed.leases([row, {**row, "mac-address": "02:11:22:33:44:88"}], "defconf")


class FakeRouter:
    def __init__(self, site):
        self.site, self.commands = site, []
        self.fail = False
        self.data = {path: [] for path in managed.PATHS}
        self.data.update(export="/ip address add address=192.168.89.1/24 interface=bridge", tunnels=[dict(name=egress.TUNNEL, running=True, disabled=False)])
        self.data["/ip route"] = [{".id": "*A", "comment": egress.OWNER + ":remote-default"}]
        if site == "fethiye":
            self.data.update(servers=[dict(name="defconf", interface="bridge")], leases=[{
                ".id": "*99", "mac-address": egress.MAC, "address": egress.CLIENT, "server": "defconf", "status": "bound", "host-name": "MacBook"}])
            for index, (name, path) in enumerate(egress.CONTROL_PATHS.items()):
                self.data[path].append({".id": "*" + format(index + 1, "X"), "comment": egress.OWNER + ":" + name, "disabled": True})
            self.data["/ip firewall filter"].append({".id": "*FE", "comment": egress.OWNER + ":flow-0", "disabled": False,
                                                    "src-mac-address": egress.MAC})

    def snapshot(self):
        if self.fail: raise RuntimeError("unavailable")
        return copy.deepcopy(self.data)

    def json(self, expr):
        return [{".id": "*A"}]

    def run(self, command):
        self.commands.append(command)
        if "connection remove" in command: return ""
        path, verb, identity = command.rsplit(" ", 2)
        row = next(r for r in self.data[path] if r[".id"] == identity)
        row["disabled"] = verb == "disable"
        return ""

    def mutate(self, command):
        return self.run(command)


def instance(tmp_path):
    routers = {site: FakeRouter(site) for site in managed.SITES}
    legacy = dict(ip=egress.CLIENT, mac=egress.MAC)
    config = dict(dhcp_server="defconf", baseline={site: managed.outside_hash(r.data["export"]) for site, r in routers.items()},
                  legacy_hashes={site: managed.owned_hash(r.data["export"], legacy) for site, r in routers.items()})
    path = tmp_path / "state.json"
    write(path, dict(version=1, generation=0, clients={}))
    return Controller(config, path, routers=routers, clock=lambda: 100), routers


def test_legacy_add_remove_persist_and_do_not_write_other_router(tmp_path):
    c, routers = instance(tmp_path)
    before = c.inspect()[0]
    assert before["available"] is True and before["devices"][0]["selected"] is False
    after = c.action("add", egress.MAC, before["revision"])
    assert after["success"] is True and after["devices"][0]["status"] == "remote"
    assert routers["nakhimova"].commands == []
    reloaded = Controller(c.config, c.path, routers=routers, clock=lambda: 100)
    assert reloaded.inspect()[0]["devices"][0]["selected"] is True
    after = reloaded.action("remove", egress.MAC, after["revision"])
    assert after["success"] is True and after["devices"][0]["selected"] is False
    assert json.loads(c.path.read_text())["clients"][egress.MAC]["selected"] is False
    assert all(x["row"]["disabled"] for x in managed.control_rows({"fethiye": routers["fethiye"].data}, dict(ip=egress.CLIENT, mac=egress.MAC)))


def test_stale_list_and_drift_refuse_before_writes(tmp_path):
    c, routers = instance(tmp_path)
    before = c.inspect()[0]
    routers["fethiye"].data["leases"][0]["address"] = "192.168.89.198"
    with pytest.raises(ValueError): c.action("add", egress.MAC, before["revision"])
    assert not routers["fethiye"].commands
    routers["fethiye"].data["export"] += "\n/ip service set ssh disabled=yes"
    assert c.inspect()[0]["available"] is False
    with pytest.raises(ValueError): c.action("add", egress.MAC, c.inspect()[0]["revision"])
    assert not routers["fethiye"].commands


def test_remove_still_works_when_remote_router_is_unavailable(tmp_path):
    c, routers = instance(tmp_path)
    c.action("add", egress.MAC, c.inspect()[0]["revision"])
    routers["nakhimova"].fail = True
    current = c.inspect()[0]
    assert not current["available"] and current["can_remove"]
    assert current["devices"][0]["status"] == "unknown"
    assert c.action("remove", egress.MAC, current["revision"])["success"] is True


def test_failed_entry_keeps_persistent_intent_and_existing_guards(tmp_path):
    c, routers = instance(tmp_path)
    run = routers["fethiye"].run
    def fail(command):
        if command.startswith("/ip firewall nat enable"): raise RuntimeError("write_failed")
        return run(command)
    routers["fethiye"].run = fail
    result = c.action("add", egress.MAC, c.inspect()[0]["revision"])
    assert result["success"] is False
    assert result["devices"][0]["selected"] and result["devices"][0]["status"] == "pending"
    guards = [x for x in managed.control_rows({"fethiye": routers["fethiye"].data}, dict(ip=egress.CLIENT, mac=egress.MAC)) if x["suffix"] in managed.GUARDS]
    assert all(not x["row"]["disabled"] for x in guards)
    assert not any(" disable " in command for command in routers["fethiye"].commands)
    assert c.action("remove", egress.MAC, c.inspect()[0]["revision"])["success"] is True


def test_router_adapter_is_pinned_and_does_not_return_command_errors(tmp_path):
    class Result:
        returncode, stdout = 0, 'failure: secret material'
    calls = []
    def runner(args, **kwargs):
        calls.append(args)
        return Result()
    r = Router("fethiye", runner=runner, config=tmp_path / "config", runtime=tmp_path)
    with pytest.raises(RuntimeError, match="router_command_failed:fethiye"):
        r.run("/export terse")
    assert "StrictHostKeyChecking=yes" in calls[0] and "ForwardAgent=no" in calls[0]


def test_rule_rank_and_foreign_namespace_cannot_be_hidden_by_ownership():
    spec = managed.policy(CLIENT)[0]
    own = managed.add_command(spec, "*A").replace(" place-before=*A", "")
    fixed = '/ip firewall filter add chain=s2s-egress-forward action=drop comment=fixed-deny'
    first, moved = own + "\n" + fixed, fixed + "\n" + own
    assert managed.outside_hash(first, [CLIENT]) == managed.outside_hash(moved, [CLIENT])
    assert managed.owned_hash(first, CLIENT) != managed.owned_hash(moved, CLIENT)
    malicious = f'/ip firewall mangle add chain=prerouting action=mark-routing comment={managed.owner(CLIENT)}:wan-guard'
    with pytest.raises(ValueError): managed.outside_hash(malicious, [CLIENT])


def test_extra_guard_selector_and_disabled_flow_are_rejected_before_pinning():
    guard = next(s for s in managed.policy(CLIENT) if s["suffix"] == "wan-guard")
    row = dict(guard["values"], disabled=True)
    line = managed.add_command(guard, "*A").replace(" place-before=*A", "")
    managed.exact_object(line, guard, row)
    with pytest.raises(ValueError): managed.exact_object(line + " src-address=192.168.89.199", guard, {**row, "src-address": "192.168.89.199"})
    flow = managed.policy(CLIENT)[0]
    with pytest.raises(ValueError): managed.exact_object(managed.add_command(flow, "*A") + " disabled=yes", flow, dict(flow["values"], disabled=True))


def test_crash_during_remove_retains_visible_selection_and_can_resume(tmp_path):
    c, routers = instance(tmp_path)
    c.action("add", egress.MAC, c.inspect()[0]["revision"])
    old = routers["fethiye"].run
    def crash(command): raise KeyboardInterrupt()
    routers["fethiye"].run = crash
    with pytest.raises(KeyboardInterrupt): c.action("remove", egress.MAC, c.inspect()[0]["revision"])
    new = Controller(c.config, c.path, routers=routers, clock=lambda: 100)
    item = new.inspect()[0]["devices"][0]
    assert item["selected"] and item["status"] == "pending"
    routers["fethiye"].run = old
    assert new.action("remove", egress.MAC, new.inspect()[0]["revision"])["success"]


def test_crash_before_first_guard_is_pending_not_remote_and_retry_is_allowed(tmp_path):
    c, routers = instance(tmp_path)
    old = routers["fethiye"].run
    def crash(command): raise KeyboardInterrupt()
    routers["fethiye"].run = crash
    with pytest.raises(KeyboardInterrupt): c.action("add", egress.MAC, c.inspect()[0]["revision"])
    new = Controller(c.config, c.path, routers=routers, clock=lambda: 100)
    status = new.inspect()[0]
    assert status["devices"][0]["status"] == "pending"
    assert "local internet may still" in status["error"]
    routers["fethiye"].run = old
    assert new.action("add", egress.MAC, status["revision"])["success"]


class FullRouter(FakeRouter):
    def __init__(self, site):
        super().__init__(site)
        self.next_id = 256
        self.static = False
        if site == "fethiye":
            self.data["leases"].append({".id": "*99A", "mac-address": CLIENT["mac"], "address": CLIENT["ip"], "server": "defconf", "status": "bound", "host-name": CLIENT["label"]})
        anchors = [("/ip firewall filter", egress.OWNER + ":forward-deny", "s2s-egress-forward"),
                   ("/ip firewall filter", "s2s-pilot-20261016:forward-in", "forward"),
                   ("/routing rule", "GLOBAL: Local bypass for ALL", "")]
        anchors += [("/ipv6 firewall filter", "defconf: accept established,related,untracked", chain) for chain in ("input", "forward")]
        for path, comment, chain in anchors:
            self.data[path].append(dict(comment=comment, chain=chain, disabled=False, **{".id": "*" + format(self.next_id, "X")}))
            self.next_id += 1

    def render(self):
        lines = []
        for path in managed.PATHS:
            for row in self.data[path]:
                parts = []
                for key, value in row.items():
                    if key.startswith("."): continue
                    if key == "disabled" and not value: continue
                    if value is True: parts.append(key if key == "blackhole" else key + "=yes")
                    elif value is not False: parts.append(key + '=' + json.dumps(str(value)))
                lines.append(path + " add " + " ".join(parts))
        if self.static:
            row = next(r for r in self.data["leases"] if r["mac-address"] == CLIENT["mac"])
            lines.append('/ip dhcp-server lease add address=' + row["address"] + ' mac-address=' + row["mac-address"] + ' server=defconf')
        return "\n".join(lines)

    def snapshot(self):
        data = super().snapshot()
        data["export"] = self.render()
        return data

    def rows(self, path): return copy.deepcopy(self.data["leases"] if path == "/ip dhcp-server lease" else self.data[path])

    def json(self, expr):
        if expr.endswith(" dynamic]"): return not self.static
        return super().json(expr)

    def run(self, command):
        if "/ip dhcp-server lease make-static " in command:
            self.commands.append(command)
            row = next(r for r in self.data["leases"] if r[".id"] == command.rsplit(" ", 1)[1])
            assert row["mac-address"] == CLIENT["mac"]
            self.static = True
            return ""
        if " add " in command:
            self.commands.append(command)
            path, tail = command.split(" add ", 1)
            values = dict(token.split("=", 1) for token in shlex.split(tail))
            anchor = values.pop("place-before", None)
            values["disabled"] = values.get("disabled") == "yes"
            if "blackhole" in values: values["blackhole"] = values["blackhole"] == "yes"
            values[".id"] = "*" + format(self.next_id, "X"); self.next_id += 1
            position = next((i for i, r in enumerate(self.data[path]) if r[".id"] == anchor), len(self.data[path]))
            self.data[path].insert(position, values)
            return ""
        return super().run(command)


def full_instance(tmp_path):
    routers = {s: FullRouter(s) for s in managed.SITES}
    legacy = dict(ip=egress.CLIENT, mac=egress.MAC)
    config = dict(dhcp_server="defconf", baseline={s: managed.outside_hash(r.render()) for s,r in routers.items()},
                  legacy_hashes={s: managed.owned_hash(r.render(), legacy) for s,r in routers.items()})
    path = tmp_path / "state.json"
    write(path, dict(version=1, generation=0, clients={}))
    return Controller(config, path, routers=routers, clock=lambda: 100), routers


def test_new_client_full_preparation_and_remove_preserve_other_client(tmp_path):
    c, routers = full_instance(tmp_path)
    c.action("add", egress.MAC, c.inspect()[0]["revision"])
    before = {site: managed.owned_hash(r.render(), dict(ip=egress.CLIENT, mac=egress.MAC)) for site,r in routers.items()}
    result = c.action("add", CLIENT["mac"], c.inspect()[0]["revision"])
    assert result["success"], result
    assert sum(d["selected"] for d in result["devices"]) == 2
    assert all(d["status"] == "remote" for d in result["devices"])
    assert routers["fethiye"].static
    assert before == {site: managed.owned_hash(r.render(), dict(ip=egress.CLIENT, mac=egress.MAC)) for site,r in routers.items()}
    result = c.action("remove", CLIENT["mac"], result["revision"])
    assert result["success"] and sum(d["selected"] for d in result["devices"]) == 1
    assert next(d for d in result["devices"] if d["id"] == egress.MAC)["status"] == "remote"


def test_new_client_uses_fresh_lease_id_and_static_crash_is_recoverable(tmp_path):
    c, routers = full_instance(tmp_path)
    router = routers["fethiye"]
    run = router.run
    def crash(command):
        result = run(command)
        if "/ip dhcp-server lease make-static" in command: raise KeyboardInterrupt()
        return result
    router.run = crash
    with pytest.raises(KeyboardInterrupt): c.action("add", CLIENT["mac"], c.inspect()[0]["revision"])
    router.run = run
    target = next(r for r in router.data["leases"] if r["mac-address"] == CLIENT["mac"])
    target[".id"] = "*FAFA"
    new = Controller(c.config, c.path, routers=routers, clock=lambda: 100)
    status = new.inspect()[0]
    assert status["can_remove"] and any(d["status"] == "pending" for d in status["devices"])
    result = new.action("add", CLIENT["mac"], status["revision"])
    assert result["success"], result
    assert new.state["clients"][CLIENT["mac"]]["lease"] == "*FAFA"


def test_transport_and_egress_readiness_are_separate_observations(tmp_path):
    c, routers = instance(tmp_path)
    routers["fethiye"].json = lambda _: [{".id": "*DEAD"}]
    status = c.inspect()[0]
    assert status["tunnel"]["state"] == "up"
    assert status["tunnel"]["egress"] == "blocked"
    assert not status["available"]


def test_lease_id_change_invalidates_dropdown_revision(tmp_path):
    c, routers = instance(tmp_path)
    old = c.inspect()[0]["revision"]
    routers["fethiye"].data["leases"][0][".id"] = "*FFFE"
    with pytest.raises(ValueError, match="device_list_changed"):
        c.action("add", egress.MAC, old)
    assert not routers["fethiye"].commands


def test_exact_object_rejects_rows_export_value_race_and_accepts_numeric_json():
    guard = next(s for s in managed.policy(CLIENT) if s["suffix"] == "wan-guard")
    line = managed.add_command(guard, "*A").replace(" place-before=*A", "")
    with pytest.raises(ValueError):
        managed.exact_object(line.replace('action="drop"', 'action="accept"'), guard, dict(guard["values"], disabled=True))
    for spec in managed.policy(CLIENT):
        row = dict(spec["values"], disabled=spec["control"])
        for key in ("distance", "dst-port", "to-ports"):
            if key in row: row[key] = float(row[key])
        line = managed.add_command(spec, "*A" if spec["anchor"] else None).replace(" place-before=*A", "")
        managed.exact_object(line, spec, row)


def test_resume_before_hash_pinning_rejects_moved_flow(tmp_path):
    c, routers = full_instance(tmp_path)
    prepare = c.prepare
    def crash(client, snapshots):
        prepare(client, snapshots)
        raise KeyboardInterrupt()
    c.prepare = crash
    with pytest.raises(KeyboardInterrupt): c.action("add", CLIENT["mac"], c.inspect()[0]["revision"])
    rows = routers["fethiye"].data["/ip firewall filter"]
    target = next(r for r in rows if r.get("comment") == managed.owner(CLIENT) + ":flow-0")
    rows.remove(target); rows.append(target)
    fresh = Controller(c.config, c.path, routers=routers, clock=lambda: 100)
    result = fresh.action("add", CLIENT["mac"], fresh.inspect()[0]["revision"])
    assert not result["success"]
    assert not any(" enable " in cmd for router in routers.values() for cmd in router.commands)
    assert not fresh.state["clients"][CLIENT["mac"]].get("hashes")


def test_cancel_before_make_static_does_not_pin_or_flush_reassigned_ip(tmp_path):
    c, routers = full_instance(tmp_path)
    router = routers["fethiye"]
    run = router.run
    def crash(command):
        if "/ip dhcp-server lease make-static " in command: raise KeyboardInterrupt()
        return run(command)
    router.run = crash
    with pytest.raises(KeyboardInterrupt): c.action("add", CLIENT["mac"], c.inspect()[0]["revision"])
    target = next(r for r in router.data["leases"] if r["mac-address"] == CLIENT["mac"])
    target["address"] = "192.168.89.151"
    router.run = run
    fresh = Controller(c.config, c.path, routers=routers, clock=lambda: 100)
    status = fresh.inspect()[0]
    assert status["can_remove"]
    assert fresh.action("remove", CLIENT["mac"], status["revision"])["success"]
    assert CLIENT["mac"] not in fresh.state["clients"]
    assert router.commands == []
    result = fresh.action("add", CLIENT["mac"], fresh.inspect()[0]["revision"])
    assert result["success"], result
    assert fresh.state["clients"][CLIENT["mac"]]["ip"] == "192.168.89.151"


def test_existing_static_reservation_is_preserved(tmp_path):
    routers = {s: FullRouter(s) for s in managed.SITES}
    routers["fethiye"].static = True
    legacy = dict(ip=egress.CLIENT, mac=egress.MAC)
    config = dict(dhcp_server="defconf", baseline={s: managed.outside_hash(r.render()) for s,r in routers.items()},
                  legacy_hashes={s: managed.owned_hash(r.render(), legacy) for s,r in routers.items()})
    path = tmp_path / "state.json"; write(path, dict(version=1, generation=0, clients={}))
    c = Controller(config, path, routers=routers, clock=lambda: 100)
    result = c.action("add", CLIENT["mac"], c.inspect()[0]["revision"])
    assert result["success"], result
    assert not c.state["clients"][CLIENT["mac"]]["binding"]["converted"]
    assert not any("make-static" in command for command in routers["fethiye"].commands)


@pytest.mark.parametrize("moved_suffix", ["flow-0", "client-route"])
def test_rows_export_order_race_is_refused_before_pinning(tmp_path, moved_suffix):
    c, routers = full_instance(tmp_path)
    router = routers["fethiye"]
    snapshot = router.snapshot
    def raced_snapshot():
        result = snapshot()
        lines = result["export"].splitlines()
        target = next((line for line in lines if managed.line_comment(line) == managed.owner(CLIENT) + ":" + moved_suffix), None)
        if target:
            lines.remove(target)
            if moved_suffix == "flow-0": lines.append(target)
            else: lines.insert(0, target)
            result["export"] = "\n".join(lines)
        return result
    router.snapshot = raced_snapshot
    result = c.action("add", CLIENT["mac"], c.inspect()[0]["revision"])
    assert not result["success"]
    assert not c.state["clients"][CLIENT["mac"]].get("hashes")
    assert not any(" enable " in command for r in routers.values() for command in r.commands)
