#!/usr/bin/env python3
"""Download and verify the deployment checkpoint, using the shared Mac venv."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

from admin_stage import EVIDENCE, ROOT, SSH

record = json.loads((EVIDENCE / "final-checkpoint.json").read_text())
assert record["returncode"] == 0
lines = record["stdout"].splitlines()
remote = next(line.removeprefix("CHECKPOINT=") for line in lines if line.startswith("CHECKPOINT="))
assert remote.startswith("/root/uplink-guards-stage-20260911/checkpoint-")
assert all(c.isalnum() or c in "/-_." for c in remote)
expected = next(line.split()[0] for line in lines if line.endswith("  " + remote))
destination = EVIDENCE / Path(remote).name
if not destination.exists():
    with destination.open("xb") as stream:
        subprocess.run(SSH + [f"cat {remote}"], stdout=stream, check=True, timeout=30)
actual = hashlib.file_digest(destination.open("rb"), "sha256").hexdigest()
assert actual == expected, "checkpoint archive checksum mismatch"
with tarfile.open(destination) as archive:
    checks = archive.extractfile("SHA256SUMS").read().decode().splitlines()
    for line in checks:
        digest, name = line.split("  ", 1)
        payload = archive.extractfile(name).read()
        assert hashlib.sha256(payload).hexdigest() == digest, name
        if name in {"guardctl.sh", "guard-manifest.json", "probe-targets.json"}:
            assert payload == (ROOT / name).read_bytes(), f"local/deployed mismatch: {name}"
print(f"CHECKPOINT_VERIFIED {destination}\nSHA256={actual}\nFILES_VERIFIED={len(checks)}")
