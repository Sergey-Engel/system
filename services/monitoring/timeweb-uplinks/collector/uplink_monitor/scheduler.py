"""Bounded POSIX batch adapter; never shell-execute or queue catch-up cycles."""
from dataclasses import dataclass
import os
import math
import selectors
import signal
import subprocess
import time
from .timing import DEFAULT_TIMING


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    stdout: str
    reason: str
    duration: float


def run_bounded(argv, timeout=DEFAULT_TIMING.deadline, output_limit=65536):
    if not argv or not os.path.isabs(argv[0]) or not 0 < timeout <= DEFAULT_TIMING.deadline or not 0 < output_limit <= 65536:
        raise ValueError('invalid_command_budget')
    started = time.monotonic()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    except OSError:
        return CommandResult(None, '', 'spawn_error', time.monotonic()-started)
    chunks, size, reason = [], 0, 'ok'
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            remaining = timeout - (time.monotonic()-started)
            if remaining <= 0:
                reason = 'scheduler_deadline'
                break
            for key, _ in selector.select(remaining):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                size += len(chunk)
                if size > output_limit:
                    reason = 'output_limit'
                    break
                chunks.append(chunk)
            if reason != 'ok':
                break
        if reason == 'ok':
            try:
                proc.wait(timeout=max(0.001, timeout-(time.monotonic()-started)))
            except subprocess.TimeoutExpired:
                reason = 'scheduler_deadline'
    finally:
        selector.close()
        # Also terminate descendants which inherited the output pipe.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=1)
        proc.stdout.close()
    if reason == 'ok' and proc.returncode != 0:
        reason = 'batch_failed'
    return CommandResult(proc.returncode, b''.join(chunks).decode('utf-8', 'replace'),
                         reason, time.monotonic()-started)


class Scheduler:
    def __init__(self, started, wall_started=None, *, timing=DEFAULT_TIMING):
        self.interval = timing.interval
        if not math.isfinite(started) or started < 0:
            raise ValueError('invalid_clock')
        if wall_started is not None and (not math.isfinite(wall_started) or wall_started < 0):
            raise ValueError('invalid_clock')
        self.next_due = started + (0 if wall_started is None else (-wall_started) % self.interval)
        self.missed = 0
        self.last_wall = None

    def due(self, monotonic_now, wall_now):
        if not all(math.isfinite(t) and t >= 0 for t in (monotonic_now, wall_now)):
            raise ValueError('invalid_clock')
        if monotonic_now < self.next_due:
            return None
        skipped = int((monotonic_now-self.next_due)//self.interval)
        self.missed += skipped
        self.next_due += (skipped+1)*self.interval
        slot = int(wall_now//self.interval)*self.interval
        if self.last_wall is not None and slot <= self.last_wall:
            return {'slot':slot, 'reason':'clock_regression', 'missed':skipped}
        self.last_wall = slot
        return {'slot':slot, 'reason':'ok', 'missed':skipped}
