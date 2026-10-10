---
name: create-timeweb-vpn-client
description: Audit and plan TimeWeb WG, REALITY/SOCKS/FLEX and AWG client changes. Use for device/profile lifecycle and routing changes. Require scoped deployment, backup and separate BTH/monitoring/runtime-policy gates; retired WG writers must not run.
---

# VPN Client Maintenance

## Read First

From the repository root read [architecture](../../../docs/architecture/overview.md),
[configuration](../../../docs/registry/configuration.md),
[tunnels](../../../docs/registry/tunnels.md),
[access](../../../docs/operations/access.md),
[agent workflow](../../../docs/operations/agent-workflow.md) and
[backup/storage](../../../docs/operations/storage-and-transfer.md).
For AWG read [operations](../../../docs/operations/Fornex_AWG31_Operations.md).
Paths in commands are relative to the repository root, not to this skill folder.

## Safety Gate

The old WG add/delete/regenerate/up/apply-ru-bth/backup writer is retired.
Do not run stage/migration CLIs against a later generation, append selector TSV
directly, restore the removed container recreate fallback or re-sign unknown drift.
This skill is a changeset procedure, not an implemented transactional WG writer.

Run fresh schema-3 backups using `.venv/bin/python -B
services/transport/timeweb-reality/run_backup.py all`. Require VERIFIED and
current topology/contract checks. The preserved legacy
`maintenance_preflight.py --check` fails closed on old baseline drift; it is
not equivalent to the current live runtime-policy check. Never auto-refresh a
contract to clear its failure. Historical checkpoints are evidence only.
No credential/UUID/private-key/PSK/QR material may enter public files or chat.

## Procedure

1. Identify owner, device, transport and gateway separately. Never revoke by
   device name alone; WG, Xray and AWG may coexist.
2. Verify live namespace, routes, identities, deployed hashes and approved
   generation. Take a fresh verified backup. Specify exact files/rules,
   contract impact, rollback and device acceptance tests.
3. Implement/test a current guarded writer if none exists. No manual RPDB edit
   or retired stage tool as a workaround. Obtain scoped change approval.
4. Deploy only reviewed changes; compare persistent/runtime/master and
   unaffected identities. Never general route/firewall flush or Docker recreate.
5. Publish only the approved profile into `.local/clients`, mode 600. Update
   `.local/secrets.json` and [profile catalog](../../../config/inventory/clients.json)
   together, retaining provenance and SHA-256. Leave other identities unchanged.
6. Update [observation inventory](../../../config/inventory/observations.json),
   fleet/controller config, registry and cardinality tests. Render dashboard
   mappings using `services/monitoring/vpn-connectivity/grafana/dashboard_source/build_device_dashboards.py`.
7. Review BTH full RPDB contract and monitoring manifest separately. Update
   only exact approved diff with rollback, state generation and pinned helper
   hashes. One contract does not update the other. Record verified no-change
   evidence where unaffected; never sign unknown drift.
8. Coordinate exact console `ReadWritePaths` and tmpfiles lock/state/audit paths.
   The agent performs daemon-reload and necessary targeted restarts. Check
   controllers inside the running console mount namespace and HTTP `/state`.
   Root SSH success is not proof that the console sandbox can access the files.
9. After an approved topology/config/controller change and both contract gates,
   publish the reviewed runtime policy with `python3
   /opt/vpn-runtime-recovery/runtime_recovery.py publish`, then run `check`.
   A timer must never publish its own observed drift.
10. Require two fresh valid collector cycles for both upstreams and actual
    Prometheus/Grafana device coverage. Healthy scrape alone is insufficient.
    Test DNS, HTTPS, egress and the actual application on the device; issued,
    imported, connected and accepted are different states.
11. Take a new verified backup, write a sanitized dated log in `docs/history`
    and run `scripts/validate_repository.py` plus local tests. Failed partial
    changes require exact inspection/rollback, not a blind retry.

The agent owns routine synchronization/deploy/restart/read-back steps; do not
leave them to the user. Deleting a client file does not revoke a live peer.
