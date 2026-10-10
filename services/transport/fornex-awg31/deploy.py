"""Retired initial AWG31 deployment; historical implementation is reference only."""
import base64
import io
import json
import secrets
import tarfile
from prepare import ROOT, call, put, retired

REMOTE = '/opt/fornex-awg31'
NAME = 'fornex-awg31'

def main():
    retired('deploy.py')
    # Historical implementation below is intentionally unreachable.
    from prepare_stage3 import keypair
    assert call('fornex', "docker ps -a --format '{{.Names}}'").decode().splitlines().count(NAME) == 0
    credentials = ROOT / 'credentials.json'
    if not credentials.exists():
        put(credentials, json.dumps({'server': keypair(), 'header': base64.b64encode(secrets.token_bytes(32)).decode(),
                                    'clients': {n: dict(keypair(), psk=base64.b64encode(secrets.token_bytes(32)).decode())
                                                for n in ['MacBook-Sergey', 'iPhone-Sergey', 'test']}}))
    keys = json.loads(credentials.read_text())
    params = '\n'.join(['Jc = 5', 'Jmin = 10', 'Jmax = 50', 'S1 = 139', 'S2 = 81', 'S3 = 28', 'S4 = 12',
                        'H1 = 1', 'H2 = 2', 'H3 = 3', 'H4 = 4', 'HeaderProtectionKey = ' + keys['header'],
                        'ContentPaddingAddition = 10-100', 'RekeyAfterTime = 100-120', 'RekeyTimeout = 3-7',
                        'RejectAfterTime = 150-180', 'KeepaliveTimeout = 5-15', 'MaxHandshakeAttempts = 15-20',
                        'RandomTrailers = on', 'DisableCookies = on'])
    config = '[Interface]\nAddress = 10.83.1.254/24\nListenPort = 46056\nMTU = 1280\nPrivateKey = ' + keys['server']['private'] + '\n' + params + '\n'
    payload = ROOT / 'release'
    payload.mkdir(mode=0o700, exist_ok=True)
    for i, (name, key) in enumerate(keys['clients'].items(), 1):
        config += '\n[Peer]\nPublicKey = ' + key['public'] + '\nPresharedKey = ' + key['psk'] + f'\nAllowedIPs = 10.83.1.{i}/32\n'
        client = f'[Interface]\nAddress = 10.83.1.{i}/32\nDNS = 1.1.1.1, 1.0.0.1\nMTU = 1280\nPrivateKey = ' + key['private'] + '\n' + params
        client += '\nI1 = <r 2><b 0x858000010001000000000669636c6f756403636f6d0000010001c00c000100010000105a00044d583737>\n'
        client += '\n[Peer]\nPublicKey = ' + keys['server']['public'] + '\nPresharedKey = ' + key['psk'] + '\nEndpoint = 103.75.126.143:46056\nAllowedIPs = 0.0.0.0/0, ::/0\nPersistentKeepalive = 25-35\n'
        put(ROOT / ('Fornex-AWG31-' + name + '.conf'), client)
    put(payload / 'awg0.conf', config)
    put(payload / 'start.sh', '''#!/bin/bash
set -euo pipefail
awg-quick up /opt/fornex-awg31/awg0.conf
iptables -A FORWARD -i awg0 -o eth0 -s 10.83.1.0/24 -j ACCEPT
iptables -A FORWARD -i eth0 -o awg0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -A POSTROUTING -s 10.83.1.0/24 -o eth0 -j MASQUERADE
exec tail -f /dev/null
''')
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as t:
        for p in payload.iterdir():
            t.add(p, arcname=p.name)
    call('fornex', 'install -d -m 700 ' + REMOTE)
    call('fornex', 'tar -xf - -C ' + REMOTE, archive.getvalue())
    image = json.loads(call('fornex', 'docker image inspect fornex-awg31:20260913'))[0]['Id']
    put(ROOT / 'image-id.txt', image)
    command = f'docker run -d --name {NAME} --restart unless-stopped --cap-add NET_ADMIN --device /dev/net/tun --sysctl net.ipv4.ip_forward=1 --sysctl net.ipv4.conf.all.src_valid_mark=1 --memory 256m --pids-limit 128 --log-opt max-size=2m --log-opt max-file=2 -p 103.75.126.143:46056:46056/udp -v {REMOTE}:{REMOTE}:ro --entrypoint /bin/bash {image} {REMOTE}/start.sh'
    put(ROOT / 'run-command.txt', command)
    print(call('fornex', command).decode())
    print('New service created; verify startup before issuing profiles.')

if __name__ == '__main__':
    main()
