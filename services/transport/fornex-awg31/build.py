"""Build the pinned image on explicit invocation; importing does not run a build."""
import io
import json
import tarfile
from prepare import ROOT, call, put

def main():
    base = json.loads((ROOT / 'base-image.json').read_text())['RepoDigests'][0]
    dockerfile = (ROOT / 'source/Dockerfile').read_text().replace('amneziavpn/amneziawg-go:latest', base)
    put(ROOT / 'Dockerfile', dockerfile)
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as t:
        b = dockerfile.encode()
        info = tarfile.TarInfo('Dockerfile')
        info.size = len(b)
        t.addfile(info, io.BytesIO(b))
    output = call('fornex', 'docker build -t fornex-awg31:20260913 -', archive.getvalue(), timeout=240)
    put(ROOT / 'build.log', output)
    print('Build complete')

if __name__ == '__main__':
    main()
