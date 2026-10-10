"""Synthetic REALITY/WG acceptance lab. Run only in the network-none lab container."""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import signal
import socketserver
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse

WORK = Path('/work')
OUT = Path('/out')
PROCS = []
RESULTS = []


def cmd(args, ns=None, check=True, timeout=12):
    argv = ['ip', 'netns', 'exec', ns] + args if ns else args
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'{argv[:5]}: {result.stderr[-1500:]}')
    return result


def spawn(args, ns, name, env=None):
    log = open(OUT / (name + '.log'), 'w')
    proc = subprocess.Popen(['ip', 'netns', 'exec', ns] + args, stdout=log,
                            stderr=subprocess.STDOUT, env=env)
    log.close()
    PROCS.append(proc)
    return proc


def record(name, passed, **evidence):
    RESULTS.append(dict(name=name, passed=bool(passed), **evidence))
    print(('PASS ' if passed else 'FAIL ') + name, flush=True)


def link(a, ai, aa, b, bi, ba):
    cmd(['ip', 'link', 'add', ai, 'type', 'veth', 'peer', 'name', bi])
    for ns, iface, addr in ((a, ai, aa), (b, bi, ba)):
        cmd(['ip', 'link', 'set', iface, 'netns', ns])
        cmd(['ip', '-n', ns, 'addr', 'add', addr, 'dev', iface])
        cmd(['ip', '-n', ns, 'link', 'set', iface, 'up'])


def ipt(ns, *args):
    return cmd(['iptables', '-w', '2'] + list(args), ns).stdout


def snapshot():
    links = json.loads(cmd(['ip', '-j', 'link'], 'relay').stdout)
    return dict(links=[{k: x.get(k) for k in ('ifname', 'flags', 'address', 'link_type')} for x in links],
                addresses=json.loads(cmd(['ip', '-j', '-4', 'addr'], 'relay').stdout),
                routes=json.loads(cmd(['ip', '-j', '-4', 'route', 'show', 'table', 'all'], 'relay').stdout),
                rules=json.loads(cmd(['ip', '-j', '-4', 'rule'], 'relay').stdout))


def curl(url, port=10808, extra=(), uid=None, limit=5):
    args = ['curl', '--silent', '--show-error', '--fail', '--connect-timeout', str(limit), '--max-time', str(limit),
            '--cacert', '/work/lab.crt', '--proxy', f'socks5h://127.0.0.1:{port}', '--noproxy', '']
    if uid is not None:
        args = ['setpriv', '--reuid', str(uid), '--regid', str(uid), '--clear-groups'] + args
    return cmd(args + list(extra) + [url], 'client', check=False, timeout=limit+2)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def response(self, body, kind='application/json'):
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def answer(self, body=b''):
        if self.path.startswith('/dns-query'):
            import dns.message
            import dns.rrset
            import dns.rdatatype
            if not body:
                token = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)['dns'][0]
                body = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
            query = dns.message.from_wire(body)
            reply = dns.message.make_response(query)
            q = query.question[0]
            name = str(q.name)
            address = '10.123.0.1' if name == 'private.lab.' else '93.184.216.34'
            if q.rdtype == dns.rdatatype.A:
                reply.answer.append(dns.rrset.from_text(q.name, 5, 'IN', 'A', address))
            print(json.dumps(dict(kind='doh', source=self.client_address[0], query=name)), flush=True)
            self.response(reply.to_wire(), 'application/dns-message')
            return
        print(json.dumps(dict(kind='web', source=self.client_address[0], path=self.path,
                              length=len(body))), flush=True)
        if self.path == '/large':
            self.response(b'x' * 262144, 'application/octet-stream')
        else:
            self.response(json.dumps(dict(source=self.client_address[0], length=len(body),
                                         sha256=hashlib.sha256(body).hexdigest())).encode())

    def do_GET(self):
        self.answer()

    def do_POST(self):
        self.answer(self.rfile.read(int(self.headers.get('Content-Length', '0'))))


def serve():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain('/work/lab.crt', '/work/lab.key')
    class Server(http.server.ThreadingHTTPServer):
        def server_bind(self):
            socketserver.TCPServer.server_bind(self)
            self.server_name = 'fixture.lab'
            self.server_port = self.server_address[1]
    for addr in ('93.184.216.34', '10.123.0.1'):
        server = Server((addr, 443), Handler)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    signal.pause()


