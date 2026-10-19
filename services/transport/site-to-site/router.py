"""Pinned OpenSSH RouterOS adapter; credentials are never returned to callers."""
import json
from pathlib import Path
import re
import subprocess

import managed

CONFIG = Path("/etc/vpn-s2s/ssh_config")
RUNTIME = Path("/run/timeweb-s2s")
ERROR = re.compile(r"(?im)^(failure:|syntax error|bad command name|expected end|invalid value|Script Error|not enough permissions|no such item|input does not match|lease_identity_changed)")


class Router:
    def __init__(self, site, *, runner=subprocess.run, config=CONFIG, runtime=RUNTIME):
        if site not in managed.SITES:
            raise ValueError("unknown_site")
        self.site, self.runner = site, runner
        self.config, self.runtime = Path(config), Path(runtime)
        self.base = ["ssh", "-F", str(self.config), "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                     "-o", "ClearAllForwardings=yes", "-o", "ForwardAgent=no", "-o", "ConnectTimeout=8",
                     "-o", "ControlMaster=auto", "-o", "ControlPersist=10", "-o", "ControlPath=" + str(self.runtime / (site + ".sock")), site]

    def run(self, command):
        try:
            p = self.runner([*self.base, command], capture_output=True, text=True, timeout=25, check=False)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError("router_unavailable:" + self.site) from None
        if p.returncode or ERROR.search(p.stdout) or len(p.stdout) > 8_000_000:
            raise RuntimeError("router_command_failed:" + self.site)
        return p.stdout.strip()

    def json(self, expression):
        try:
            return json.loads(self.run(":put [:serialize to=json " + expression + "]"))
        except (ValueError, TypeError):
            raise RuntimeError("invalid_router_output:" + self.site) from None

    def mutate(self, command):
        if self.run(command):
            raise RuntimeError("unexpected_router_mutation_output:" + self.site)

    def rows(self, path):
        if path not in (*managed.PATHS, "/ip dhcp-server lease", "/ip dhcp-server", "/interface ipip", "/routing route"):
            raise ValueError("unsupported_read_path")
        result = self.json("[" + path + " print as-value]")
        if not isinstance(result, list) or any(not isinstance(r, dict) for r in result):
            raise RuntimeError("invalid_router_rows:" + self.site)
        return result

    def disabled(self, controls):
        expressions = [":put [:serialize to=json [" + p + " get " + managed.identity(r[".id"]) + " disabled]]" for p, r in controls]
        if not expressions:
            return
        try:
            values = [json.loads(line) for line in self.run("; ".join(expressions)).splitlines()]
        except ValueError:
            raise RuntimeError("invalid_router_flags:" + self.site) from None
        if len(values) != len(controls) or any(type(v) is not bool for v in values):
            raise RuntimeError("untyped_router_flags:" + self.site)
        for (_, row), value in zip(controls, values):
            row["disabled"] = value

    def snapshot(self):
        serial = self.run(":put [/system routerboard get serial-number]")
        if serial != managed.SITES[self.site]:
            raise RuntimeError("router_identity_mismatch:" + self.site)
        result = {path: self.rows(path) for path in managed.PATHS}
        targets = [(path, row) for path, rows in result.items() for row in rows
                   if row.get("comment", "").startswith((managed.OWNER + ":", "s2s-egress-20261016:"))]
        self.disabled(targets)
        result["export"] = self.run("/export terse")
        result["tunnels"] = self.rows("/interface ipip")
        for tunnel in result["tunnels"]:
            if tunnel.get("name") == "ipip-s2s-egress":
                for prop in ("running", "disabled"):
                    value = self.json("[/interface ipip get " + managed.identity(tunnel[".id"]) + " " + prop + "]")
                    if type(value) is not bool:
                        raise RuntimeError("untyped_tunnel_flag:" + self.site)
                    tunnel[prop] = value
        if self.site == "fethiye":
            result["leases"] = self.rows("/ip dhcp-server lease")
            result["servers"] = self.rows("/ip dhcp-server")
        return result
