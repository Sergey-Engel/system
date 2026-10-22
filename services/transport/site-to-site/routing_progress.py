"""Bounded in-memory observations of existing read jobs; no network or writer."""
import re
import threading
import time

STAGES = (
    'Checking Direct SSTP',
    'Reading router configuration',
    'Validating router configuration',
    'Reading devices and assignments',
    'Checking route readiness',
)


class Poll:
    def __init__(self, site, clock):
        self.site, self.clock = site, clock
        self.lock = threading.RLock()
        self.created = clock()
        self.started = self.ended = None
        self.index = None
        self.completed = 0
        self.state = 'queued'

    def stage(self, index):
        with self.lock:
            if self.state in ('error', 'complete'):
                return
            if index is None:
                self.state, self.ended = 'error', self.clock()
                return
            expected = 0 if self.index is None else self.index + 1
            if type(index) is not int or index != expected or index >= len(STAGES):
                raise ValueError('invalid_poll_stage')
            if self.started is None:
                self.started = self.clock()
            self.state, self.index, self.completed = 'running', index, index

    def finish(self, success):
        with self.lock:
            if self.state == 'error':
                return
            self.ended = self.clock()
            if success:
                self.state, self.completed = 'complete', len(STAGES)
            else:
                self.state = 'error'

    def snapshot(self):
        with self.lock:
            end = self.clock() if self.ended is None else self.ended
            queue_end = end if self.started is None else self.started
            return dict(site=self.site, state=self.state, completed=self.completed, total=len(STAGES),
                stage=STAGES[self.index] if self.index is not None else None,
                elapsed_seconds=max(0, end-self.created), queue_seconds=max(0, queue_end-self.created))


class Polls:
    def __init__(self, clock=time.monotonic, capacity=64, retention=300):
        self.clock, self.capacity, self.retention = clock, capacity, retention
        self.lock, self.jobs = threading.Lock(), {}

    def prune(self):
        self.jobs = {key: job for key, job in self.jobs.items()
                     if job.ended is None or self.clock()-job.ended <= self.retention}

    def create(self, token, site):
        if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}', token) or site not in ('nakhimova', 'fethiye'):
            raise ValueError('invalid_poll_identity')
        with self.lock:
            self.prune()
            if token in self.jobs:
                raise FileExistsError('poll_identity_reused')
            if len(self.jobs) >= self.capacity:
                raise OverflowError('poll_capacity_reached')
            poll = self.jobs[token] = Poll(site, self.clock)
            return poll

    def get(self, token):
        with self.lock:
            self.prune()
            poll = self.jobs.get(token)
            return poll.snapshot() if poll is not None else None
