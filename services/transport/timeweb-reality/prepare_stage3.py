"""Prepare local-only credentials/configs and a separate synthetic lab fixture."""
if __name__ == "__main__":
    raise SystemExit("RETIRED one-shot prepare_stage3.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import uuid
import zipfile

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

ROOT = Path(__file__).resolve().parent
STAGING = ROOT.parents[2] / ".local/config/historical-stage3-workzone"
ASSETS = {"amd64": ("Xray-linux-64.zip", "23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae"),
          "arm64": ("Xray-linux-arm64-v8a.zip", "4d30283ae614e3057f730f67cd088a42be6fdf91f8639d82cb69e48cde80413c")}
PRIVATE = ["0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
           "172.16.0.0/12", "192.168.0.0/16", "192.0.0.0/24", "192.0.2.0/24", "192.88.99.0/24",
           "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "::/0"]


def write_json(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    path.chmod(0o600)


def keypair(urlsafe=False):
    key = X25519PrivateKey.generate()
    encode = base64.urlsafe_b64encode if urlsafe else base64.b64encode
    def enc(raw):
        text = encode(raw).decode()
        return text.rstrip("=") if urlsafe else text
    return {"private": enc(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())),
            "public": enc(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}


def credentials(path, lab=False):
    if path.exists():
        return json.loads(path.read_text())
    value = {"reality": keypair(True), "wg_client": keypair(),
             "psk": base64.b64encode(secrets.token_bytes(32)).decode(),
             "short_id": secrets.token_hex(8),
             "macbook_uuid": str(uuid.uuid4()), "iphone_uuid": str(uuid.uuid4())}
    if lab:
        value["wg_server"] = keypair()
        value["unauthorized_uuid"] = str(uuid.uuid4())
    write_json(path, value)
    return value


def server_config(keys, endpoint, wg_public, target, sni, listen="127.0.0.1"):
    users = [{"id": keys[device + "_uuid"], "email": device + "-reality-fornex",
              "flow": "xtls-rprx-vision"} for device in ("macbook", "iphone")]
    return {"log": {"loglevel": "warning"},
        "dns": {"tag": "dns-fornex", "queryStrategy": "UseIPv4", "disableFallback": True,
                "servers": ["https://1.1.1.1/dns-query"]},
        "inbounds": [{"tag": "reality-in", "listen": listen, "port": 443, "protocol": "vless",
            "settings": {"clients": users, "decryption": "none"},
            "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {
                "show": False, "target": target, "serverNames": [sni],
                "privateKey": keys["reality"]["private"], "shortIds": [keys["short_id"]]}}}],
        "outbounds": [{"tag": "blocked", "protocol": "blackhole"},
            {"tag": "wg-fornex", "protocol": "wireguard", "settings": {
                "noKernelTun": True, "secretKey": keys["wg_client"]["private"],
                "address": ["10.20.0.3/32"], "mtu": 1380, "workers": 1, "domainStrategy": "ForceIPv4",
                "peers": [{"publicKey": wg_public, "preSharedKey": keys["psk"], "endpoint": endpoint,
                           "allowedIPs": ["0.0.0.0/0"], "keepAlive": 25}]}}],
        "routing": {"domainStrategy": "AsIs", "rules": [
            {"type": "field", "ip": PRIVATE + ["94.241.171.65/32", "103.75.126.143/32", "89.252.153.129/32"], "outboundTag": "blocked"},
            {"type": "field", "inboundTag": ["dns-fornex"], "ip": ["1.1.1.1/32"], "port": "443", "network": "tcp", "outboundTag": "wg-fornex"},
            {"type": "field", "user": [u["email"] for u in users], "outboundTag": "wg-fornex"},
            {"type": "field", "network": "tcp,udp", "outboundTag": "blocked"}]}}


def client_config(keys, device, address, sni, port=10808, user_id=None):
    return {"log": {"loglevel": "warning"},
        "inbounds": [{"tag": "local-socks", "listen": "127.0.0.1", "port": port, "protocol": "socks",
                      "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [{"tag": "blocked", "protocol": "blackhole"},
            {"tag": "timeweb-fornex", "protocol": "vless", "settings": {"vnext": [{
                "address": address, "port": 443, "users": [{"id": user_id or keys[device + "_uuid"],
                "encryption": "none", "flow": "xtls-rprx-vision"}]}]},
             "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {
                 "serverName": sni, "fingerprint": "chrome", "publicKey": keys["reality"]["public"], "shortId": keys["short_id"]}}}],
        "routing": {"domainStrategy": "AsIs", "rules": [
            {"type": "field", "inboundTag": ["local-socks"], "outboundTag": "timeweb-fornex"}]}}


def download():
    STAGING.mkdir(mode=0o700, parents=True, exist_ok=True)
    meta = {}
    for arch, (name, expected) in ASSETS.items():
        archive = STAGING / name
        url = "https://github.com/XTLS/Xray-core/releases/download/v26.3.27/" + name
        if not archive.exists():
            print("Downloading verified candidate " + arch, flush=True)
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--connect-timeout", "10",
                            "--max-time", "90", "--output", str(archive), url], check=True, timeout=95)
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, "Archive hash mismatch"
        with zipfile.ZipFile(archive) as z:
            data = z.read("xray")
        out = ROOT / "vendor" / arch / "xray"
        out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        out.write_bytes(data)
        out.chmod(0o755)
        meta[arch] = {"url": url, "archive_sha256": expected, "binary_sha256": hashlib.sha256(data).hexdigest()}
        archive.unlink()
    STAGING.rmdir()
    write_json(ROOT / "vendor/artifacts.json", meta)


def main():
    os.umask(0o077)
    download()
    keys = credentials(ROOT / "staging/fornex/secrets.json")
    server = server_config(keys, "103.75.126.143:51821", "yjkRluzDifiJqj9loXlxcbIsEQP3uUsPmlwJcmZGOlE=",
                           "23.12.158.97:443", "www.microsoft.com")
    write_json(ROOT / "staging/fornex/server.loopback.json", server)
    for device in ("macbook", "iphone"):
        write_json(ROOT / ("staging/fornex/client-" + device + ".json"),
                   client_config(keys, device, "94.241.171.65", "www.microsoft.com"))
    peer = "[Peer]\nPublicKey = " + keys["wg_client"]["public"] + "\nPresharedKey = " + keys["psk"] + "\nAllowedIPs = 10.20.0.3/32\n"
    (ROOT / "staging/fornex/new-peer.fragment.conf").write_text(peer)
    lab = ROOT / "lab/input"
    testkeys = credentials(lab / "secrets.json", lab=True)
    write_json(lab / "server.json", server_config(testkeys, "10.250.2.2:51821", testkeys["wg_server"]["public"],
                "10.250.3.2:443", "reality.lab", listen="10.250.1.2"))
    write_json(lab / "client.json", client_config(testkeys, "macbook", "10.250.1.2", "reality.lab"))
    write_json(lab / "bad-client.json", client_config(testkeys, "macbook", "10.250.1.2", "reality.lab", 10809, testkeys["unauthorized_uuid"]))
    (lab / "wg-server.conf").write_text("[Interface]\nPrivateKey = " + testkeys["wg_server"]["private"] +
        "\nListenPort = 51821\n\n[Peer]\nPublicKey = " + testkeys["wg_client"]["public"] +
        "\nPresharedKey = " + testkeys["psk"] + "\nAllowedIPs = 10.20.0.3/32\n")
    print("Local staging and independent lab configs created; no remote connection or deployment", flush=True)


if __name__ == "__main__":
    main()
