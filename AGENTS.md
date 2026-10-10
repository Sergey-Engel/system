# Agent Instructions

## Initialization

1. Determine OS, actual repository root, Git branch and dirty state.
2. Read [README](README.md), [Quick Guide](docs/quick-start.md),
   [architecture](docs/architecture/overview.md), [access](docs/operations/access.md),
   [configuration](docs/registry/configuration.md), [tunnels](docs/registry/tunnels.md).
3. Before any device/tunnel change, read the local
   [VPN maintenance skill](.agents/skills/create-timeweb-vpn-client/SKILL.md) and
   [agent workflow](docs/operations/agent-workflow.md).

## Storage And Safety

- Russian prose by default; CLI/code in English. All file links are relative.
- This repository is the public source tree. `.local/secrets.json` is the
  portable, private canonical store. `.local/clients`, `.local/config` and
  `.local/ssh` are materialized derivatives. Update the store together with
  approved master changes; never silently overwrite newer master files.
- Never print credentials, full configs, private keys, PSKs, UUID credentials,
  QR contents, or private backup output. Never stage `.local` or use `git add -f`.
- Live hosts are authoritative runtime evidence. Historical snapshots are
  dated evidence, not a current deployment baseline.
- Do not run retired WG mutators or old stage CLIs. Never auto-sign unknown
  BTH/monitoring/runtime-policy drift, flush routes/firewall, or recreate
  containers as a diagnostic shortcut.
- Do not mutate PostgreSQL. Preserve unrelated working changes.
- Original Dropbox/Vault folders are retained for user-owned removal.

## Mandatory Tunnel Completion Gate

For every create/update/delete/rename/regenerate/routing/device change:
update profile catalog, observation inventory, fleet and registry; review BTH
and monitoring contracts separately; coordinate exact console sandbox and
tmpfiles lock paths; deploy/restart only affected services. Verify controllers
inside the running console namespace and HTTP `/state`. After an approved
topology change, publish only the reviewed recovery policy and run its check.
Require two fresh valid collector cycles, Prometheus/Grafana evidence, unchanged
unaffected identities and a fresh verified backup. The agent owns routine
completion steps; do not leave them to the user. Handshake is not client acceptance.

## Local Verification

```sh
.venv/bin/python -B scripts/validate_repository.py
.venv/bin/python -B scripts/private_store.py --verify-only
.venv/bin/python -B -m pytest -q
git status --short
git add --dry-run .
```

Run server checks only through strict existing SSH identities. Record check
scope, timestamp, actual failure and rollback, not only a green summary.
