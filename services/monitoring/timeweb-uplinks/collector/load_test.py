"""Accelerated 30-day synthetic history; not a 30-day production baseline."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import statistics
import tempfile
import time

from uplink_monitor.collector import POLICIES, SOURCES, ingest_batch
from uplink_monitor.storage import Store, UPSTREAMS, report, connect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--days', type=int, default=30, choices=range(1,31))
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    started, cpu = time.monotonic(), time.process_time()
    with tempfile.TemporaryDirectory(prefix='uplink-synthetic-', dir='/tmp') as tmp:
        store = Store(Path(tmp)/'history.sqlite')
        base = 86400
        counts = {up:dict(failed=0, unknown=0) for up in UPSTREAMS}
        payload = dict(started_unix=0, finished_unix=0, generation=1, path_verified=True,
                       upstreams={up:dict(probes={}) for up in UPSTREAMS})
        targets = dict(resolved_unix=0, expires_unix=0, targets={
            name:dict(host=p['host'], url=p['url'], ips=['1.1.1.1']) for name,p in POLICIES.items()})
        for index in range(args.days*86400//120):
            slot = base + index*120
            payload.update(started_unix=slot, finished_unix=slot+1)
            targets.update(resolved_unix=slot, expires_unix=slot+60)
            for up in UPSTREAMS:
                failed = index%113 < 5 if up=='cenuta' else index%491<4
                missing = index%199==0
                counts[up]['failed'] += failed and not missing
                counts[up]['unknown'] += missing
                for name,p in POLICIES.items():
                    payload['upstreams'][up]['probes'][name] = dict(returncode=2 if missing else 0,
                        output='REFUSED path_invalid' if missing else (
                        f'http={0 if failed else p["expected_http"][0]} local={SOURCES[up]} remote=1.1.1.1 seconds=0.2 connect=0 tls=0\n'
                        f'VALID_OBSERVATION curl_exit={28 if failed else 0} generation=1'))
            ingest_batch(store, payload, targets, 1, slot, run='synthetic', mono=index*120,
                         revision='load-v1', metadata=dict(slot=slot))
        queries = []
        for _ in range(50):
            before = time.monotonic()
            summaries = [report(store.path, up, base, base+args.days*86400) for up in UPSTREAMS]
            queries.append(time.monotonic()-before)
        for summary in summaries:
            expected = counts[summary['upstream']]
            assert summary['failed_seconds']==expected['failed']*120
            assert summary['unknown_seconds']==expected['unknown']*120
        with connect(store.path) as db:
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            rows = db.execute('SELECT count(*) FROM cycles').fetchone()[0]
            aggregates = db.execute('SELECT count(*) FROM daily').fetchone()[0]
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        assert rows == args.days*1440 and aggregates == args.days*2 and integrity=='ok'
        # RSS units differ on macOS vs Linux.
        import sys
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform=='darwin' else 1024)
        result = dict(kind='accelerated_synthetic_not_production', simulated_days=args.days,
            cycles=args.days*720, channel_rows=rows, daily_rows=aggregates,
            elapsed_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu,
            rss_mib=rss, database_bytes=store.path.stat().st_size,
            summary_pair_p95_seconds=sorted(queries)[int(len(queries)*.95)-1],
            integrity=integrity, summaries=summaries,
            limitations='Mac process only; excludes Linux helper children, kernel and Prometheus; no production CPU/RSS acceptance.')
        result['amortized_cpu_percent_one_core'] = result['cpu_seconds']/(args.days*86400)*100
        result['local_budget_pass'] = rss<96 and result['database_bytes']<1024**3 and result['summary_pair_p95_seconds']<.7
        (out/'load-report.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
        if not result['local_budget_pass']:
            raise SystemExit('local load budget failed')


if __name__ == '__main__':
    main()
