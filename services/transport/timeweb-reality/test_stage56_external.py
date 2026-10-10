"""Bounded external REALITY tests; local SOCKS only, no OS route changes."""
import json
import os
import socket
import subprocess
import time
from stage56 import ROOT, DEST

os.umask(0o077)
config = json.loads((ROOT / "staging/fornex/client-macbook.json").read_text())
config["inbounds"][0]["port"] = 10844
config["outbounds"][1]["streamSettings"]["realitySettings"]["serverName"] = "www.apple.com"
config["outbounds"] = [config["outbounds"][1]]
path = DEST / "external-client.json"
path.write_text(json.dumps(config, indent=2) + "\n")
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 10844))
report = {}
with (DEST / "external-client.log").open("w") as log:
    process = subprocess.Popen([str(ROOT / "vendor/macos-arm64/xray"), "run", "-config", str(path)], stdout=log, stderr=log)
    try:
        time.sleep(2)
        assert process.poll() is None, "Test client did not start"
        for name, url in (
            ("exit_ip", "https://api.ipify.org"),
            ("independent_https", "https://example.com/"),
            ("download_1MiB", "https://speed.cloudflare.com/__down?bytes=1048576"),
            ("private_denied", "http://10.20.0.2/"),
        ):
            started = time.monotonic()
            result = subprocess.run(["curl", "-fsS", "--max-time", "20" if name != "private_denied" else "4",
                                     "--proxy", "socks5h://127.0.0.1:10844", url], capture_output=True, timeout=25)
            item = {"exit": result.returncode, "bytes": len(result.stdout), "seconds": round(time.monotonic()-started, 3),
                    "error": result.stderr.decode()}
            if name == "exit_ip":
                item["ip"] = result.stdout.decode().strip()
                item["passed"] = item["ip"] == "103.75.126.143" and result.returncode == 0
            elif name == "private_denied":
                item["passed"] = result.returncode != 0
            else:
                item["passed"] = result.returncode == 0 and len(result.stdout) >= (1048576 if name == "download_1MiB" else 100)
            report[name] = item
            print(name + ": " + json.dumps(item), flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        (DEST / "external-tests.json").write_text(json.dumps(report, indent=2) + "\n")
assert len(report) == 4 and all(r["passed"] for r in report.values())
