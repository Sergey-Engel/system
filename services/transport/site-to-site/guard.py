"""Check an immutable reviewed pilot bundle and its own nft table only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = Path("/etc/wireguard/s2s-pilot")


def normalized(value):
    if isinstance(value, list):
        return [normalized(x) for x in value if not (isinstance(x, dict) and "metainfo" in x)]
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k not in {"handle", "packets", "bytes"}}
    return value


def main(mode):
    if mode not in {"load", "check"}:
        raise ValueError("unsupported operation")
    manifest = json.loads((BASE / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        path = Path(name)
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError("unsafe pilot file metadata")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("pilot file drift")
    result = subprocess.run(["nft", "-j", "list", "table", "inet", "s2s_pilot"], capture_output=True)
    if result.returncode:
        if mode != "load":
            raise ValueError("pilot guard absent")
        subprocess.run(["nft", "-c", "-f", str(BASE / "guard.nft")], check=True, capture_output=True)
        subprocess.run(["nft", "-f", str(BASE / "guard.nft")], check=True, capture_output=True)
        result = subprocess.run(["nft", "-j", "list", "table", "inet", "s2s_pilot"], check=True, capture_output=True)
    actual = normalized(json.loads(result.stdout))
    if actual != manifest["nft_expected"]:
        raise ValueError("pilot guard drift; refusing repair")
    print("S2S_GUARD_VERIFIED")


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception:
        print("S2S_GUARD_FAILED: inspect private evidence", file=sys.stderr)
        sys.exit(1)
