"""Three failures confirm an episode; two available cycles confirm recovery."""
from dataclasses import dataclass, field


@dataclass
class Machine:
    state: str = 'UNKNOWN'
    failures: int = 0
    recoveries: int = 0
    healthy: int = 0
    outages: int = 0
    episode: dict | None = None

    def step(self, assessment, slot):
        events = []
        if assessment.kind == 'unknown':
            if self.episode:
                events.append(dict(self.episode, type='interrupted', ended=slot))
            self.episode = None
            self.failures = self.recoveries = self.healthy = 0
            self.state = 'UNKNOWN'
            return events
        if assessment.kind == 'failed':
            self.healthy = self.recoveries = 0
            self.failures += 1
            if self.episode is None:
                self.episode = dict(started=slot, confirmed=False, reason=assessment.reason,
                                    first_recovery=None, confirmed_at=None)
                events.append(dict(self.episode, type='opened'))
            self.episode['first_recovery'] = None
            if self.failures >= 3 and not self.episode['confirmed']:
                self.episode.update(confirmed=True, confirmed_at=slot)
                self.outages += 1
                events.append(dict(self.episode, type='confirmed'))
            self.state = 'DOWN' if self.episode['confirmed'] else 'DEGRADED'
            return events
        self.failures = 0
        self.healthy = self.healthy + 1 if assessment.kind == 'healthy' else 0
        if self.episode:
            self.recoveries += 1
            if self.episode['first_recovery'] is None:
                self.episode['first_recovery'] = slot
            if self.recoveries < 2:
                self.state = 'DOWN' if self.episode['confirmed'] else 'DEGRADED'
                return events
            events.append(dict(self.episode, type='closed', ended=self.episode['first_recovery']))
            self.episode = None
            self.recoveries = 0
        if assessment.kind == 'partial' or (self.state == 'DEGRADED' and self.healthy < 2):
            self.state = 'DEGRADED'
        else:
            self.state = 'UP'
        return events
