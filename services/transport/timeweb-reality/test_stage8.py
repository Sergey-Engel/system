"""Bounded dual-profile acceptance; starts only loopback clients on this Mac."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["smoke", "extended"])
    args = parser.parse_args()
    os.umask(0o077)
    out = ROOT / ("stage8-test-" + time.strftime("%Y%m%dT%H%M%S"))
    out.mkdir(mode=0o700)
    processes = []
    reports = []
    try:
        for country, port, expected in (("Fornex",10846,"103.75.126.143"),("Cenuta",10847,"89.252.153.129")):
            base = "stage56-timeweb" if country == "Fornex" else "stage8-cenuta"
            c = json.loads((ROOT/base/f"TimeWeb-REALITY-{country}-MacBook-Sergey.json").read_text())
            assert len(c["outbounds"]) == 1 and c["outbounds"][0]["protocol"] == "vless"
            c["inbounds"][0]["listen"] = "127.0.0.1"
            c["inbounds"][0]["port"] = port
            with socket.socket() as s: s.bind(("127.0.0.1",port))
            path = out / (country+".json")
            path.write_text(json.dumps(c))
            with (out/(country+".log")).open("w") as log:
                p = subprocess.Popen([str(ROOT/"vendor/macos-arm64/xray"),"run","-config",str(path)],stdout=log,stderr=log)
            processes.append(p)
        time.sleep(2)
        assert all(p.poll() is None for p in processes)
        for country, port, expected in (("Fornex",10846,"103.75.126.143"),("Cenuta",10847,"89.252.153.129")):
            checks = [("ip","https://api.ipify.org"),("trace","https://1.1.1.1/cdn-cgi/trace")]
            if args.mode == "extended":
                checks = [("download","https://speed.cloudflare.com/__down?bytes=1048576"),
                          ("upload","https://speed.cloudflare.com/__up"),
                          ("private","http://10.40.40.1/"),
                          ("private-name","http://127.0.0.1.nip.io/")]
            for name,url in checks:
                body = out/f"{country}-{name}.body"
                cmd = ["curl","-q","-4","-sS","--noproxy","","--proxy",f"socks5h://127.0.0.1:{port}",
                       "--connect-timeout","8","--max-time","15","-o",str(body),"-w","%{http_code}",url]
                data = None
                if name=="upload":
                    cmd += ["-X","POST","-H","Content-Type: application/octet-stream","--data-binary","@-"]
                    data = b"0" * 1048576
                start=time.monotonic()
                r=subprocess.run(cmd,input=data,capture_output=True,timeout=20)
                payload=body.read_bytes() if body.exists() else b""
                status=r.stdout.decode().strip()
                valid = r.returncode==0 and status=="200"
                if name=="ip": valid=valid and payload.decode().strip()==expected
                if name=="trace": valid=valid and ("ip="+expected+"\n") in payload.decode()
                if name=="download": valid=valid and len(payload)==1048576
                if name.startswith("private"): valid=r.returncode!=0 and len(payload)==0
                item={"country":country,"test":name,"exit":r.returncode,"HTTP":status,"bytes":len(payload),
                      "seconds":round(time.monotonic()-start,3),"passed":valid,"error":r.stderr.decode()}
                reports.append(item)
                print(json.dumps(item),flush=True)
    finally:
        for p in processes:
            p.terminate()
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait()
        (out/"report.json").write_text(json.dumps(reports,indent=2)+"\n")
        print("REPORT",out,flush=True)
    assert reports and all(r["passed"] for r in reports), "Acceptance incomplete; inspect report"

if __name__=="__main__": main()
