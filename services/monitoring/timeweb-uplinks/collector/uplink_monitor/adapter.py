"""Fixed candidate batch protocol. No shell strings, remote API or route edits."""
import json
from pathlib import Path
import re
import time

from .collector import POLICIES, SOURCES
from .model import parse_helper
from .runtime import atomic_json, digest, private_file
from .scheduler import run_bounded
from .targets import Refused


class BatchAdapter:
    def __init__(self, config, state_dir, *, runner=run_bounded, clock=time.time):
        self.config, self.state = config, Path(state_dir)
        self.runner, self.clock = runner, clock

    def __call__(self, targets, budget):
        if not self.config.get('allow_snapshot_scope', False):
            raise Refused('generation_coverage_not_accepted')
        helper = private_file(self.config['helper'])
        if helper.name != 'guardctl-batch.sh':
            raise Refused('fixed_helper_required')
        if set(self.config['helper_sha256']) != {'guardctl-batch.sh', 'batch_probe.sh'}:
            raise Refused('helper_inventory')
        private_file(self.config['manifest'])
        for name, expected in self.config['helper_sha256'].items():
            if not re.fullmatch(r'[a-z_-]+\.sh', name):
                raise Refused('helper_inventory')
            path = private_file(helper.parent/name)
            if digest(path) != expected:
                raise Refused('helper_revision_changed')
        revision = digest(self.config['manifest'])
        wire = dict(resolved_unix=targets['resolved_unix'], expires_unix=targets['expires_unix'],
                    cache_generation=targets['generation'], targets={
            name: dict(host=p['host'], url=p['url'], ip=p['ips'][0], port=443)
            for name, p in targets['targets'].items()})
        path = self.state/'batch-targets.json'
        atomic_json(path, wire)
        cache_hash = digest(path)
        result = self.runner(['/usr/bin/bash', str(helper), self.config['manifest'],
                              'batch', str(path)], timeout=min(budget, 43))
        if result.reason != 'ok':
            refused = re.search(r'^REFUSED ([a-z_]{1,64})$', result.stdout, re.M)
            if refused:
                raise Refused('helper_' + refused[1])
            raise Refused('batch_' + result.reason)
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise Refused('batch_invalid_json') from exc
        if not isinstance(value, dict):
            raise Refused('invalid_batch_protocol')
        if value.get('version') != 1 or value.get('path_verified') is not True:
            raise Refused('invalid_batch_protocol')
        if value.get('validity_scope') != 'rtnl_and_snapshots':
            raise Refused('unknown_generation_scope')
        if not self.config.get('allow_snapshot_scope', False):
            raise Refused('generation_coverage_not_accepted')
        if value.get('cache_sha256') != cache_hash or digest(path) != cache_hash:
            raise Refused('cache_revision_changed')
        if value.get('manifest_sha256') != revision or digest(self.config['manifest']) != revision:
            raise Refused('manifest_revision_changed')
        for name, expected in self.config['helper_sha256'].items():
            if digest(helper.parent/name) != expected:
                raise Refused('helper_revision_changed')
        return decode_batch(value, targets)


def decode_batch(value, targets):
    generation = value['generation']
    if type(generation) is not int or generation < 1:
        raise Refused('invalid_guard_generation')
    expected = {(up, name) for up in (*SOURCES, 'direct') for name in POLICIES}
    records = value['records']
    if len(records) != 6 or {(r['upstream'], r['target']) for r in records} != expected:
        raise Refused('incomplete_or_duplicate_batch')
    upstreams = {up:dict(probes={}, signals=value.get('diagnostics', {}).get(up, {}).copy()) for up in SOURCES}
    controls = []
    for record in records:
        up, name = record['upstream'], record['target']
        if type(record['curl_exit']) is not int or not 0 <= record['curl_exit'] <= 255:
            raise Refused('invalid_curl_exit')
        raw = record['output']
        if not isinstance(raw, str) or len(raw)>4096 or 'VALID_OBSERVATION' in raw:
            raise Refused('invalid_record')
        output = raw + f'\nVALID_OBSERVATION curl_exit={record["curl_exit"]} generation={generation}\n'
        if up == 'direct':
            local = re.search(r'local=([^\s]+)', raw)
            p = parse_helper(output, returncode=0, generation=generation,
                source=local[1] if local else '', pinned_ip=targets['targets'][name]['ips'][0],
                expected_http=POLICIES[name]['expected_http'], target=name, family=POLICIES[name]['family'])
            controls.append(p)
        else:
            upstreams[up]['probes'][name] = dict(returncode=0, output=output)
    if len(controls)==2 and all(p.valid for p in controls):
        for up in upstreams:
            upstreams[up]['signals']['controls_healthy'] = dict(
                value=all(p.success for p in controls), observed_unix=value['finished_unix'])
    return {**value, 'upstreams':upstreams}
