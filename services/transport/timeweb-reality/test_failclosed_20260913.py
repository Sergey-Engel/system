"""One-shot bounded failure test of the new Xray egress; no persistent changes."""

from pathlib import Path
import sys
import json
import os
from pathlib import Path
import socket
import subprocess
import time

os.umask(0o077)
ROOT = Path(__file__).resolve().parent
OUT = ROOT / ("failclosed-" + time.strftime("%Y%m%dT%H%M%S"))
OUT.mkdir(mode=0o700)
TABLE = "reality_failclosed_20260913"
UNIT = "reality-failclosed-20260913"
SSH = ["ssh", "-i", str(Path(__file__).resolve().parents[3] / '.local/ssh/codex_timeweb_audit_20260628'),
       "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
       "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
       "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
       "root@94.241.171.65", "bash -se"]

def remote(script):
    p = subprocess.run(SSH, input=script, text=True, capture_output=True, timeout=25)
    if p.returncode:
        raise RuntimeError(p.stderr + p.stdout)
    return p.stdout

def probe(url):
    start = time.monotonic()
    p = subprocess.run(["curl", "-q", "-4", "-sS", "--noproxy", "", "--connect-timeout", "5",
                        "--max-time", "10", "--proxy", "socks5h://127.0.0.1:10844",
                        url], capture_output=True, timeout=15)
    return {"exit": p.returncode, "bytes": len(p.stdout),
            "seconds": round(time.monotonic()-start, 3),
            "ip": p.stdout.decode().strip() if "ipify" in url else None,
            "error": p.stderr.decode()}

def phase(name):
    result = {url: probe(url) for url in
              ("https://api.ipify.org", "https://example.com/", "https://1.1.1.1/cdn-cgi/trace")}
    report[name] = result
    print(name, json.dumps(result), flush=True)
    return result

report = {}
process = None
armed = False
snapshot = "nft -s list table inet reality_fornex\nsha256sum /opt/timeweb-reality/config.json\nip -4 rule show\nip -4 route show table all\ndocker inspect --format '{{.Name}} {{.State.StartedAt}} {{.State.Running}}' wg-relay\n"
try:
    remote('test "$(id -u reality-fornex)" = 10001\nsystemctl is-active --quiet xray-timeweb-reality\n')
    report["before_guard"] = remote(snapshot)
    remote(f"if nft list table inet {TABLE} >/dev/null 2>&1; then exit 1; fi\nif systemctl is-active --quiet {UNIT}.timer; then exit 1; fi\n")
    config = json.loads((ROOT / "stage56-timeweb/external-client.json").read_text())
    assert config["inbounds"][0]["port"] == 10844
    assert all(o["protocol"] != "freedom" for o in config["outbounds"])
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 10844))
    with (OUT / "client.log").open("w") as log:
        process = subprocess.Popen([str(ROOT / "vendor/macos-arm64/xray"), "run", "-config",
                                    str(ROOT / "stage56-timeweb/external-client.json")], stdout=log, stderr=log)
    time.sleep(2)
    assert process.poll() is None
    baseline = phase("baseline")
    assert all(v["exit"] == 0 and v["bytes"] > 0 for v in baseline.values()), "Baseline failed; no fault applied"
    assert baseline["https://api.ipify.org"]["ip"] == "103.75.126.143"
    baseline2 = phase("baseline_repeat")
    assert all(v["exit"] == 0 and v["bytes"] > 0 for v in baseline2.values()), "Repeated baseline failed"
    assert baseline2["https://api.ipify.org"]["ip"] == "103.75.126.143"
    armed = True
    remote(f"systemd-run --unit={UNIT} --on-active=120s --timer-property=AccuracySec=1s /usr/sbin/nft delete table inet {TABLE}\nsystemctl is-active --quiet {UNIT}.timer\nnft -f - <<'NFT'\nadd table inet {TABLE}\nadd chain inet {TABLE} output {{ type filter hook output priority -10; policy accept; }}\nadd rule inet {TABLE} output meta skuid 10001 ip daddr 103.75.126.143 udp dport 51821 counter drop\nNFT\n")
    print("FAULT ACTIVE: new Xray to Fornex only; auto cleanup <=120s", flush=True)
    fault_started = time.monotonic()
    failed = phase("fault")
    report["fault_counter"] = json.loads(remote(f"nft -j list table inet {TABLE}\n"))
    report["fault_seconds"] = time.monotonic() - fault_started
    remote(f"nft delete table inet {TABLE}\nsystemctl stop {UNIT}.timer\n")
    armed = False
    print("FAULT REMOVED", flush=True)
    time.sleep(3)
    restored = phase("restored")
    restored2 = phase("restored_repeat")
    report["after_guard"] = remote(f"if nft list table inet {TABLE} >/dev/null 2>&1; then exit 1; fi\nif systemctl is-active --quiet {UNIT}.timer; then exit 1; fi\n" + snapshot)
    dropped = sum(expr.get("counter", {}).get("packets", 0)
                  for item in report["fault_counter"]["nftables"]
                  for expr in item.get("rule", {}).get("expr", []))
    report["dropped_packets"] = dropped
    report["passed"] = (dropped > 0 and report["fault_seconds"] < 80
                        and all(v["exit"] == 28 and v["bytes"] == 0 for v in failed.values())
                        and all(v["exit"] == 0 and v["bytes"] > 0 for v in restored.values())
                        and restored["https://api.ipify.org"]["ip"] == "103.75.126.143"
                        and all(v["exit"] == 0 and v["bytes"] > 0 for v in restored2.values())
                        and restored2["https://api.ipify.org"]["ip"] == "103.75.126.143"
                        and report["before_guard"] == report["after_guard"])
finally:
    if armed:
        try:
            remote(f"if nft list table inet {TABLE} >/dev/null 2>&1; then nft delete table inet {TABLE}; fi\nsystemctl stop {UNIT}.timer\n")
            report["emergency_cleanup"] = "confirmed"
        except Exception as exc:
            report["emergency_cleanup"] = str(exc)
            print("Cleanup not confirmed; server auto-cleanup timer remains", flush=True)
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("REPORT", str(OUT / "report.json"), flush=True)
assert report.get("passed"), "Acceptance failed; inspect report"