def serve_h2(address='10.250.3.2', doh=False):
    import h2.config
    import h2.connection
    import h2.events
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain('/work/lab.crt', '/work/lab.key')
    ctx.set_alpn_protocols(['h2', 'http/1.1'])
    ctx.set_ecdh_curve('X25519')

    class Target(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                self.request.settimeout(20)
                with ctx.wrap_socket(self.request, server_side=True) as conn:
                    if conn.selected_alpn_protocol() != 'h2':
                        conn.recv(4096)
                        conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK')
                        return
                    protocol = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False))
                    bodies = {}
                    protocol.initiate_connection()
                    conn.sendall(protocol.data_to_send())
                    while True:
                        chunk = conn.recv(16384)
                        if not chunk:
                            return
                        for event in protocol.receive_data(chunk):
                            if isinstance(event, h2.events.RequestReceived):
                                bodies[event.stream_id] = bytearray()
                            elif isinstance(event, h2.events.DataReceived):
                                bodies[event.stream_id].extend(event.data)
                                protocol.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                            elif isinstance(event, h2.events.StreamEnded):
                                body = b'OK'
                                kind = 'text/plain'
                                if doh:
                                    import dns.message
                                    import dns.rrset
                                    import dns.rdatatype
                                    query = dns.message.from_wire(bytes(bodies[event.stream_id]))
                                    reply = dns.message.make_response(query)
                                    q = query.question[0]
                                    name = str(q.name)
                                    resolved = '10.123.0.1' if name == 'private.lab.' else '93.184.216.34'
                                    if q.rdtype == dns.rdatatype.A:
                                        reply.answer.append(dns.rrset.from_text(q.name, 5, 'IN', 'A', resolved))
                                    body, kind = reply.to_wire(), 'application/dns-message'
                                    print(json.dumps(dict(kind='doh', source=self.client_address[0], query=name)), flush=True)
                                protocol.send_headers(event.stream_id, [(':status', '200'), ('content-length', str(len(body))), ('content-type', kind)])
                                protocol.send_data(event.stream_id, body, end_stream=True)
                                del bodies[event.stream_id]
                        conn.sendall(protocol.data_to_send())
            except (OSError, ssl.SSLError):
                pass

    with socketserver.ThreadingTCPServer((address, 443), Target) as server:
        server.daemon_threads = True
        server.serve_forever()


