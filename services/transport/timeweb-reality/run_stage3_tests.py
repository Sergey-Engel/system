"""Bounded local Docker tests; never contacts a production VPS."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
IMAGE = 'timeweb-reality-lab:20260912'


def run(args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def bind(source, target, readonly=True):
    return ['--mount', f'type=bind,source={source},target={target}' + (',readonly' if readonly else '')]


def main():
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT / 'lab/results' / stamp
    out.mkdir(mode=0o700, parents=True)
    contracts = run([sys.executable, '-B', str(ROOT / 'lab/test_contract.py')])
    (out / 'contract-tests.log').write_text(contracts.stdout + contracts.stderr)
    print('Offline contract tests: exit ' + str(contracts.returncode), flush=True)
    if contracts.returncode:
        return contracts.returncode
    inputs = list((ROOT / 'lab/input').glob('*')) + list((ROOT / 'staging/fornex').glob('*'))
    inputs += [ROOT / name for name in ('prepare_stage3.py', 'run_stage3_tests.py', 'lab/run_lab.py',
               'lab/test_contract.py', 'lab/image/Dockerfile', 'vendor/artifacts.json', 'vendor/arm64/xray', 'vendor/amd64/xray')]
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    (out / 'input-sha256.json').write_text(json.dumps(before, indent=2) + '\n')
    validations = []
    for arch in ('arm64', 'amd64'):
        for config in ('server.loopback.json', 'client-macbook.json', 'client-iphone.json'):
            command = ['docker', 'run', '--rm', '--network', 'none']
            command += bind(ROOT / 'vendor' / arch / 'xray', '/xray')
            command += bind(ROOT / 'staging/fornex' / config, '/config.json')
            command += [IMAGE, '/xray', 'run', '-test', '-config', '/config.json']
            result = run(command)
            validations.append(dict(arch=arch, config=config, exit_code=result.returncode,
                                    output=result.stdout + result.stderr))
            print(f'Config {arch}/{config}: exit {result.returncode}', flush=True)
    (out / 'config-validation.json').write_text(json.dumps(validations, indent=2) + '\n')
    meta = run(['docker', 'image', 'inspect', IMAGE, '--format', '{{json .}}'])
    (out / 'image.json').write_text(meta.stdout)
    if any(x['exit_code'] for x in validations):
        print('Config validation failed; live lab not started: ' + str(out), flush=True)
        return 1
    name = 'timeweb-reality-stage3-' + stamp.lower()
    command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--memory', '512m',
               '--cpus', '2', '--pids-limit', '256', '--cap-add', 'NET_ADMIN', '--cap-add', 'SYS_ADMIN',
               '--security-opt', 'seccomp=unconfined', '--tmpfs', '/run', '--tmpfs', '/work', '--tmpfs', '/tmp']
    command += bind(ROOT / 'vendor/arm64/xray', '/xray/xray')
    command += bind(ROOT / 'lab/input', '/input')
    command += bind(ROOT / 'lab/run_lab.py', '/scripts/run_lab.py')
    command += bind(out, '/out', False)
    command += [IMAGE, 'timeout', '150', '/opt/lab/.venv/bin/python', '-B', '/scripts/run_lab.py']
    (out / 'invocation.json').write_text(json.dumps(command, indent=2) + '\n')
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        with (out / 'runner.log').open('w') as log:
            for line in proc.stdout:
                print(line, end='', flush=True)
                log.write(line)
        code = proc.wait(timeout=5)
    finally:
        # Only the exact per-run container is eligible for cleanup.
        run(['docker', 'rm', '-f', name], timeout=10)
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    (out / 'input-integrity.json').write_text(json.dumps({'unchanged': before == after}) + '\n')
    if before != after:
        print('Input drift: reject run', flush=True)
        code = 1
    print('Evidence: ' + str(out), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
