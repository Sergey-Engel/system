"""Transactional local mirror. Cursor and rows are committed together."""
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .storage import UPSTREAMS


def packed(value):
    return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))


class Cache:
    def __init__(self,path):
        self.path=Path(path)
        if 'Dropbox' in self.path.resolve().parts:
            raise ValueError('live_database_in_sync_directory_forbidden')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.db() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sources(origin TEXT PRIMARY KEY,cursor INTEGER,
                  head INTEGER,refreshed REAL,metadata TEXT,ready INTEGER,earliest INTEGER);
                CREATE TABLE IF NOT EXISTS samples(origin TEXT,upstream TEXT,slot INTEGER,body TEXT,
                  PRIMARY KEY(origin,upstream,slot));
                CREATE TABLE IF NOT EXISTS status(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS missing(origin TEXT,started INTEGER,ended INTEGER,
                  PRIMARY KEY(origin,started,ended));''')
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=1)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def cursor(self,origin):
        with self.db() as db:
            row=db.execute('SELECT cursor FROM sources WHERE origin=?',(origin,)).fetchone()
            return row[0] if row else -1

    def apply(self,page,now):
        if not math.isfinite(now):
            raise ValueError('invalid_clock')
        origin=page['database_id']; uuid.UUID(origin)
        after,nxt,head=page['after'],page['next'],page['head']
        if page['version']!=1 or page['interval']!=120 or not all(type(v) is int and v>=-1 for v in (after,nxt,head)):
            raise ValueError('invalid_page')
        if not after<=nxt<=head or len(page['rows'])>200 or not math.isfinite(page['server_time']):
            raise ValueError('invalid_page')
        pairs={}
        for r in page['rows']:
            if r['upstream'] not in UPSTREAMS or r['state'] not in ('UP','DOWN','UNKNOWN','DEGRADED'):
                raise ValueError('invalid_row')
            slot=r['slot']
            if not isinstance(slot,(int,float)) or not math.isfinite(slot) or slot%120 or not after<slot<=nxt:
                raise ValueError('invalid_slot')
            if not slot<=r['observed']<=slot+45 or len(packed(r))>20000:
                raise ValueError('invalid_observation')
            if not isinstance(json.loads(r['probes']),list):
                raise ValueError('invalid_probes')
            pairs.setdefault(slot,[]).append(r)
        for pair in pairs.values():
            if len(pair)!=2 or {r['upstream'] for r in pair}!=set(UPSTREAMS):
                raise ValueError('partial_batch')
            if len({(r['run'],r['generation'],r['revision']) for r in pair})!=1:
                raise ValueError('mixed_batch')
        if (pairs and max(pairs)!=nxt) or (not pairs and nxt!=after):
            raise ValueError('cursor_without_rows')
        meta=page['metadata']
        if (nxt==head)!=(meta is not None):
            raise ValueError('missing_snapshot')
        if meta is not None:
            if set(meta)!= {'channels','incidents','gaps'} or len(packed(meta))>500000:
                raise ValueError('invalid_metadata')
            channels=meta['channels']
            if head!=-1 and (len(channels)!=2 or {r['upstream'] for r in channels}!=set(UPSTREAMS)
                            or any(r['slot']!=head for r in channels)):
                raise ValueError('mixed_metadata_generation')
            for r in channels:
                json.loads(r['machine']); json.loads(r['assessment'])
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT * FROM sources WHERE origin=?',(origin,)).fetchone()
            cursor=previous['cursor'] if previous else -1
            if after>cursor or head<cursor or (previous and (head<previous['head'] or now<previous['refreshed'])):
                raise ValueError('cursor_or_clock_regression')
            for r in page['rows']:
                body=packed(r)
                old=db.execute('SELECT body FROM samples WHERE origin=? AND upstream=? AND slot=?',
                               (origin,r['upstream'],r['slot'])).fetchone()
                if old and old[0]!=body:
                    raise ValueError('immutable_record_changed')
                db.execute('INSERT OR IGNORE INTO samples VALUES (?,?,?,?)',(origin,r['upstream'],r['slot'],body))
            earliest=page['earliest']
            if cursor>=0 and earliest is not None and earliest>cursor+120:
                db.execute('INSERT OR IGNORE INTO missing VALUES (?,?,?)',(origin,cursor+120,earliest))
            db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?) ON CONFLICT(origin) DO UPDATE SET '
                'cursor=max(cursor,excluded.cursor),head=excluded.head,refreshed=excluded.refreshed,'
                'metadata=excluded.metadata,ready=excluded.ready,earliest=excluded.earliest',
                (origin,nxt,head,now if meta is not None else (previous['refreshed'] if previous else 0),
                 packed(meta) if meta is not None else (previous['metadata'] if previous else '{}'),
                 int(page['source_ready'] is True),earliest))
            db.execute('INSERT OR REPLACE INTO status VALUES (?,?)',('active',origin))
            if meta is not None:
                db.execute('INSERT OR REPLACE INTO status VALUES (?,?)',('error',''))
            db.execute('DELETE FROM samples WHERE slot<?',(now-7*86400,))

    def error(self,code):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO status VALUES (?,?)',('error',code))

    def snapshot(self,now):
        with self.db() as db:
            active=db.execute("SELECT value FROM status WHERE key='active'").fetchone()
            source=db.execute('SELECT * FROM sources WHERE origin=?',(active[0],)).fetchone() if active else None
            error=db.execute("SELECT value FROM status WHERE key='error'").fetchone()
            missing=[dict(r) for r in db.execute('SELECT * FROM missing ORDER BY started DESC LIMIT 100')]
        source=dict(source) if source else dict(origin=None,cursor=-1,head=-1,refreshed=0,ready=0,metadata='{}')
        meta=json.loads(source.pop('metadata'))
        synced=not (error and error[0]) and 0<=now-source['refreshed']<=75 and source['cursor']==source['head']
        current={up:dict(upstream=up,state=0,reason='no_data',age=None,handshake=None,signals='') for up in UPSTREAMS}
        for row in meta.get('channels',[]):
            age=now-row['observed']
            fresh=synced and source['ready'] and 0<=age<=180
            assessment=json.loads(row['assessment']); machine=json.loads(row['machine'])
            current[row['upstream']]=dict(upstream=row['upstream'],state={'UNKNOWN':0,'UP':1,'DEGRADED':2,'DOWN':3}[machine['state']] if fresh else 0,
                reason=assessment['reason'] if fresh else 'sync_or_source_stale',age=age,
                handshake=assessment.get('handshake_age') if fresh else None,
                signals=', '.join(assessment.get('signals',[])) if fresh else '')
        return dict(**source,synced=bool(synced),error=error[0] if error else '',current=list(current.values()),
                    incidents=meta.get('incidents',[]),gaps=meta.get('gaps',[]),missing=missing)

    def history(self,start,end,metric):
        if not all(math.isfinite(t) for t in (start,end)) or not 0<=start<end or end-start>7*86400:
            raise ValueError('invalid_range')
        if metric not in ('state','success','duration'):
            raise ValueError('invalid_metric')
        status=self.snapshot(time.time()); origin=status['origin']
        with self.db() as db:
            rows=db.execute('SELECT body FROM samples WHERE origin=? AND slot>=? AND slot<? ORDER BY slot',
                            (origin,int(start//120)*120,end)).fetchall()
        lookup={(r['upstream'],int(r['slot'])):r for r in (json.loads(r[0]) for r in rows)}
        data=[]
        for slot in range(int(start//120)*120,int(end)+1,120):
            if slot>end: break
            item={'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(slot))}
            for up in UPSTREAMS:
                row=lookup.get((up,slot))
                if metric=='state':
                    item[up]={'UNKNOWN':0,'UP':1,'DEGRADED':2,'DOWN':3}[row['state']] if row else None
                else:
                    probes={p['target']:p for p in json.loads(row['probes'])} if row else {}
                    for target in ('gstatic','cloudflare'):
                        p=probes.get(target,{})
                        value=(p.get('success') if metric=='success' else p.get('seconds')) if p.get('valid') else None
                        item[up+'_'+target]=int(value) if type(value) is bool else value
            data.append(item)
        return data
