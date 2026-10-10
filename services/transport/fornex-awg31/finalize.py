"""Retired two-client finalization; historical implementation is reference only."""
import hashlib
import json
import time
from prepare import ROOT, call, put, retired

def main():
    retired('finalize.py')
    # Historical implementation below is intentionally unreachable.
    key = json.loads((ROOT / 'credentials.json').read_text())['clients']['test']['public']
    p = ROOT / 'release/awg0.conf'
    sections = p.read_text().split('\n[Peer]\n')
    filtered = [sections[0]] + [s for s in sections[1:] if ('PublicKey = ' + key) not in s]
    assert len(filtered) == 3
    config = '\n[Peer]\n'.join(filtered)
    put(p, config)
    call('fornex', 'sh -c "umask 077; cat > /opt/fornex-awg31/awg0.conf"', config.encode())
    call('fornex', 'docker restart fornex-awg31')
    time.sleep(3)
    peers = call('fornex', 'docker exec fornex-awg31 awg show awg0 peers').decode().splitlines()
    assert len(peers) == 2 and key not in peers
    before = json.loads((ROOT / 'backup/containers.json').read_text())
    after = json.loads(call('fornex', 'docker inspect amnezia-awg2 wg-exit'))
    for old, new in zip(before, after):
        assert old['Id'] == new['Id']
        assert old['State']['StartedAt'] == new['State']['StartedAt']
        assert new['State']['Running']
    target = ROOT.parent.parent / 'clients'
    for name in ['MacBook-Sergey', 'iPhone-Sergey']:
        src = ROOT / ('Fornex-AWG31-' + name + '.conf')
        dest = target / src.name
        assert not dest.exists() or dest.read_bytes() == src.read_bytes()
        put(dest, src.read_bytes())
    put(ROOT / 'final-status.txt', call('fornex', 'docker ps --format "{{.Names}} {{.Status}}"; docker stats --no-stream --format "{{.Name}} {{.MemUsage}} {{.CPUPerc}}" fornex-awg31; df -h /'))
    put(ROOT / 'release-sha256.json', json.dumps({f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT / 'release').iterdir()}, indent=2))
    print('Restart passed; two production peers; legacy AWG and wg-exit unchanged; profiles published.')

if __name__ == '__main__':
    main()
