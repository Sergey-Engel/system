#!/usr/bin/env python3
"""Shared FLEX defaults with independent per-device exceptions."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


CONTROLLER = "/usr/local/sbin/timeweb-flex-macbook"
STATE = Path("/var/lib/vpn-uplink-pilot/flex-fleet.json")
LOCK = Path("/run/lock/timeweb-flex-fleet.lock")
DEVICES = {"macbook": ("MacBook Sergey", "macbook-socks-flex", "10.50.50.39/32"),
           "iphone12": ("iPhone 12 Sergey", "iphone12-socks-flex", "10.50.50.40/32"),
           "macmini": ("Mac Mini Sergey", "macmini-socks-flex", "10.50.50.41/32")}
FIELDS = {"exit": ("fx", "cen"), "ru_direct": ("off", "on")}


def command(device, *args):
    result = subprocess.run([CONTROLLER, "--device", device, *args],
                            capture_output=True, text=True, timeout=40, check=False)
    if result.returncode:
        raise RuntimeError(f"{device}: controller failed ({result.stderr.strip()[:200]})")
    value = json.loads(result.stdout)
    if value.get("observed") != "ready":
        raise RuntimeError(f"{device}: route not ready")
    return value


def initial_state():
    macbook = command("macbook", "status")
    return {"default": {"exit": macbook["exit"],
                        "ru_direct": "on" if macbook["ru_direct"] else "off"},
            "overrides": {device: {"exit": None, "ru_direct": None} for device in DEVICES}}


def read_state():
    value = json.loads(STATE.read_text()) if STATE.exists() else initial_state()
    if set(value) != {"default", "overrides"} or not set(value["overrides"]) <= set(DEVICES):
        raise ValueError("Invalid FLEX fleet state")
    for device in DEVICES:
        value["overrides"].setdefault(device, {"exit": None, "ru_direct": None})
    for field, allowed in FIELDS.items():
        if value["default"].get(field) not in allowed:
            raise ValueError("Invalid FLEX default")
        if any(value["overrides"][device].get(field) not in (*allowed, None)
               for device in DEVICES):
            raise ValueError("Invalid FLEX override")
    return value


def save_state(value):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=".flex-fleet-", dir=STATE.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, 0o600)
        os.replace(path, STATE)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def effective(state, device):
    return {field: state["overrides"][device][field] or state["default"][field]
            for field in FIELDS}


def activity():
    now = time.time()
    events = {device: 0 for device in DEVICES}
    result = subprocess.run(["journalctl", "-u", "xray-timeweb-reality.service",
                             "--since", f"@{int(now - 720)}", "-o", "json", "--no-pager"],
                            capture_output=True, text=True, timeout=10, check=False)
    if result.returncode:
        return {device: {"state": "unknown", "age_seconds": None} for device in DEVICES}
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
            stamp = int(record.get("__REALTIME_TIMESTAMP", 0)) / 1000000
            message = record.get("MESSAGE", "")
        except (ValueError, TypeError):
            continue
        for device, (_, identity, _) in DEVICES.items():
            if "email: " + identity in message:
                events[device] = max(events[device], stamp)
    return {device: {"state": "active" if stamp and now - stamp < 90 else "inactive",
                     "age_seconds": round(now - stamp) if stamp else None}
            for device, stamp in events.items()}


def status(state):
    with ThreadPoolExecutor(max_workers=3) as executor:
        activity_future = executor.submit(activity)
        route_futures = {device: executor.submit(command, device, "status") for device in DEVICES}
        seen = activity_future.result()
        observed_routes = {}
        for device, future in route_futures.items():
            try:
                observed_routes[device] = future.result()
            except (RuntimeError, ValueError, subprocess.TimeoutExpired):
                observed_routes[device] = {"exit": None, "ru_direct": None, "observed": "unavailable"}
    devices = {}
    for device, (label, _, peer) in DEVICES.items():
        observed = observed_routes[device]
        desired = effective(state, device)
        route_ready = (observed["observed"] == "ready" and
                       observed["exit"] == desired["exit"] and
                       observed["ru_direct"] == (desired["ru_direct"] == "on"))
        devices[device] = {"label": label, "peer": peer,
                           "overrides": state["overrides"][device],
                           "effective": desired, "observed": observed,
                           "route": "ready" if route_ready else "unavailable",
                           "activity": seen[device]}
    counts = {name: sum(info["activity"]["state"] == name for info in devices.values())
              for name in ("active", "inactive", "unknown")}
    counts["total"] = len(devices)
    counts["route_ready"] = sum(info["route"] == "ready" for info in devices.values())
    return {"default": state["default"], "devices": devices, "counts": counts}


def change(state, scope, field, value):
    if field not in FIELDS or scope not in ("all", *DEVICES):
        raise ValueError("Invalid FLEX setting")
    if value not in (*FIELDS[field], "default") or (scope == "all" and value == "default"):
        raise ValueError("Invalid FLEX value")
    desired = json.loads(json.dumps(state))
    if scope == "all":
        desired["default"][field] = value
    else:
        desired["overrides"][scope][field] = None if value == "default" else value
    changed = []
    try:
        for device in DEVICES:
            before, after = effective(state, device), effective(desired, device)
            if before != after:
                observed = command(device, "switch", after["exit"], after["ru_direct"])
                changed.append(device)
                if observed["exit"] != after["exit"] or observed["ru_direct"] != (after["ru_direct"] == "on"):
                    raise RuntimeError(f"{device}: read-back mismatch")
        observed = status(desired)
        if observed["counts"]["route_ready"] != observed["counts"]["total"]:
            raise RuntimeError("Fleet route read-back failed")
        save_state(desired)
    except Exception:
        for device in reversed(changed):
            previous = effective(state, device)
            try:
                command(device, "switch", previous["exit"], previous["ru_direct"])
            except Exception:
                pass
        raise
    return observed


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    setting = sub.add_parser("set")
    setting.add_argument("scope", choices=("all", *DEVICES))
    setting.add_argument("field", choices=FIELDS)
    setting.add_argument("value")
    args = parser.parse_args()
    if args.action == "status":
        print(json.dumps(status(read_state())))
        return
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(change(read_state(), args.scope, args.field, args.value)))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"FLEX fleet unavailable: {error}", file=sys.stderr)
        sys.exit(1)
