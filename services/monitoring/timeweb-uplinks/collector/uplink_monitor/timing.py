"""Timing policy shared by scheduler, collector and persisted history."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Timing:
    interval: int = 120
    deadline: int = 45
    stale_after: int = 180

    def __post_init__(self):
        if any(type(v) is not int for v in (self.interval, self.deadline, self.stale_after)):
            raise ValueError('invalid_timing')
        if not 0 < self.deadline < self.interval or self.stale_after < self.interval + self.deadline:
            raise ValueError('invalid_timing')


DEFAULT_TIMING = Timing()
LEGACY_TIMING = Timing(interval=10, deadline=8, stale_after=25)
