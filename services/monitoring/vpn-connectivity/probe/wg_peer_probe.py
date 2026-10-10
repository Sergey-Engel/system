"""Read-only server-side VPN telemetry grouped by device.

WireGuard and AWG31 activity comes from their server-side handshakes and
counters. TimeWeb Xray/REALITY activity comes from signed client access events
already written to journald. No client agent, credential, or Xray config read
is required. Xray access events have no per-client byte counters.
"""

from pathlib import Path
import sys

import json
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ACTIVE_HANDSHAKE_SECONDS = 180
XRAY_RECENT_ACCESS_SECONDS = 90
OBSERVATION_FRESH_SECONDS = 45
POLL_SECONDS = 15
XRAY_JOURNAL_LOOKBACK_SECONDS = 720

INVENTORY_PATH = Path(__file__).resolve().parents[4] / "config/inventory/observations.json"

SOURCES = {
    "timeweb-wg": {
        "label": "TimeWeb WireGuard",
        "container": "wg-relay",
        "tool": "wg",
        "ssh": [
            "ssh",
            "-i",
            str(Path(__file__).resolve().parents[4] / '.local/ssh/codex_timeweb_audit_20260628'),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "ServerAliveInterval=3",
            "-o",
            "ServerAliveCountMax=1",
            "root@94.241.171.65",
            "/opt/vpn-monitoring/pilot/.venv/bin/python -B -",
        ],
    },
    "fornex-awg31": {
        "label": "Fornex AWG 3.1",
        "container": "fornex-awg31",
        "tool": "awg",
        "ssh": [
            "ssh",
            "-i",
            str(Path(__file__).resolve().parents[4] / '.local/ssh/codex_fornex_audit_20260628'),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "ServerAliveInterval=3",
            "-o",
            "ServerAliveCountMax=1",
            "root@103.75.126.143",
            "python3 -",
        ],
    },
    "timeweb-xray": {
        "label": "TimeWeb Xray/REALITY",
        "ssh": [
            "ssh",
            "-i",
            str(Path(__file__).resolve().parents[4] / '.local/ssh/codex_timeweb_audit_20260628'),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "ServerAliveInterval=3",
            "-o",
            "ServerAliveCountMax=1",
            "root@94.241.171.65",
            "python3 -",
        ],
    },
}
SOURCE_CODES = {"timeweb-wg": 1, "fornex-awg31": 2, "timeweb-xray": 3}
FLEX_CLIENT_IDS = {"macbook": "macbook-socks-tw-flex",
                   "iphone": "iphone-socks-tw-flex",
                   "macmini": "macmini-socks-tw-flex"}
FLEX_STATUS_SSH = [
    *SOURCES["timeweb-xray"]["ssh"][:-1],
    "/usr/local/sbin/timeweb-flex-fleet status",
]


def flex_route_code(base_code, route):
    return base_code * 10 + (1 if route["exit"] == "fx" else 3) + int(route["ru_direct"])


def flex_route_label(route):
    exit_name = route["exit"].upper()
    ru_exit = "TW" if route["ru_direct"] else exit_name
    return f"SOCKS-TW-FLEX · {exit_name} · RU {ru_exit}"


