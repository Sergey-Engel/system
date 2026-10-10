"""Verify that a valid REALITY transport with an unknown VLESS UUID is refused."""
import json
import os
import subprocess
import time
import uuid
from stage56 import DEST, ROOT

os.umask(0o077)
c = json.loads((DEST / "external-client.json").read_text())
c["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] = str(uuid.uuid4())
path = DEST / "unknown-uuid-client.json"
path.write_text(json.dumps(c) + "\n")
with (DEST / "unknown-uuid.log").open("w") as log:
    proc = subprocess.Popen([str(ROOT / "vendor/macos-arm64/xray"), "run", "-config", str(path)], stdout=log, stderr=log)
    try:
        time.sleep(2)
        assert proc.poll() is None
        result = subprocess.run(["curl", "-fsS", "--max-time", "6", "--proxy", "socks5h://127.0.0.1:10844", "https://api.ipify.org"], capture_output=True, timeout=10)
        report = {"unknown_uuid_refused": result.returncode != 0 and not result.stdout,
                  "curl_exit": result.returncode, "bytes": len(result.stdout)}
        (DEST / "auth-test.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        assert report["unknown_uuid_refused"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
