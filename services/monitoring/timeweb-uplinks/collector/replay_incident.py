"""Replay recorded observations; synthetic time slots are NOT outage statistics."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re

from uplink_monitor.collector import POLICIES, SOURCES
from uplink_monitor.exporter import metrics
from uplink_monitor.model import Assessment, Probe, assess, parse_helper
from uplink_monitor.storage import Store, current, incidents, report
from uplink_monitor.timing import LEGACY_TIMING

ROOT = Path(__file__).resolve().parents[1]
FAILED = Path(__file__).resolve().parent/'tests/fixtures/incident-failed.json'
RECOVERED = Path(__file__).resolve().parent/'tests/fixtures/incident-recovered.json'


def failed_observations():
    record=json.loads(FAILED.read_text())
    text=record['stdout']
    if record['returncode'] or text.count('VALID generation=5')!=2 or 'PROBE_WAN_DIRECT_COUNT=0' not in text:
        raise ValueError('historical_proof_missing')
    result={up:[] for up in SOURCES}
    pattern=r'^PROBE upstream=(\w+) target=(\w+)\n(.*?)(?=^PROBE |^CAPTURE_END)'
    for up,name,raw in re.findall(pattern,text,re.M|re.S):
        if name not in POLICIES:
            continue
        result[up].append(parse_helper(raw,returncode=0,generation=5,source=SOURCES[up],
            pinned_ip='172.217.23.227' if name=='gstatic' else '104.16.123.96',
            expected_http=POLICIES[name]['expected_http'],target=name,family=POLICIES[name]['family']))
    if any(len(p)!=2 for p in result.values()):
        raise ValueError('historical_probe_inventory')
    return result


def replay(destination):
    os.umask(0o077)
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    failed=failed_observations()
    recovered=json.loads(RECOVERED.read_text())
    healthy={up:[Probe(**p) for p in recovered[up]['probes']] for up in SOURCES}
    store=Store(destination/'synthetic-replay.sqlite', timing=LEGACY_TIMING)
    timeline=[]
    for slot in range(0,80,10):
        for up in SOURCES:
            probes=failed[up] if slot<30 else healthy[up]
            assessment=assess(probes,path_verified=True)
            if slot==50:
                assessment=Assessment('unknown','targets_expired')
                probes=[]
            store.ingest(up,slot,'synthetic-replay','5',assessment,mono=slot,
                         revision='replay-v1',probes=probes)
        timeline.append(dict(synthetic_slot=slot,channels=current(store.path,slot)))
    summary=dict(
        warning='Synthetic timeline: real one-shot observations repeated to test thresholds. NOT real outage duration/count.',
        sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (FAILED,RECOVERED)],
        actual_failure={up:asdict(assess(p,path_verified=True)) for up,p in failed.items()},
        actual_recovery={up:asdict(assess(p,path_verified=True)) for up,p in healthy.items()},
        synthetic_timeline=timeline,
        synthetic_summary=report(store.path,'cenuta',0,80),
        synthetic_incidents=incidents(store.path,'cenuta',0,80),
        stale_snapshot=current(store.path,100))
    (destination/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
    (destination/'metrics-at-synthetic-70.prom').write_text(metrics(current(store.path,70)))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=replay(args.output)
    print(result['warning'])
    for key in ('actual_failure','actual_recovery','synthetic_summary'):
        print(key,json.dumps(result[key]))