def load_inventory(path=INVENTORY_PATH):
    """Load the device peer inventory shared with Grafana."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    devices = []
    peers = []
    xray_clients = []
    seen_devices = set()
    seen_observations = set()
    seen_addresses = set()

    for device in raw["devices"]:
        device_id = device["id"]
        if device_id in seen_devices:
            raise ValueError(f"duplicate device id: {device_id}")
        seen_devices.add(device_id)
        devices.append(device_id)

        tunnel_codes = set()
        for entry in device["peers"]:
            peer = {
                **entry,
                "source": entry.get("source", "timeweb-wg"),
                "device": device_id,
                "device_name": device["name"],
            }
            if peer["source"] not in SOURCES:
                raise ValueError(f"unknown telemetry source: {peer['source']}")
            if peer["id"] in seen_observations:
                raise ValueError(f"duplicate observation id: {peer['id']}")
            if peer["address"] in seen_addresses:
                raise ValueError(f"duplicate peer address: {peer['address']}")
            if peer["tunnel_code"] in tunnel_codes:
                raise ValueError(f"duplicate tunnel code for {device_id}: {peer['tunnel_code']}")
            seen_observations.add(peer["id"])
            seen_addresses.add(peer["address"])
            tunnel_codes.add(peer["tunnel_code"])
            peers.append(peer)

        for entry in device.get("xray_clients", []):
            client = {
                **entry,
                "source": entry.get("source", "timeweb-xray"),
                "device": device_id,
                "device_name": device["name"],
            }
            if client["source"] not in SOURCES:
                raise ValueError(f"unknown telemetry source: {client['source']}")
            if client["source"] != "timeweb-xray" or not client.get("email"):
                raise ValueError(f"invalid Xray client observation: {client['id']}")
            if client["id"] in seen_observations:
                raise ValueError(f"duplicate observation id: {client['id']}")
            if client["tunnel_code"] in tunnel_codes:
                raise ValueError(f"duplicate tunnel code for {device_id}: {client['tunnel_code']}")
            seen_observations.add(client["id"])
            tunnel_codes.add(client["tunnel_code"])
            xray_clients.append(client)

    if not peers and not xray_clients:
        raise ValueError("VPN inventory contains no observations")
    return tuple(peers), tuple(xray_clients), tuple(devices)


PEERS, XRAY_CLIENTS, DEVICES = load_inventory()
PEERS_BY_SOURCE = {
    source: tuple(peer for peer in PEERS if peer["source"] == source)
    for source in SOURCES
}
XRAY_CLIENTS_BY_SOURCE = {
    source: tuple(client for client in XRAY_CLIENTS if client["source"] == source)
    for source in SOURCES
}

REMOTE_TEMPLATE = r'''
import json,subprocess,time

def run(*args): return subprocess.check_output(args,text=True,timeout=2).strip()
def identity():
 return run('cat','/proc/sys/kernel/random/boot_id')+run('docker','inspect','--format','{{.Id}} {{.State.StartedAt}}',__CONTAINER__)
def wg(interface,field):
 return dict(line.split(None,1) for line in run('docker','exec',__CONTAINER__,__TOOL__,'show',interface,field).splitlines())

peers=json.loads(__PEERS_JSON__)
before=identity()
snapshot={}
for interface in sorted({peer['interface'] for peer in peers}):
 snapshot[interface]={field:wg(interface,field) for field in ('allowed-ips','transfer','latest-handshakes')}
assert identity()==before
now=time.time()
result={}
for peer in peers:
 data=snapshot[peer['interface']]
 key=next((key for key,ips in data['allowed-ips'].items() if peer['address'] in ips.split()),None)
 if key is None:
  result[peer['id']]=dict(identity=before,present=False,server_time=now)
  continue
 transfer=list(map(int,data['transfer'][key].split()))
 result[peer['id']]=dict(identity=before,present=True,rx=transfer[0],tx=transfer[1],handshake=int(data['latest-handshakes'][key]),server_time=now)
print(json.dumps(result))
'''

def remote_script(source, peers):
    inventory = [
        {key: peer[key] for key in ("id", "interface", "address")}
        for peer in peers
    ]
    config = SOURCES[source]
    return (
        REMOTE_TEMPLATE.replace("__PEERS_JSON__", repr(json.dumps(inventory)))
        .replace("__CONTAINER__", repr(config["container"]))
        .replace("__TOOL__", repr(config["tool"]))
    )


XRAY_REMOTE_TEMPLATE = r'''
import json,subprocess,time

clients=json.loads(__CLIENTS_JSON__)
now=time.time()
result={client['id']:dict(present=True,activity=0,server_time=now) for client in clients}
command=['journalctl','-u','xray-timeweb-reality.service','--since','@'+str(now-__LOOKBACK__),'-o','json','--no-pager']
for raw in subprocess.check_output(command,text=True,timeout=8).splitlines():
 try:
  record=json.loads(raw)
  message=record.get('MESSAGE','')
  stamp=float(record.get('__REALTIME_TIMESTAMP',0))/1000000
 except (ValueError,TypeError,json.JSONDecodeError):
  continue
 for client in clients:
  if 'email: '+client['email'] in message:
   result[client['id']]['activity']=max(result[client['id']]['activity'],stamp)
print(json.dumps(result))
'''


def remote_xray_script(clients):
    inventory = [{key: client[key] for key in ("id", "email")} for client in clients]
    return (
        XRAY_REMOTE_TEMPLATE.replace("__CLIENTS_JSON__", repr(json.dumps(inventory)))
        .replace("__LOOKBACK__", repr(XRAY_JOURNAL_LOOKBACK_SECONDS))
    )


def sample_is_fresh(sample, now):
    return bool(sample and 0 <= now - sample["mono"] <= OBSERVATION_FRESH_SECONDS)


def sample_age(sample, now):
    return sample["server_time"] - sample["handshake"] + now - sample["mono"]


def activity_age(sample, now):
    return sample["server_time"] - sample["activity"] + now - sample["mono"]


def speeds(previous, current):
    if (
        not previous
        or not previous.get("present")
        or previous["identity"] != current["identity"]
    ):
        return None
    dt = current["mono"] - previous["mono"]
    if not 0 < dt <= OBSERVATION_FRESH_SECONDS or abs(
        current["server_time"] - previous["server_time"] - dt
    ) > 5:
        return None
    rx, tx = current["rx"] - previous["rx"], current["tx"] - previous["tx"]
    if rx < 0 or tx < 0 or current["handshake"] < previous["handshake"]:
        return None
    # Server TX is client IN. Counters include WireGuard overhead.
    return tx * 8 / dt, rx * 8 / dt


def labels_for_peer(peer):
    return {
        "device": peer["device"],
        "device_name": peer["device_name"],
        "tunnel": peer["tunnel"],
        "interface": peer["interface"],
        "source": peer["source"],
    }


def labels_for_xray_client(client):
    return {
        "device": client["device"],
        "device_name": client["device_name"],
        "tunnel": client["tunnel"],
        "source": client["source"],
    }


def peer_values(sample, now):
    fresh = sample_is_fresh(sample, now)
    values = {"observation_fresh": int(fresh), "peer_present": 0, "activity": 0}
    if not fresh or not sample["present"]:
        return values

    values.update(
        peer_present=1,
        last_observed_seconds=sample["observed"],
        client_in_bytes_total=sample["tx"],
        client_out_bytes_total=sample["rx"],
    )
    age = max(0, sample_age(sample, now))
    if sample["handshake"]:
        values["last_handshake_seconds"] = sample["handshake"]
        values["handshake_age_seconds"] = age
    values["activity"] = int(bool(sample["handshake"]) and age < ACTIVE_HANDSHAKE_SECONDS) or 2
    if sample.get("rates") is not None:
        values["rate_valid"] = 1
        values["client_in_bps"], values["client_out_bps"] = sample["rates"]
    else:
        values["rate_valid"] = 0
    return values


def xray_client_values(sample, now):
    fresh = sample_is_fresh(sample, now)
    values = {"observation_fresh": int(fresh), "activity": 0}
    if not fresh:
        return values

    if not sample["activity"]:
        values["activity"] = 2
        return values

    age = max(0, activity_age(sample, now))
    values["last_activity_seconds"] = sample["activity"]
    values["activity_age_seconds"] = age
    values["activity"] = 3 if age < XRAY_RECENT_ACCESS_SECONDS else 2
    return values


def device_values(device, samples, xray_samples, now, flex_sample=None):
    device_peers = [peer for peer in PEERS if peer["device"] == device]
    device_xray_clients = [client for client in XRAY_CLIENTS if client["device"] == device]
    observed_sources = {
        peer["source"]
        for peer in device_peers
        if sample_is_fresh(samples.get(peer["id"]), now)
    }
    observed_sources.update(
        client["source"]
        for client in device_xray_clients
        if sample_is_fresh(xray_samples.get(client["id"]), now)
    )
    expected_sources = {peer["source"] for peer in device_peers}
    expected_sources.update(client["source"] for client in device_xray_clients)
    if not observed_sources:
        return {"activity": 0, "active_tunnel_code": -1, "active_source_code": -1}, None

    candidates = []
    for peer in device_peers:
        sample = samples.get(peer["id"])
        if not sample_is_fresh(sample, now) or not sample["present"] or not sample["handshake"]:
            continue
        if sample_age(sample, now) < ACTIVE_HANDSHAKE_SECONDS:
            candidates.append((sample["handshake"], "handshake", peer, sample))
    for client in device_xray_clients:
        sample = xray_samples.get(client["id"])
        if not sample_is_fresh(sample, now) or not sample["activity"]:
            continue
        if activity_age(sample, now) < XRAY_RECENT_ACCESS_SECONDS:
            candidates.append((sample["activity"], "xray_activity", client, sample))
    if not candidates:
        if observed_sources != expected_sources:
            return {"activity": 0, "active_tunnel_code": -1, "active_source_code": -1}, None
        return {"activity": 2, "active_tunnel_code": 0, "active_source_code": 0}, None

    _, observation_kind, tunnel, sample = max(candidates, key=lambda candidate: candidate[0])
    values = {
        "activity": 3 if observation_kind == "xray_activity" else 1,
        "active_tunnel_code": tunnel["tunnel_code"],
        "active_source_code": SOURCE_CODES[tunnel["source"]],
        "active_observation_kind": 1 if observation_kind == "handshake" else 2,
        "active_observation_age_seconds": max(
            0,
            sample_age(sample, now)
            if observation_kind == "handshake"
            else activity_age(sample, now),
        ),
    }
    flex_route = (flex_sample or {}).get(device)
    if tunnel["id"] == FLEX_CLIENT_IDS.get(device) and sample_is_fresh(flex_route, now):
        values["active_tunnel_code"] = flex_route_code(tunnel["tunnel_code"], flex_route)
        tunnel = {**tunnel, "tunnel": flex_route_label(flex_route)}
    if observation_kind == "xray_activity":
        tunnel = {**tunnel, "tunnel": f'{tunnel["tunnel"]} · access <90s'}
    if observation_kind == "handshake" and sample.get("rates") is not None:
        values["active_rate_valid"] = 1
        values["active_client_in_bps"], values["active_client_out_bps"] = sample["rates"]
    else:
        values["active_rate_valid"] = 0
    return values, tunnel


def escaped_label(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def prometheus_metrics(samples, now, source_observed=None, xray_samples=None, flex_sample=None):
    metrics = defaultdict(list)
    source_observed = source_observed or {}
    xray_samples = xray_samples or {}

    def add(name, value, labels, kind="gauge"):
        metrics[(name, kind)].append((labels, value))

    for peer in PEERS:
        for key, value in peer_values(samples.get(peer["id"]), now).items():
            kind = "counter" if key.endswith("_total") else "gauge"
            add(f"vpn_wg_peer_{key}", value, labels_for_peer(peer), kind)

    for client in XRAY_CLIENTS:
        for key, value in xray_client_values(xray_samples.get(client["id"]), now).items():
            add(f"vpn_xray_client_{key}", value, labels_for_xray_client(client))

    for source, config in SOURCES.items():
        observed = source_observed.get(source)
        fresh = int(observed is not None and 0 <= now - observed <= OBSERVATION_FRESH_SECONDS)
        add(
            "vpn_source_observation_fresh",
            fresh,
            {"source": source, "source_name": config["label"]},
        )

    for device in FLEX_CLIENT_IDS:
        route = (flex_sample or {}).get(device)
        flex_fresh = sample_is_fresh(route, now)
        add("vpn_flex_route_observation_fresh", int(flex_fresh), {"device": device})
        if flex_fresh:
            add("vpn_flex_route_exit_code", 1 if route["exit"] == "fx" else 2, {"device": device})
            add("vpn_flex_route_ru_direct", int(route["ru_direct"]), {"device": device})

    for device in DEVICES:
        observed = next(
            observation
            for observation in (*PEERS, *XRAY_CLIENTS)
            if observation["device"] == device
        )
        values, active = device_values(device, samples, xray_samples, now, flex_sample)
        labels = {"device": device, "device_name": observed["device_name"]}
        for key, value in values.items():
            add(f"vpn_device_{key}", value, labels)
        if active is not None:
            add(
                "vpn_device_active_tunnel",
                1,
                {
                    **labels,
                    "tunnel": active["tunnel"],
                    "source": active["source"],
                },
            )

    lines = []
    for (name, kind), series in sorted(metrics.items()):
        lines.append(f"# TYPE {name} {kind}")
        for labels, value in series:
            rendered = ",".join(
                f'{key}="{escaped_label(value)}"' for key, value in sorted(labels.items())
            )
            lines.append(f"{name}{{{rendered}}} {value}")
    return "\n".join(lines) + "\n"


def collect_wg_source(source, peers, previous):
    """Read and validate one WireGuard-family source without config or keys."""
    completed = subprocess.run(
        SOURCES[source]["ssh"],
        input=remote_script(source, peers),
        text=True,
        capture_output=True,
        timeout=13,
        check=True,
    )
    samples = json.loads(completed.stdout)
    if set(samples) != {peer["id"] for peer in peers}:
        raise ValueError(f"incomplete peer inventory from {source}")
    for peer in peers:
        sample = samples[peer["id"]]
        sample.update(mono=time.monotonic(), observed=time.time())
        if sample["present"]:
            sample["rates"] = speeds(previous.get(peer["id"]), sample)
    return samples


def collect_xray_source(source, clients):
    """Read recent signed Xray access events without exporting their payload."""
    completed = subprocess.run(
        SOURCES[source]["ssh"],
        input=remote_xray_script(clients),
        text=True,
        capture_output=True,
        timeout=13,
        check=True,
    )
    samples = json.loads(completed.stdout)
    if set(samples) != {client["id"] for client in clients}:
        raise ValueError(f"incomplete Xray inventory from {source}")
    for sample in samples.values():
        sample.update(mono=time.monotonic(), observed=time.time())
    return samples


def collect_flex_status():
    """Use the controller's read-back, never its desired-state file."""
    completed = subprocess.run(
        FLEX_STATUS_SSH, text=True, capture_output=True, timeout=30, check=True
    )
    status = json.loads(completed.stdout)
    routes = {}
    for controller_device, info in status.get("devices", {}).items():
        device = "iphone" if controller_device == "iphone12" else controller_device
        if device not in FLEX_CLIENT_IDS:
            continue
        observed = info.get("observed", {})
        if (info.get("route") != "ready" or observed.get("observed") != "ready"
                or observed.get("exit") not in ("fx", "cen")
                or type(observed.get("ru_direct")) is not bool):
            continue
        routes[device] = {**observed, "mono": time.monotonic()}
    if set(routes) != set(FLEX_CLIENT_IDS):
        raise ValueError("invalid FLEX fleet status")
    return routes


