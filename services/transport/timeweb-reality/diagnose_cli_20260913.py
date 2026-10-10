"""Read-only network probes through an isolated local Xray client."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time

os.umask(0o077)
root = Path(__file__).resolve().parent
out = root / ("cli-diagnostic-" + time.strftime("%Y%m%dT%H%M%S"))
out.mkdir(mode=0o700)
config = json.loads((root / "stage56-timeweb/external-client.json").read_text())
config["inbounds"][0]["port"] = 10845
(out / "client.json").write_text(json.dumps(config))
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 10845))
with (out / "client.log").open("w") as log:
    proc = subprocess.Popen([str(root / "vendor/macos-arm64/xray"), "run", "-config", str(out / "client.json")], stdout=log, stderr=log)
results = []
try:
    time.sleep(2)
    assert proc.poll() is None
    for url in ("https://api.ipify.org", "https://example.com/", "https://1.1.1.1/cdn-cgi/trace"):
        p = subprocess.run(["curl", "-q", "-4", "-v", "--noproxy", "", "--proxy", "socks5h://127.0.0.1:10845", "--connect-timeout", "15", "--max-time", "20", "-i", url], capture_output=True, text=True, timeout=25)
        results.append({"url":url,"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr})
        print(json.dumps(results[-1]), flush=True)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    (out / "report.json").write_text(json.dumps(results, indent=2))
    print("REPORT", out, flush=True)
