"""Bounded immutable cycle pages, with a consistent final mutable-state snapshot."""
import json
import uuid
from .storage import connect, UPSTREAMS, read_timing


def export_page(path, after=-1, limit=100):
    if type(after) is not int or after < -1 or not 1 <= limit <= 100:
        raise ValueError('invalid_cursor')
    with connect(path, readonly=True) as db:
        db.execute('BEGIN')
        origin = db.execute("SELECT value FROM settings WHERE name='database_id'").fetchone()[0]
        uuid.UUID(origin)
        timing = read_timing(db)
        if timing.interval != 120:
            raise ValueError('unsupported_interval')
        first, head = db.execute('SELECT min(slot),max(slot) FROM cycles').fetchone()
        first, head = (None if first is None else int(first)), (-1 if head is None else int(head))
        if after > head:
            raise ValueError('cursor_ahead_of_database')
        slots = [r[0] for r in db.execute(
            'SELECT DISTINCT slot FROM cycles WHERE slot>? ORDER BY slot LIMIT ?', (after, limit))]
        rows, cursor, size = [], after, 0
        for slot in slots:
            pair = [dict(r) for r in db.execute('SELECT * FROM cycles WHERE slot=? ORDER BY upstream',(slot,))]
            if {r['upstream'] for r in pair} != set(UPSTREAMS) or len(pair)!=2:
                raise ValueError('partial_batch')
            if len({(r['run'],r['generation'],r['revision']) for r in pair})!=1:
                raise ValueError('mixed_batch')
            encoded = json.dumps(pair,allow_nan=False)
            if size+len(encoded.encode())>400_000:
                break
            rows.extend(pair); size+=len(encoded.encode()); cursor=int(slot)
        if slots and not rows:
            raise ValueError('batch_size_limit')
        metadata = None
        if cursor==head:
            metadata = {}
            for table in ('channels','incidents','gaps'):
                values=[dict(r) for r in db.execute(f'SELECT * FROM {table} LIMIT 6001')]
                if len(values)>6000:
                    raise ValueError('metadata_limit')
                metadata[table]=values
            if len(json.dumps(metadata,allow_nan=False).encode())>500_000:
                raise ValueError('metadata_size_limit')
        return dict(version=1,database_id=origin,after=after,next=cursor,head=head,
                    earliest=first,interval=120,rows=rows,metadata=metadata)