def main():
    shared = {"samples": {}, "xray_samples": {}, "source_observed": {}, "flex_sample": None}
    lock = threading.Lock()

    def poll():
        previous_by_source = {source: {} for source in SOURCES}
        latest_by_source = {}
        latest_xray_by_source = {}
        latest_flex = None
        source_observed = {}
        with ThreadPoolExecutor(max_workers=len(SOURCES) + 1) as executor:
            while True:
                start = time.monotonic()
                futures = {}
                for source, peers in PEERS_BY_SOURCE.items():
                    if peers:
                        futures[
                            executor.submit(
                                collect_wg_source,
                                source,
                                peers,
                                previous_by_source[source],
                            )
                        ] = ("wg", source)
                for source, clients in XRAY_CLIENTS_BY_SOURCE.items():
                    if clients:
                        futures[executor.submit(collect_xray_source, source, clients)] = (
                            "xray",
                            source,
                        )
                futures[executor.submit(collect_flex_status)] = ("flex", "timeweb-flex")
                for future in as_completed(futures):
                    kind, source = futures[future]
                    try:
                        samples = future.result()
                    except (subprocess.SubprocessError, ValueError, KeyError, OSError, TypeError):
                        # Keep the last good snapshot until it becomes stale; re-baseline
                        # rates after a failed source instead of calculating across a gap.
                        if kind == "wg":
                            previous_by_source[source] = {}
                        continue
                    if kind == "wg":
                        previous_by_source[source] = samples
                        latest_by_source[source] = samples
                    elif kind == "xray":
                        latest_xray_by_source[source] = samples
                    else:
                        latest_flex = samples
                    if kind != "flex":
                        source_observed[source] = time.monotonic()

                combined = {
                    peer_id: sample
                    for source_samples in latest_by_source.values()
                    for peer_id, sample in source_samples.items()
                }
                combined_xray = {
                    client_id: sample
                    for source_samples in latest_xray_by_source.values()
                    for client_id, sample in source_samples.items()
                }
                with lock:
                    shared["samples"] = combined
                    shared["xray_samples"] = combined_xray
                    shared["source_observed"] = dict(source_observed)
                    shared["flex_sample"] = latest_flex
                time.sleep(max(0.1, POLL_SECONDS - (time.monotonic() - start)))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != "/metrics":
                self.send_error(404)
                return
            with lock:
                payload = prometheus_metrics(
                    shared["samples"],
                    time.monotonic(),
                    shared["source_observed"],
                    shared["xray_samples"],
                    shared["flex_sample"],
                ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = HTTPServer(("127.0.0.1", 19108), Handler)
    server.timeout = 2
    threading.Thread(target=poll, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
