"""Scoped Cenuta rollout. Secrets and reproducible artifacts stay in System."""
if __name__ == "__main__":
    raise SystemExit("RETIRED one-shot stage8_cenuta.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import argparse
import base64
import copy
import hashlib
import io
import json
import os
import secrets
import subprocess
import tarfile
import uuid
from run_backup import ROOT, ssh_args
from prepare_stage3 import keypair, PRIVATE

DEST = ROOT / "stage8-cenuta"
REMOTE = "/var/backups/timeweb-reality/stage8-cenuta"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def call(host, command, data=None, timeout=60):
    p = subprocess.run(ssh_args(host) + [("sudo -n " if host == "cenuta" else "") + command],
                       input=data, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"{host}: rc={p.returncode}: " + p.stderr.decode())
    return p.stdout

def put(path, data):
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    path.chmod(0o600)

def prepare():
    DEST.mkdir(mode=0o700, exist_ok=False)
    for h in ("cenuta", "timeweb"):
        (DEST / h).mkdir(mode=0o700)
    c = DEST / "cenuta"
    t = DEST / "timeweb"
    before = call("cenuta", "cat /etc/wireguard/wg-cenuta.conf")
    assert sha(before) == "5504135666c08cf0e0c55ac020f57104f5c0a1b9d1b30a480382e925f71478aa"
    nft_before = call("cenuta", "cat /etc/nftables.conf")
    put(c / "wg.before", before)
    put(c / "nft.before", nft_before)
    put(c / "ruleset.before", call("cenuta", "nft -s list ruleset"))
    peer = keypair()
    psk = base64.b64encode(secrets.token_bytes(32)).decode()
    put(c / "peer.psk", psk + "\n")
    put(c / "peer.public", peer["public"] + "\n")
    fragment = f"\n# BEGIN REALITY-C3\n[Peer]\nPublicKey = {peer['public']}\nPresharedKey = {psk}\nAllowedIPs = 10.40.40.3/32\n# END REALITY-C3\n"
    after = before.decode().replace("[Interface]\n", "[Interface]\nPreUp = /bin/bash /etc/reality-c3/guard.sh\n", 1) + fragment
    assert after != before.decode()
    put(c / "wg.after", after)
    denied = [x for x in PRIVATE if ":" not in x] + ["94.241.171.65/32", "103.75.126.143/32", "89.252.153.129/32"]
    nft = '''table inet reality_c3 {
 chain input {
  type filter hook input priority -10; policy accept;
  iifname "wg-cenuta" ip saddr 10.40.40.3 counter drop
 }
 chain forward {
  type filter hook forward priority -10; policy accept;
'''
    for net in denied:
        nft += f'  iifname "wg-cenuta" ip saddr 10.40.40.3 ip daddr {net} counter drop\n'
    nft += '  iifname "wg-cenuta" ip saddr 10.40.40.3 oifname != "ens3" counter drop\n }\n}\n'
    put(c / "guard.nft", nft)
    put(c / "nft.after", nft_before + b"\n# BEGIN REALITY-C3\n" + nft.encode() + b"# END REALITY-C3\n")
    put(c / "guard.sh", '''#!/bin/bash
set -euo pipefail
cd /etc/reality-c3
if ! nft list table inet reality_c3 >/dev/null 2>&1; then nft -f guard.nft; fi
diff -u guard.expected <(nft -s list table inet reality_c3)
''')
    old = call("timeweb", "cat /opt/timeweb-reality/config.json")
    assert sha(old) == "34cf6121a487bbb69e2082eb3e7be9f1d704f8f2fcabfe64d6a03e74fd3b5534"
    put(t / "config.before", old)
    for name in ("guard.nft", "guard.expected", "guard.sh"):
        put(t / (name + ".before"), call("timeweb", "cat /opt/timeweb-reality/" + name))
    config = json.loads(old)
    config["dns"] = {"tag":"dns-foreign", "queryStrategy":"UseIPv4", "disableFallback":False,
                     "servers":[{"address":"https://1.1.1.1/dns-query","tag":"dns-fornex","timeoutMs":3000},
                                {"address":"https://1.0.0.1/dns-query","tag":"dns-cenuta","timeoutMs":3000}]}
    wg = copy.deepcopy(config["outbounds"][1])
    wg["tag"] = "wg-cenuta"
    wg["settings"].update(secretKey=peer["private"], address=["10.40.40.3/32"])
    wg["settings"]["peers"] = [{"publicKey":call("cenuta", "wg show wg-cenuta public-key").decode().strip(),
                                "preSharedKey":psk,"endpoint":"89.252.153.129:51840","allowedIPs":["0.0.0.0/0"],"keepAlive":25}]
    config["outbounds"].append(wg)
    users = []
    for device in ("macbook", "iphone"):
        user = {"id":str(uuid.uuid4()),"email":device+"-reality-cenuta","flow":"xtls-rprx-vision"}
        users.append(user)
        label = "MacBook-Sergey" if device == "macbook" else "iPhone"
        client = json.loads((ROOT / "stage56-timeweb" / ("TimeWeb-REALITY-Fornex-" + label + ".json")).read_text())
        client["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] = user["id"]
        # Preserve the imported profile's routing tag to avoid incompatible client rewrites.
        put(DEST / ("TimeWeb-REALITY-Cenuta-" + label + ".json"), json.dumps(client, indent=2)+"\n")
    config["inbounds"][0]["settings"]["clients"].extend(users)
    rules = config["routing"]["rules"]
    rules.insert(2,{"type":"field","inboundTag":["dns-cenuta"],"ip":["1.0.0.1/32"],"port":"443","network":"tcp","outboundTag":"wg-cenuta"})
    rules.insert(-1,{"type":"field","user":[u["email"] for u in users],"outboundTag":"wg-cenuta"})
    put(t / "config.after", json.dumps(config, indent=2)+"\n")
    guard = (t / "guard.nft.before").read_text().replace(" chain guard {", " chain guard {\n  ip daddr 89.252.153.129 udp dport 51840 counter accept",1)
    assert guard != (t / "guard.nft.before").read_text()
    put(t / "guard.nft.after", guard)
    put(t / "guard.sh.after", (t / "guard.sh.before").read_bytes())
    for h in ("cenuta", "timeweb"):
        folder = DEST / h
        control = (ROOT / ("stage8_" + h + "_control.sh")).read_text().replace("@REMOTE@",REMOTE)
        for name in ("wg.before", "wg.after", "nft.before", "nft.after", "config.before", "config.after"):
            if (folder / name).exists():
                control = control.replace("@"+name+"@",sha((folder / name).read_bytes()))
        put(folder / "control.sh", control)
    manifest = {"scope":"new Cenuta .3 and second TimeWeb outbound; no old WG restart", "files":{str(p.relative_to(DEST)):sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}}
    put(DEST / "manifest.json",json.dumps(manifest,indent=2)+"\n")
    print("PREPARED: protected artifacts, no deployment")

def upload(host):
    folder = DEST / host
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as archive:
        for p in folder.iterdir():
            if p.is_file(): archive.add(p,arcname=p.name)
    call(host, "bash -c 'set -e; umask 077; mkdir " + REMOTE + "; tar -xf - -C " + REMOTE + "'",buf.getvalue())
    print(host,"UPLOADED")

def refresh(host):
    folder = DEST / host
    source = (ROOT / ("stage8_"+host+"_control.sh")).read_text().replace("@REMOTE@",REMOTE)
    for name in ("wg.before","wg.after","nft.before","nft.after","config.before","config.after"):
        if (folder/name).exists(): source=source.replace("@"+name+"@",sha((folder/name).read_bytes()))
    put(folder/"control.sh",source)
    call(host,"tee "+REMOTE+"/control.sh",source.encode())
    m=json.loads((DEST/"manifest.json").read_text())
    m["files"][host+"/control.sh"]=sha(source.encode())
    put(DEST/"manifest.json",json.dumps(m,indent=2)+"\n")
    print(host,"CONTROL REFRESHED")

def finalize():
    for host, files in {"cenuta": {"wg.after":"/etc/wireguard/wg-cenuta.conf", "nft.after":"/etc/nftables.conf"}, "timeweb":{"config.after":"/opt/timeweb-reality/config.json", "guard.nft.after":"/opt/timeweb-reality/guard.nft"}}.items():
        for local, remote in files.items():
            assert call(host, "cat " + remote) == (DEST/host/local).read_bytes(), (host,local)
        name = "guard.expected" if host == "cenuta" else "guard.expected.after"
        put(DEST/host/name, call(host,"cat "+REMOTE+"/"+name))
    clients = ROOT.parents[1]/"clients"
    for source in DEST.glob("TimeWeb-REALITY-Cenuta-*.json"):
        target = clients/source.name
        if target.exists():
            assert target.read_bytes() == source.read_bytes(), "Existing client differs"
        put(target, source.read_bytes())
    manifest=json.loads((DEST/"manifest.json").read_text())
    manifest["files"]={str(p.relative_to(DEST)):sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file() and p.name!="manifest.json"}
    put(DEST/"manifest.json",json.dumps(manifest,indent=2)+"\n")
    print("LIVE FILES VERIFIED; CLIENTS PUBLISHED; MANIFEST SEALED")

if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=["prepare","upload","refresh","validate","apply","rollback","commit","finalize"])
    parser.add_argument("host",nargs="?",choices=["cenuta","timeweb"])
    args=parser.parse_args()
    if args.action=="prepare": prepare()
    elif args.action=="finalize": finalize()
    elif args.action=="upload": upload(args.host)
    elif args.action=="refresh": refresh(args.host)
    else: print(call(args.host,"bash "+REMOTE+"/control.sh "+args.action).decode())