def main():
    start = time.time()
    error = None
    os.umask(0o077)
    try:
        links = json.loads(cmd(['ip', '-j', 'link']).stdout)
        kernel_fallbacks = {'tunl0', 'gre0', 'gretap0', 'erspan0', 'ip_vti0', 'ip6_vti0',
                            'sit0', 'ip6tnl0', 'ip6gre0'}
        if any(x['ifname'] != 'lo' and (x['ifname'] not in kernel_fallbacks or 'UP' in x['flags']) for x in links):
            raise RuntimeError('Unexpected network interface in network-none lab')
        if json.loads(cmd(['ip', '-j', 'route']).stdout):
            raise RuntimeError('Unexpected initial route in network-none lab')
        WORK.mkdir(exist_ok=True)
        WORK.chmod(0o755)
        for source in Path('/input').glob('*.json'):
            if source.name == 'secrets.json':
                continue
            dest = WORK / source.name
            data = json.loads(source.read_text())
            data['log'] = {'loglevel': 'debug'}
            dest.write_text(json.dumps(data))
            dest.chmod(0o644)
            cmd(['/xray/xray', 'run', '-test', '-config', str(dest)])
        record('xray_config_validation', True)
        for ns in ('client', 'relay', 'exit', 'target', 'web'):
            cmd(['ip', 'netns', 'add', ns])
            cmd(['ip', '-n', ns, 'link', 'set', 'lo', 'up'])
            cmd(['sysctl', '-qw', 'net.ipv4.ip_unprivileged_port_start=0'], ns)
        link('client', 'c-r', '10.250.1.1/24', 'relay', 'r-c', '10.250.1.2/24')
        link('relay', 'r-e', '10.250.2.1/24', 'exit', 'e-r', '10.250.2.2/24')
        link('relay', 'r-t', '10.250.3.1/24', 'target', 't-r', '10.250.3.2/24')
        link('exit', 'e-w', '93.184.216.1/24', 'web', 'w-e', '93.184.216.34/24')
        for addr in ('1.1.1.1/32', '10.123.0.1/32'):
            cmd(['ip', '-n', 'web', 'addr', 'add', addr, 'dev', 'lo'])
        cmd(['ip', '-n', 'relay', 'route', 'add', 'default', 'via', '10.250.2.2'])
        cmd(['ip', '-n', 'web', 'route', 'add', 'default', 'via', '93.184.216.1'])
        for addr in ('1.1.1.1/32', '10.123.0.1/32'):
            cmd(['ip', '-n', 'exit', 'route', 'add', addr, 'via', '93.184.216.34'])
        cmd(['sysctl', '-qw', 'net.ipv4.ip_forward=1'], 'exit')
        cmd(['ip', '-n', 'exit', 'link', 'add', 'wg0', 'type', 'wireguard'])
        cmd(['wg', 'setconf', 'wg0', '/input/wg-server.conf'], 'exit')
        cmd(['ip', '-n', 'exit', 'addr', 'add', '10.20.0.2/24', 'dev', 'wg0'])
        cmd(['ip', '-n', 'exit', 'link', 'set', 'wg0', 'up'])
        for net in ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16',
                    '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '240.0.0.0/4'):
            ipt('exit', '-A', 'FORWARD', '-s', '10.20.0.3/32', '-d', net, '-j', 'DROP')
        ipt('exit', '-A', 'INPUT', '-s', '10.20.0.3/32', '-j', 'DROP')
        ipt('exit', '-t', 'nat', '-A', 'POSTROUTING', '-s', '10.20.0.3/32', '-o', 'e-w', '-j', 'MASQUERADE')
        ipt('relay', '-N', 'XRAY_ONLY')
        ipt('relay', '-A', 'OUTPUT', '-m', 'owner', '--uid-owner', '10001', '-j', 'XRAY_ONLY')
        ipt('relay', '-A', 'XRAY_ONLY', '-p', 'tcp', '--sport', '443', '-d', '10.250.1.1',
            '-m', 'conntrack', '--ctstate', 'ESTABLISHED', '-j', 'ACCEPT')
        ipt('relay', '-A', 'XRAY_ONLY', '-p', 'udp', '-d', '10.250.2.2', '--dport', '51821', '-j', 'ACCEPT')
        ipt('relay', '-A', 'XRAY_ONLY', '-p', 'tcp', '-d', '10.250.3.2', '--dport', '443', '-j', 'ACCEPT')
        ipt('relay', '-A', 'XRAY_ONLY', '-j', 'DROP')
        cmd(['ip6tables', '-A', 'OUTPUT', '-m', 'owner', '--uid-owner', '10001', '-j', 'DROP'], 'relay')
        spawn(['tcpdump', '-ni', 'any', '-nn', '-l', '-c', '500'], 'relay', 'packets')
        cmd(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=reality.lab',
             '-addext', 'subjectAltName=DNS:reality.lab,DNS:good.lab,DNS:private.lab,DNS:uncached.lab,IP:1.1.1.1,IP:93.184.216.34',
             '-addext', 'basicConstraints=critical,CA:TRUE', '-keyout', '/work/lab.key', '-out', '/work/lab.crt'])
        (WORK / 'lab.crt').chmod(0o644)
        spawn(['/opt/lab/.venv/bin/python', '-B', '/scripts/run_lab.py', 'target'], 'target', 'target')
        spawn(['/opt/lab/.venv/bin/python', '-B', '/scripts/run_lab.py', 'serve'], 'web', 'fixture')
        spawn(['/opt/lab/.venv/bin/python', '-B', '/scripts/run_lab.py', 'doh'], 'web', 'doh')
        for ns, listeners in (('target', 1), ('web', 3)):
            deadline = time.monotonic() + 8
            while len(cmd(['ss', '-H', '-lnt', 'sport', '=', ':443'], ns).stdout.splitlines()) != listeners:
                if time.monotonic() > deadline:
                    raise RuntimeError('Fixture readiness timeout: ' + ns)
                time.sleep(0.1)
        control = cmd(['curl', '-sS', '--max-time', '3', '--cacert', '/work/lab.crt',
                       'https://93.184.216.34/'], 'relay')
        record('direct_route_exists_for_negative_control', json.loads(control.stdout)['source'] == '10.250.2.1')
        leak = spawn(['tcpdump', '-ni', 'r-e', '-nn', '-l', '-c', '100', 'tcp or udp port 53'], 'relay', 'leak-check')
        before = snapshot()
        restricted = ['setpriv', '--reuid', '10001', '--regid', '10001', '--clear-groups',
                      '--bounding-set=-all,+net_bind_service', '--inh-caps=-all,+net_bind_service',
                      '--ambient-caps=-all,+net_bind_service', '--no-new-privs']
        env = dict(os.environ, SSL_CERT_FILE='/work/lab.crt')
        server = spawn(restricted + ['/xray/xray', 'run', '-config', '/work/server.json'], 'relay', 'server', env)
        for name in ('client', 'bad-client'):
            spawn(['/xray/xray', 'run', '-config', '/work/' + name + '.json'], 'client', name)
        iphone = json.loads((WORK / 'client.json').read_text())
        iphone['inbounds'][0]['port'] = 10810
        iphone['outbounds'][1]['settings']['vnext'][0]['users'][0]['id'] = json.loads((WORK / 'server.json').read_text())['inbounds'][0]['settings']['clients'][1]['id']
        (WORK / 'iphone.json').write_text(json.dumps(iphone))
        spawn(['/xray/xray', 'run', '-config', '/work/iphone.json'], 'client', 'iphone')
        # The pinned REALITY dependency measures post-handshake records for 5s.
        # This bounded lab warmup is not a production readiness contract.
        time.sleep(6)
        status = Path(f'/proc/{server.pid}/status').read_text()
        cap = next(x for x in status.splitlines() if x.startswith('CapEff:')).split()[1]
        uid = next(x for x in status.splitlines() if x.startswith('Uid:')).split()[1]
        record('relay_xray_bind_only_no_net_admin', cap == '0000000000000400' and uid == '10001', uid=uid, cap_eff=cap)
        result = curl('https://93.184.216.34/', limit=15)
        good = result.returncode == 0 and json.loads(result.stdout)['source'] == '93.184.216.1'
        record('reality_vision_userspace_wg_https_exit', good, curl_exit=result.returncode, stderr=result.stderr)
        if not good:
            raise RuntimeError('Positive path failed; remaining tests not accepted')
        result = curl('https://good.lab/')
        doh = [json.loads(x) for x in (OUT / 'doh.log').read_text().splitlines() if x.startswith('{')]
        record('doh_through_wg_exit', result.returncode == 0 and any(x.get('query') == 'good.lab.' and
               x['source'] == '93.184.216.1' for x in doh), curl_exit=result.returncode, stderr=result.stderr)
        result = curl('https://good.lab/', port=10810)
        record('second_device_uuid_valid_xray_only', result.returncode == 0, actual_amnezia_test=False)
        result = curl('https://good.lab/large')
        record('download_256k', result.returncode == 0 and len(result.stdout) == 262144, size=len(result.stdout))
        payload = b'a' * 65536
        (WORK / 'payload').write_bytes(payload)
        result = curl('https://good.lab/upload', extra=('--data-binary', '@/work/payload'))
        record('upload_64k', result.returncode == 0 and json.loads(result.stdout).get('sha256') == hashlib.sha256(payload).hexdigest())
        result = curl('https://93.184.216.34/', port=10809)
        record('unauthorized_uuid_rejected', result.returncode != 0, curl_exit=result.returncode)
        result = curl('https://10.123.0.1/')
        record('private_literal_blocked', result.returncode != 0, curl_exit=result.returncode)
        result = curl('https://[2606:4700:4700::1111]/')
        record('ipv6_literal_blocked', result.returncode != 0, curl_exit=result.returncode)
        result = curl('https://private.lab/')
        counters = ipt('exit', '-L', 'FORWARD', '-n', '-v', '-x')
        dropped = [x.split() for x in counters.splitlines() if '10.0.0.0/8' in x]
        record('private_after_dns_blocked_at_exit', result.returncode != 0 and int(dropped[0][0]) > 0,
               curl_exit=result.returncode, drop_packets=int(dropped[0][0]))
        direct = cmd(restricted + ['curl', '-sS', '--max-time', '3', '--cacert', '/work/lab.crt',
                                  'https://93.184.216.34/'], 'relay', check=False, timeout=5)
        drops = int(ipt('relay', '-L', 'XRAY_ONLY', '-n', '-v', '-x').strip().splitlines()[-1].split()[0])
        record('uid_direct_egress_blocked', direct.returncode != 0 and drops > 0, curl_exit=direct.returncode, drop_packets=drops)
        web_before = (OUT / 'fixture.log').read_text().count('"kind": "web"')
        cmd(['ip', '-n', 'exit', 'link', 'set', 'wg0', 'down'])
        result = curl('https://93.184.216.34/')
        web_after = (OUT / 'fixture.log').read_text().count('"kind": "web"')
        record('wg_down_no_direct_fallback', result.returncode != 0 and web_before == web_after,
               curl_exit=result.returncode, new_web_requests=web_after - web_before)
        cmd(['ip', '-n', 'exit', 'link', 'set', 'wg0', 'up'])
        recovery_start = time.monotonic()
        for attempt in range(4):
            result = curl('https://93.184.216.34/')
            if result.returncode == 0:
                break
            time.sleep(1)
        record('wg_restored_recovers', result.returncode == 0, curl_exit=result.returncode,
               seconds=round(time.monotonic() - recovery_start, 2), attempts=attempt+1)
        ipt('exit', '-I', 'FORWARD', '1', '-s', '10.20.0.3/32', '-d', '1.1.1.1/32', '-p', 'tcp', '--dport', '443', '-j', 'DROP')
        result = curl('https://uncached.lab/')
        dns_drops = int(ipt('exit', '-L', 'FORWARD', '-n', '-v', '-x').splitlines()[2].split()[0])
        record('cold_dns_failure_no_fallback', result.returncode != 0 and dns_drops > 0,
               curl_exit=result.returncode, drop_packets=dns_drops)
        ipt('exit', '-D', 'FORWARD', '-s', '10.20.0.3/32', '-d', '1.1.1.1/32', '-p', 'tcp', '--dport', '443', '-j', 'DROP')
        record('relay_kernel_network_unchanged', before == snapshot())
        memory = [x for x in Path(f'/proc/{server.pid}/status').read_text().splitlines() if x.startswith(('VmRSS:', 'VmHWM:'))]
        record('native_arm64_short_run_memory_sample', True, sample=memory, production_budget_accepted=False)
        (OUT / 'exit-firewall.txt').write_text(ipt('exit', '-S') + ipt('exit', '-t', 'nat', '-S'))
        (OUT / 'relay-firewall.txt').write_text(ipt('relay', '-S') + cmd(['ip6tables', '-S'], 'relay').stdout)
        server.terminate()
        server.wait(timeout=3)
        result = curl('https://93.184.216.34/')
        record('relay_stopped_client_fails', result.returncode != 0, curl_exit=result.returncode)
        leak.terminate()
        leak.wait(timeout=3)
        leak_log = (OUT / 'leak-check.log').read_text()
        record('no_direct_tcp_or_plain_dns_on_relay_egress', '0 packets captured' in leak_log,
               scope='r-e TCP and UDP/53; synthetic run only')
    except Exception as exc:
        error = str(exc)
        print('LAB ERROR ' + error, flush=True)
    finally:
        for ns in ('relay', 'exit'):
            try:
                (OUT / (ns + '-counters.txt')).write_text(ipt(ns, '-L', '-n', '-v', '-x'))
            except Exception:
                pass
        for proc in reversed(PROCS):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
        OUT.mkdir(exist_ok=True)
        report = dict(start_unix=start, elapsed_seconds=round(time.time()-start, 2), results=RESULTS,
                      error=error, production_connections=False, external_network=False,
                      accepted=error is None and all(x['passed'] for x in RESULTS))
        (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['accepted'] else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['serve']:
        serve()
    elif sys.argv[1:] == ['target']:
        serve_h2()
    elif sys.argv[1:] == ['doh']:
        serve_h2('1.1.1.1', doh=True)
    else:
        sys.exit(main())
