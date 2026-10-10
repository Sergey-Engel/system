#!/usr/bin/env python3
"""Prepare the additive MacBook FLEX identity and peer in a private staging directory."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


PEER_IP = "10.50.50.39"
IDENTITY = "macbook-socks-flex"
TAG = "wg-flex-macbook"
CONFIG = Path("/opt/timeweb-reality/config.json")
WG_CONFIG = Path("/opt/wg/config/wg_confs/wg-clients.conf")
STAGE = Path("/root/timeweb-flex-macbook-stage")
TEMPLATE = STAGE / "template.json"


def run(*args, input_text=None):
    result = subprocess.run(args, input=input_text, text=True, capture_output=True,
                            timeout=20, check=True)
    return result.stdout.strip()


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    if not STAGE.is_dir() or STAGE.stat().st_mode & 0o077:
        raise RuntimeError("Private staging directory is required")
    if any((STAGE / name).exists() for name in ("config.candidate.json", "wg-clients.candidate.conf", "client.json")):
        raise RuntimeError("Pilot already staged")
    config = json.loads(CONFIG.read_text())
    profile = json.loads(TEMPLATE.read_text())
    identities = [inbound for inbound in config["inbounds"] if inbound.get("tag") == "reality-in"]
    if len(identities) != 1:
        raise RuntimeError("Unexpected REALITY inbound")
    clients = identities[0]["settings"]["clients"]
    if any(client.get("email") == IDENTITY for client in clients):
        raise RuntimeError("Identity already exists")
    if any(outbound.get("tag") == TAG for outbound in config["outbounds"]):
        raise RuntimeError("Outbound already exists")
    wg_text = WG_CONFIG.read_text()
    if PEER_IP in wg_text or IDENTITY in wg_text:
        raise RuntimeError("Peer address already allocated")
    if len(profile.get("outbounds", [])) != 1 or profile["outbounds"][0].get("protocol") != "vless":
        raise RuntimeError("Not a single-outbound VLESS template")

    private_key = run("wg", "genkey")
    public_key = run("wg", "pubkey", input_text=private_key + "\n")
    server_public = run("docker", "exec", "wg-relay", "wg", "show", "wg-clients", "public-key")
    identity_id = str(uuid.uuid4())
    clients.append({"id": identity_id, "flow": "xtls-rprx-vision", "email": IDENTITY})
    bth = [outbound for outbound in config["outbounds"] if outbound.get("tag") == "wg-bth"]
    if len(bth) != 1:
        raise RuntimeError("Unexpected WG outbound template")
    outbound = copy.deepcopy(bth[0])
    outbound["tag"] = TAG
    outbound["settings"]["secretKey"] = private_key
    outbound["settings"]["address"] = [f"{PEER_IP}/32"]
    outbound["settings"]["peers"][0]["publicKey"] = server_public
    outbound["settings"]["peers"][0].pop("preSharedKey", None)
    outbound["settings"]["peers"][0]["endpoint"] = "172.19.0.2:51850"
    config["outbounds"].insert(-1, outbound)
    config["routing"]["rules"].insert(-1, {"type": "field", "user": [IDENTITY], "outboundTag": TAG})

    profile["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] = identity_id
    routes = profile["routing"]["rules"]
    if len(routes) != 1 or routes[0].get("outboundTag") != profile["outbounds"][0]["tag"]:
        raise RuntimeError("Client route does not match the template outbound")
    profile["outbounds"][0]["tag"] = "timeweb-flex"
    routes[0]["outboundTag"] = "timeweb-flex"
    interface, remainder = wg_text.split("[Peer]", 1)
    if "[Interface]" not in interface:
        raise RuntimeError("WG server format changed")
    quarantine = (f"PreUp = iptables -I FORWARD -i %i -s {PEER_IP}/32 -j DROP\n"
                  f"PostDown = iptables -D FORWARD -i %i -s {PEER_IP}/32 -j DROP || true\n")
    wg_text = interface + quarantine + "[Peer]" + remainder
    wg_text += f"\n[Peer]\n# {IDENTITY}\nPublicKey = {public_key}\nAllowedIPs = {PEER_IP}/32\n"

    write_private(STAGE / "config.candidate.json", json.dumps(config, indent=2) + "\n")
    write_private(STAGE / "wg-clients.candidate.conf", wg_text)
    write_private(STAGE / "client.json", json.dumps(profile, indent=2) + "\n")
    write_private(STAGE / "peer.public", public_key + "\n")
    run("/opt/timeweb-reality/xray", "run", "-test", "-config", str(STAGE / "config.candidate.json"))
    print("FLEX candidate prepared; Xray config test passed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"FLEX staging failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
