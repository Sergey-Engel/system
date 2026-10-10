#!/usr/bin/env python3
"""Local connectivity probe for the active macOS route.

The process exposes Prometheus metrics on localhost. It never reads VPN
configuration files or private keys; the active tunnel is inferred from the
route table and utun interfaces.
"""

from __future__ import annotations

import http.server
import os
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(os.environ.get("PROBE_PORT", "9105"))
SITE_PROFILE = os.environ.get("SITE_PROFILE", "nakhimova_domru")
EGRESS_PROFILE = os.environ.get("EGRESS_PROFILE", "fornex_amnezia")
VPN_PUBLIC_IP_MAP = {
    item.split("=", 1)[0].strip(): item.split("=", 1)[1].strip()
    for item in os.environ.get(
        "VPN_PUBLIC_IP_MAP",
        "103.75.126.143=Fornex Amnezia,89.252.153.129=Cenuta,94.241.171.65=TimeWeb,89.105.208.242=Amnezia Premium VLES",
    ).split(",")
    if "=" in item
}


@dataclass
class CheckResult:
    name: str
    up: int
    latency_seconds: float


def run(command: list[str], timeout: float = 3.0) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), time.monotonic() - started
    except (OSError, subprocess.TimeoutExpired):
        return 1, "", time.monotonic() - started


def route_state() -> tuple[str, str, str]:
    code, output, _ = run(["route", "-n", "get", "default"])
    if code != 0:
        return "", "", ""
    gateway = re.search(r"^\s*gateway:\s+(\S+)", output, re.MULTILINE)
    interface = re.search(r"^\s*interface:\s+(\S+)", output, re.MULTILINE)
    lan_ip = ""
    if interface:
        ip_code, ip_output, _ = run(["ipconfig", "getifaddr", interface.group(1)])
        if ip_code == 0:
            lan_ip = ip_output
    return (
        gateway.group(1) if gateway else "",
        interface.group(1) if interface else "",
        lan_ip,
    )


def utun_state() -> tuple[str, str, int]:
    code, ifconfig, _ = run(["ifconfig"], timeout=5.0)
    ifconfig_up = 0
    tunnel_interface = ""
    tunnel_ip = ""
    for block in re.split(r"(?m)(?=^utun\d+:)", ifconfig):
        header = re.match(r"^(utun\d+):([^\n]*)", block)
        if not header or "UP" not in header.group(2):
            continue
        ifconfig_up = 1
        tunnel_interface = header.group(1)
        address = re.search(r"^\s+inet\s+(\S+)", block, re.MULTILINE)
        tunnel_ip = address.group(1) if address else ""
    return tunnel_interface, tunnel_ip, ifconfig_up


def check_gateway(gateway: str) -> CheckResult:
    if not gateway:
        return CheckResult("gateway", 0, 0.0)
    code, _, elapsed = run(["ping", "-c", "1", "-W", "1000", gateway], timeout=3.0)
    return CheckResult("gateway", int(code == 0), elapsed)


def check_external_icmp() -> CheckResult:
    code, _, elapsed = run(["ping", "-c", "1", "-W", "1000", "1.1.1.1"], timeout=3.0)
    return CheckResult("external_icmp", int(code == 0), elapsed)


def check_dns() -> CheckResult:
    started = time.monotonic()
    try:
        socket.setdefaulttimeout(3.0)
        socket.getaddrinfo("api.ipify.org", 443, type=socket.SOCK_STREAM)
        return CheckResult("dns", 1, time.monotonic() - started)
    except (OSError, socket.timeout):
        return CheckResult("dns", 0, time.monotonic() - started)


def check_https() -> CheckResult:
    started = time.monotonic()
    code, _, elapsed = run(
        ["curl", "-4", "--silent", "--show-error", "--max-time", "5", "-o", "/dev/null", "https://api.ipify.org"],
        timeout=6.0,
    )
    return CheckResult("https", int(code == 0), elapsed)


def public_ipv4() -> str:
    code, output, _ = run(
        [
            "curl",
            "-4",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            "https://api.ipify.org",
        ],
        timeout=6.0,
    )
    return output if code == 0 and re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", output) else ""


def vpn_name(ipv4: str) -> str:
    return VPN_PUBLIC_IP_MAP.get(ipv4, "Unknown VPN" if ipv4 else "No public IP")


def check_https_upload() -> CheckResult:
    started = time.monotonic()
    code, _, elapsed = run(
        [
            "curl",
            "-4",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            "-X",
            "POST",
            "--data-binary",
            "vpn_probe=1",
            "-o",
            "/dev/null",
            "https://httpbin.org/post",
        ],
        timeout=6.0,
    )
    return CheckResult("https_upload", int(code == 0), time.monotonic() - started)


def metric_line(name: str, labels: dict[str, str], value: object) -> str:
    encoded = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
    return f"{name}{{{encoded}}} {value}"


def metrics() -> str:
    gateway, lan_interface, lan_ip = route_state()
    tunnel_interface, tunnel_ip, utun_up = utun_state()
    check_functions = [
        lambda: check_gateway(gateway),
        check_external_icmp,
        check_dns,
        check_https,
        check_https_upload,
    ]
    with ThreadPoolExecutor(max_workers=len(check_functions)) as executor:
        checks = [future.result() for future in [executor.submit(function) for function in check_functions]]
    checks_by_name = {check.name: check for check in checks}
    internet_up = int(checks_by_name.get("https", CheckResult("https", 0, 0.0)).up == 1)
    common = {
        "site_profile": SITE_PROFILE,
        "egress_profile": EGRESS_PROFILE,
    }
    current_public_ip = public_ipv4()
    current_vpn_name = vpn_name(current_public_ip)
    lines = [
        "# HELP vpn_probe_up Whether a connectivity check succeeded.",
        "# TYPE vpn_probe_up gauge",
    ]
    for check in checks:
        lines.append(metric_line("vpn_probe_up", {**common, "check": check.name}, check.up))
        lines.append(
            metric_line(
                "vpn_probe_latency_seconds",
                {**common, "check": check.name},
                f"{check.latency_seconds:.6f}",
            )
        )
    lines.extend(
        [
            "# HELP vpn_probe_route_info Current route metadata.",
            "# TYPE vpn_probe_route_info gauge",
            metric_line(
                "vpn_probe_route_info",
                {
                    **common,
                    "gateway": gateway or "unknown",
                    "lan_interface": lan_interface or "unknown",
                    "lan_ip": lan_ip or "unknown",
                    "tunnel_interface": tunnel_interface or "none",
                    "tunnel_ip": tunnel_ip or "none",
                    "vpn_name": current_vpn_name,
                    "public_ip": current_public_ip or "unknown",
                },
                1,
            ),
            "# HELP vpn_probe_tunnel_up Whether an active utun interface was detected.",
            "# TYPE vpn_probe_tunnel_up gauge",
            metric_line("vpn_probe_tunnel_up", common, utun_up),
            "# HELP vpn_probe_internet_up Whether the primary HTTPS internet check succeeded.",
            "# TYPE vpn_probe_internet_up gauge",
            metric_line("vpn_probe_internet_up", common, internet_up),
        ]
    )
    return "\n".join(lines) + "\n"


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        if self.path != "/metrics":
            self.send_error(404)
            return
        payload = metrics().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        return


def main() -> None:
    server = http.server.ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), MetricsHandler)
    print(f"host probe listening on http://{LISTEN_HOST}:{LISTEN_PORT}/metrics", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
