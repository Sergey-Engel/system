"""Pinned target cache. Resolver is separate from through-tunnel DNS probes."""
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit


class Refused(ValueError):
    pass


class Targets:
    def __init__(self, path, policies):
        self.path = Path(path)
        self.policies = policies
        self.digest = hashlib.sha256(json.dumps(policies, sort_keys=True).encode()).hexdigest()
        self.last_clock = None
        for policy in policies.values():
            url = urlsplit(policy['url'])
            if url.scheme != 'https' or url.hostname != policy['host'] or url.port not in (None, 443) or url.username or url.password or url.fragment:
                raise Refused('invalid_target_policy')

    def _clock(self, now):
        if not math.isfinite(now) or now < 0 or (self.last_clock is not None and now < self.last_clock):
            raise Refused('clock_regression')
        self.last_clock = now

    def get(self, now):
        self._clock(now)
        try:
            if self.path.stat().st_size > 65536:
                raise Refused('cache_size')
            value = json.loads(self.path.read_text())
            if value['policy_sha256'] != self.digest or not value['resolved_unix'] <= now < value['expires_unix']:
                raise Refused('targets_expired_or_changed')
            if set(value['targets']) != set(self.policies):
                raise Refused('target_inventory')
            for name, target in value['targets'].items():
                self._answer(target['ips'], target['ttl'])
                if target['host'] != self.policies[name]['host'] or target['url'] != self.policies[name]['url']:
                    raise Refused('target_policy_changed')
            ttl = min(t['ttl'] for t in value['targets'].values())
            resolved, expiry = value['resolved_unix'], value['expires_unix']
            if not all(math.isfinite(t) for t in (resolved, expiry)) or resolved < 0:
                raise Refused('invalid_cache_time')
            if not resolved < expiry <= resolved + min(ttl, 3600):
                raise Refused('invalid_cache_expiry')
            if type(value['generation']) is not int or value['generation'] < 1:
                raise Refused('invalid_cache_generation')
            return value
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise Refused('target_cache_unavailable') from exc

    @staticmethod
    def _answer(ips, ttl):
        if not ips or len(ips)>16 or not math.isfinite(ttl) or ttl <= 0:
            raise Refused('invalid_dns_answer')
        try:
            if any(not ipaddress.IPv4Address(ip).is_global for ip in ips):
                raise Refused('non_public_target')
        except ipaddress.AddressValueError as exc:
            raise Refused('invalid_ipv4') from exc

    def refresh(self, resolver, now):
        self._clock(now)
        targets = {}
        for name, policy in self.policies.items():
            ips, ttl = resolver(policy['host'])
            self._answer(ips, ttl)
            targets[name] = dict(policy, ips=sorted(set(ips)), ttl=min(float(ttl), 3600))
        revision = 1
        if self.path.exists():
            try:
                revision = int(json.loads(self.path.read_text())['generation'])+1
            except (ValueError, KeyError, TypeError):
                raise Refused('invalid_cache_generation')
        value = dict(policy_sha256=self.digest, generation=revision, resolved_unix=now,
                     expires_unix=now+min(t['ttl'] for t in targets.values()), targets=targets)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(value, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            dirfd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return value


def dns_resolver(host):
    """Optional dependency; never install it automatically or substitute fake TTLs."""
    try:
        import dns.resolver
    except ImportError as exc:
        raise Refused('dnspython_not_installed') from exc
    import time
    answer = dns.resolver.resolve(host, 'A', lifetime=2.0, search=False)
    return [r.address for r in answer], answer.expiration-time.time()
