"""Scoped BTH pilot: runtime-only relay peer, exact configuration rollback."""
if __name__ == "__main__":
    raise SystemExit("RETIRED one-shot stage9_bth.py: use maintenance_preflight.py --check and run_backup.py; create a reviewed current-generation change instead. No bypass.")
import argparse
import base64
import copy
import io
import json
import os
import secrets
import shlex
import subprocess
import tarfile
import uuid
from pathlib import Path
from stage8_cenuta import call, put, sha
from prepare_stage3 import keypair, PRIVATE
from run_backup import ROOT, ssh_args

D = ROOT / "stage9-bth"
R = "/var/backups/timeweb-reality/stage9-bth"

def router(command):
    m=json.loads((D/"manifest.json").read_text())
    proxy=shlex.join(ssh_args("timeweb")+[f"nsenter -t {m['pid']} -n nc -w 20 10.30.30.2 22"])
    args=["ssh","-i",str(Path.home()/".ssh/codex_mikrotik_20260704"),"-o","IdentitiesOnly=yes",
          "-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","HostKeyAlias=192.168.88.1",
          "-o","ConnectTimeout=8","-o","ProxyCommand="+proxy,"codex@10.30.30.2",command]
    p=subprocess.run(args,capture_output=True,timeout=100)
    if p.returncode or any(e in p.stdout.lower() for e in (b"failure:",b"syntax error",b"expected end",b"no such item")):
        raise RuntimeError("Router command failed: "+p.stdout.decode()+p.stderr.decode())
    return p.stdout

def prepare():
    D.mkdir(mode=0o700)
    pid=int(call("timeweb","docker inspect -f {{.State.Pid}} wg-relay"))
    ns=call("timeweb",f"readlink /proc/{pid}/ns/net").decode().strip()
    put(D/"manifest.json",json.dumps({"pid":pid,"namespace":ns,"runtime_peer_only":True}))
    for name,path in (("config.before","/opt/timeweb-reality/config.json"),
                      ("guard.nft.before","/opt/timeweb-reality/guard.nft"),
                      ("guard.expected.before","/opt/timeweb-reality/guard.expected"),
                      ("wg.before","/opt/wg/config/wg_confs/wg-home.conf")):
        put(D/name,call("timeweb","cat "+path))
    allowed=call("timeweb","docker exec wg-relay wg show wg-home allowed-ips")
    assert b"10.30.30.5" not in allowed and b"10.30.30.5" not in (D/"wg.before").read_bytes()
    put(D/"allowed.before",allowed)
    put(D/"router.before.rsc",router("/export terse show-sensitive"))
    assert b"/ip firewall" in (D/"router.before.rsc").read_bytes()
    assert b"REALITY-B5" not in (D/"router.before.rsc").read_bytes()
    key=keypair(); psk=base64.b64encode(secrets.token_bytes(32)).decode()
    put(D/"peer.public",key["public"]+"\n"); put(D/"peer.psk",psk+"\n")
    config=json.loads((D/"config.before").read_text())
    wg=copy.deepcopy(next(o for o in config["outbounds"] if o.get("tag")=="wg-fornex"))
    wg["tag"]="wg-bth"; wg["settings"].update(secretKey=key["private"],address=["10.30.30.5/32"])
    wg["settings"]["peers"]=[{"publicKey":call("timeweb","docker exec wg-relay wg show wg-home public-key").decode().strip(),
                                "preSharedKey":psk,"endpoint":"172.19.0.2:51830","allowedIPs":["0.0.0.0/0"],"keepAlive":25}]
    config["outbounds"].append(wg)
    users=[]
    for device,label in (("macbook","MacBook-Sergey"),("iphone","iPhone")):
        u={"id":str(uuid.uuid4()),"email":device+"-reality-bth","flow":"xtls-rprx-vision"}; users.append(u)
        c=json.loads((ROOT.parents[1]/"clients"/f"TimeWeb-REALITY-Fornex-{label}.json").read_text())
        c["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"]=u["id"]
        put(D/f"TimeWeb-REALITY-BTH-{label}.json",json.dumps(c,indent=2)+"\n")
    config["inbounds"][0]["settings"]["clients"].extend(users)
    config["routing"]["rules"].insert(-1,{"type":"field","user":[u["email"] for u in users],"outboundTag":"wg-bth"})
    put(D/"config.after",json.dumps(config,indent=2)+"\n")
    guard=(D/"guard.nft.before").read_text().replace(" chain guard {"," chain guard {\n  ip daddr 172.19.0.2 udp dport 51830 counter accept",1)
    assert guard!=(D/"guard.nft.before").read_text()
    put(D/"guard.nft.after",guard)
    denied=[x for x in PRIVATE if ":" not in x]+["94.241.171.65/32","103.75.126.143/32","89.252.153.129/32"]
    nft='table inet reality_b5 {\n chain input {\n type filter hook input priority -10; policy accept;\n iifname "wg-home" ip saddr 10.30.30.5 counter drop\n }\n chain forward {\n type filter hook forward priority -10; policy accept;\n'
    for ip in denied: nft+=f' iifname "wg-home" ip saddr 10.30.30.5 ip daddr {ip} counter drop\n'
    nft+=' iifname "wg-home" ip saddr 10.30.30.5 oifname != "wg-home" counter drop\n }\n}\n'
    put(D/"relay.nft",nft)
    # A dedicated source chain must finish with drop: no fallback to another WAN/VPN.
    commands=[]
    for ip in denied:
        commands.append(f'/ip firewall filter add chain=REALITY-B5 action=drop dst-address={ip} comment="REALITY-B5-private"')
    commands.extend([
        '/ip firewall filter add chain=REALITY-B5 action=accept out-interface=ether1 comment="REALITY-B5-WAN"',
        '/ip firewall filter add chain=REALITY-B5 action=drop comment="REALITY-B5-other"',
        '/ip firewall filter add chain=input action=drop src-address=10.30.30.5 in-interface=wg-home place-before=0 comment="REALITY-B5-input"',
        '/ip firewall filter add chain=forward action=jump jump-target=REALITY-B5 src-address=10.30.30.5 in-interface=wg-home place-before=0 comment="REALITY-B5-forward"',
        '/ip firewall mangle add chain=prerouting action=accept src-address=10.30.30.5 in-interface=wg-home place-before=0 comment="REALITY-B5-main"'])
    put(D/"router.apply.rsc","\n".join(commands)+"\n")
    put(D/"router.rollback.rsc",'/ip firewall filter remove [find where comment~"^REALITY-B5-"]; /ip firewall mangle remove [find where comment="REALITY-B5-main"]')
    control=(ROOT/"stage9_control.sh").read_text().replace("@REMOTE@",R).replace("@PID@",str(pid)).replace("@NS@",ns)
    for name in ("config.before","config.after","wg.before"):
        control=control.replace("@"+name+"@",sha((D/name).read_bytes()))
    put(D/"control.sh",control)
    m=json.loads((D/"manifest.json").read_text()); m["files"]={p.name:sha(p.read_bytes()) for p in D.iterdir() if p.is_file() and p.name!="manifest.json"}
    put(D/"manifest.json",json.dumps(m,indent=2)+"\n")
    print("PREPARED; no runtime changes")

