#!/usr/bin/env python3
"""Stage an independent iPhone 12 FLEX identity, WireGuard peer, and client profile."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


PEER_IP = "10.50.50.40"
IDENTITY = "iphone12-socks-flex"
TAG = "wg-flex-iphone12"
CONFIG = Path("/opt/timeweb-reality/config.json")
WG_CONFIG = Path("/opt/wg/config/wg_confs/wg-clients.conf")
STAGE = Path("/root/timeweb-flex-iphone12-stage")
TEMPLATE = STAGE / "template.json"


def run(*args, input_text=None):
    result = subprocess.run(args, input=input_text, text=True, capture_output=True,
                            timeout=20, check=True)
    return result.stdout.strip()


def private_write(path, text):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    if not STAGE.is_dir() or STAGE.stat().st_mode & 0o077:
        raise RuntimeError("Private stage required")
    if any((STAGE / name).exists() for name in
           ("config.candidate.json", "wg-clients.candidate.conf", "client.json")):
        raise RuntimeError("iPhone candidate already staged")
    config = json.loads(CONFIG.read_text())
    profile = json.loads(TEMPLATE.read_text())
    inbound = [item for item in config["inbounds"] if item.get("tag") == "reality-in"]
    if len(inbound) != 1:
        raise RuntimeError("Unexpected REALITY inbound")
    clients = inbound[0]["settings"]["clients"]
    if any(item.get("email") == IDENTITY for item in clients):
        raise RuntimeError("Identity already allocated")
    if any(item.get("tag") == TAG for item in config["outbounds"]):
        raise RuntimeError("Outbound already allocated")
    wg_text = WG_CONFIG.read_text()
    if PEER_IP in wg_text or IDENTITY in wg_text:
        raise RuntimeError("Peer already allocated")
    if len(profile.get("outbounds", [])) != 1 or profile["outbounds"][0].get("protocol") != "vless":
        raise RuntimeError("Unexpected client template")

    private_key = run("wg", "genkey")
    public_key = run("wg", "pubkey", input_text=private_key + "\n")
    server_public = run("docker", "exec", "wg-relay", "wg", "show", "wg-clients", "public-key")
    identity_id = str(uuid.uuid4())
    clients.append({"id": identity_id, "flow": "xtls-rprx-vision", "email": IDENTITY})
    template = [item for item in config["outbounds"] if item.get("tag") == "wg-flex-macbook"]
    if len(template) != 1:
        raise RuntimeError("MacBook FLEX outbound absent")
    outbound = copy.deepcopy(template[0])
    outbound["tag"] = TAG
    outbound["settings"]["secretKey"] = private_key
    outbound["settings"]["address"] = [f"{PEER_IP}/32"]
    outbound["settings"]["peers"][0]["publicKey"] = server_public
    outbound["settings"]["peers"][0].pop("preSharedKey", None)
    outbound["settings"]["peers"][0]["endpoint"] = "172.19.0.2:51850"
    config["outbounds"].insert(-1, outbound)
    config["routing"]["rules"].insert(-1, {"type": "field", "user": [IDENTITY], "outboundTag": TAG})

    profile["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] = identity_id
    profile["outbounds"][0]["tag"] = "timeweb-flex"
    for rule in profile["routing"]["rules"]:
        rule["outboundTag"] = "timeweb-flex"
    interface, peers = wg_text.split("[Peer]", 1)
    if "[Interface]" not in interface:
        raise RuntimeError("Unexpected WG server config")
    quarantine = (f"PreUp = iptables -I FORWARD -i %i -s {PEER_IP}/32 -j DROP\n"
                  f"PostDown = iptables -D FORWARD -i %i -s {PEER_IP}/32 -j DROP || true\n")
    wg_text = interface + quarantine + "[Peer]" + peers
    wg_text += f"\n[Peer]\n# {IDENTITY}\nPublicKey = {public_key}\nAllowedIPs = {PEER_IP}/32\n"

    private_write(STAGE / "config.candidate.json", json.dumps(config, indent=2) + "\n")
    private_write(STAGE / "wg-clients.candidate.conf", wg_text)
    private_write(STAGE / "client.json", json.dumps(profile, indent=2) + "\n")
    run("/opt/timeweb-reality/xray", "run", "-test", "-config", str(STAGE / "config.candidate.json"))
    print("iPhone FLEX candidate staged and Xray config validated")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"iPhone FLEX staging failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
