"""Bounded BTH client smoke/transfer tests; never changes host routing."""
import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(); p.add_argument("mode",choices=["smoke","extended","blocked"]); a=p.parse_args()
    os.umask(0o077)
    out=ROOT/("stage9-test-"+time.strftime("%Y%m%dT%H%M%S")); out.mkdir(mode=0o700)
    c=json.loads((ROOT/"stage9-bth/TimeWeb-REALITY-BTH-MacBook-Sergey.json").read_text())
    c["inbounds"][0]["listen"]="127.0.0.1"; c["inbounds"][0]["port"]=10848
    with socket.socket() as s: s.bind(("127.0.0.1",10848))
    path=out/"client.json"; path.write_text(json.dumps(c))
    rows=[]
    with (out/"client.log").open("w") as log:
        child=subprocess.Popen([str(ROOT/"vendor/macos-arm64/xray"),"run","-config",str(path)],stdout=log,stderr=log)
    try:
        time.sleep(1); assert child.poll() is None
        checks=[("ip","https://api.ipify.org"),("ru","https://ya.ru/")]
        if a.mode=="extended": checks=[("download","https://speed.cloudflare.com/__down?bytes=1048576"),("upload","https://speed.cloudflare.com/__up"),("private","http://192.168.88.1/")]
        if a.mode=="blocked": checks=[("blocked","https://api.ipify.org")]
        for name,url in checks:
            body=out/(name+".body")
            cmd=["curl","-q","-4","-sS","--location","--max-redirs","5","--noproxy","","--proxy","socks5h://127.0.0.1:10848","--connect-timeout","6","--max-time","15","-o",str(body),"-w","%{http_code}",url]
            data=None
            if name=="upload": cmd += ["-H","Content-Type: application/octet-stream","--data-binary","@-"]; data=b"0"*1048576
            start=time.monotonic(); r=subprocess.run(cmd,input=data,capture_output=True,timeout=20)
            b=body.read_bytes() if body.exists() else b""
            ok=r.returncode==0 and r.stdout.strip()==b"200"
            if name=="ip":
                import ipaddress
                try: ok=ok and ipaddress.ip_address(b.decode().strip()).is_global and b.strip() not in [b"94.241.171.65",b"103.75.126.143",b"89.252.153.129"]
                except ValueError: ok=False
            if name=="download": ok=ok and len(b)==1048576
            if name in ("private","blocked"): ok=r.returncode!=0 and len(b)==0
            row={"test":name,"exit":r.returncode,"HTTP":r.stdout.decode(),"bytes":len(b),"seconds":round(time.monotonic()-start,3),"passed":ok}
            if name=="ip": row["ip"]=b.decode().strip()
            rows.append(row); print(json.dumps(row),flush=True)
    finally:
        child.terminate()
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: child.kill(); child.wait()
        (out/"report.json").write_text(json.dumps(rows,indent=2)+"\n")
        print(out,flush=True)
    assert rows and all(x["passed"] for x in rows), "Probe acceptance failed"

if __name__=="__main__": main()