def upload():
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as t:
        for p in D.iterdir():
            if p.is_file(): t.add(p,arcname=p.name)
    call("timeweb",f"bash -c 'umask 077; mkdir {R} && tar -xf - -C {R}'",buf.getvalue())
    print("UPLOADED")

def finalize():
    for name,remote in (("config.after","/opt/timeweb-reality/config.json"),("guard.nft.after","/opt/timeweb-reality/guard.nft")):
        assert (D/name).read_bytes()==call("timeweb","cat "+remote), "Live config mismatch"
    for name in ("relay.expected","guard.expected.after"):
        put(D/name,call("timeweb","cat "+R+"/"+name))
    put(D/"router.after.rsc",router("/export terse"))
    put(D/"router.counters",router('/ip firewall filter print stats where comment~"^REALITY-B5-"'))
    for f in D.glob("TimeWeb-REALITY-BTH-*.json"):
        dst=ROOT.parents[1]/"clients"/f.name
        if dst.exists(): assert dst.read_bytes()==f.read_bytes(), "Existing profile differs"
        put(dst,f.read_bytes())
    m=json.loads((D/"manifest.json").read_text())
    m["files"]={p.name:sha(p.read_bytes()) for p in D.iterdir() if p.is_file() and p.name!="manifest.json"}
    put(D/"manifest.json",json.dumps(m,indent=2)+"\n")
    print("LIVE CONFIG VERIFIED; BTH CLIENTS PUBLISHED; RUNTIME PEER ONLY")

if __name__=="__main__":
    os.umask(0o077)
    p=argparse.ArgumentParser(); p.add_argument("action",choices=["prepare","upload","validate","apply","commit","rollback","router-apply","router-rollback","peer-off","peer-on","finalize"])
    a=p.parse_args().action
    if a=="prepare": prepare()
    elif a=="upload": upload()
    elif a=="finalize": finalize()
    elif a.startswith("router-"):
        if a=="router-apply":
            existing=router('/ip firewall filter print terse where comment~"^REALITY-B5-"')
            assert b"REALITY-B5" not in existing
        print(router((D/(a.replace("-",".")+".rsc")).read_text()).decode())
    else: print(call("timeweb",f"bash {R}/control.sh {a}").decode())
