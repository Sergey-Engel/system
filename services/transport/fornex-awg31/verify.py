"""Bounded same-host client smoke test; not remote device acceptance."""
from prepare import ROOT, call, put
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True, help='Unused device profile basename without .conf')
args = parser.parse_args()
assert '/' not in args.profile and args.profile.startswith('Fornex-AWG31-')

image = (ROOT / 'image-id.txt').read_text().strip()
name = 'fornex-awg31-smoke'
config = (ROOT / (args.profile + '.conf')).read_text()
config = '\n'.join(x for x in config.splitlines() if not x.startswith('DNS =')) + '\n'
config = config.replace('0.0.0.0/0, ::/0', '0.0.0.0/1, 128.0.0.0/1')
call('fornex', f'docker run -d --name {name} --cap-add NET_ADMIN --device /dev/net/tun --sysctl net.ipv4.conf.all.src_valid_mark=1 --memory 128m --pids-limit 128 --entrypoint tail {image} -f /dev/null')
try:
    gateway = json.loads(call('fornex', f'docker inspect {name}'))[0]['NetworkSettings']['Networks']['bridge']['Gateway']
    call('fornex', f'docker exec {name} ip route add 103.75.126.143/32 via {gateway}')
    call('fornex', f'docker exec -i {name} sh -c "umask 077; cat > /tmp/test.conf"', config.encode())
    call('fornex', f'docker exec {name} awg-quick up /tmp/test.conf')
    result = call('fornex', f'docker exec {name} curl -fsS --connect-timeout 10 --max-time 25 https://1.1.1.1/cdn-cgi/trace', timeout=35)
    put(ROOT / 'smoke-trace.txt', result)
    assert b'ip=103.75.126.143' in result
    print('Tunnel egress IP verified', flush=True)
    for label, command in {
        'download': "curl -fsS --connect-timeout 10 --max-time 40 -o /dev/null -w '%{http_code} %{size_download} %{speed_download}' 'https://speed.cloudflare.com/__down?bytes=1000000'",
        'upload': "head -c 1000000 /dev/zero | curl -fsS --connect-timeout 10 --max-time 40 --data-binary @- -o /dev/null -w '%{http_code} %{size_upload} %{speed_upload}' https://speed.cloudflare.com/__up",
    }.items():
        result = call('fornex', f'docker exec {name} sh -c "{command}"', timeout=50)
        put(ROOT / ('smoke-' + label + '.txt'), result)
        print(label, result.decode(), flush=True)
        assert result.startswith(b'200 1000000 ')
    stamps = call('fornex', f'docker exec {name} awg show test latest-handshakes').decode()
    assert any(int(x.split()[-1]) > 0 for x in stamps.splitlines())
    print('Handshake verified', flush=True)
finally:
    call('fornex', f'docker rm -f {name}')
