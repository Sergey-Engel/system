# Isolated Site-To-Site Pilot

This directory contains the pure, scoped plan builder, its refusal tests and
the deployed root-owned startup guard. It is not a general-purpose WG writer.
The approved one-shot deployment and rollback snapshots are private evidence;
do not rerun them against a new baseline or refresh an old recovery contract.

- `pilot.py`: empty-scope / exact-baseline checks; fixed ICMP-only policy and
  configuration rendering. Router rules use a separate input chain and a
  unique static anchor, never index 0 before a dynamic FastTrack dummy.
- `guard.py`: hashes the reviewed files and compares only its own nft table.
  Startup loads the owned table when absent; unknown drift fails closed.
- `test_pilot.py`: identity/trust, occupied scope, CIDR/port, continuations,
  dotted properties, defaults and deny-transit checks.
- `second_leg.py` / `test_second_leg.py`: exact first-pilot baseline,
  append-only Nakhimova peer, immutable existing identities, static anchor
  checks and ICMP-only second-leg policy. No LAN routes or transit yet.
- `lan.py` / `test_lan.py`: a separately reviewed IPv4 LAN-pair changeset,
  staged disabled routes/rules, exact subnet/identity checks, no NAT or default
  routes, and unchanged host-service isolation.
- `egress.py` / `test_egress.py`: scoped IPIP-over-WG transport, pinned ten-object
  mode switching and exact export refusal tests. The initial lease is validated
  dynamically and pinned statically before Remote. A bounded Local -> Remote ->
  Local IPv4/HTTPS trial is accepted; current mode is Local. Controlled outage,
  permanent Remote and reverse egress remain unaccepted.

RouterOS 7.19 `print as-value` can omit `disabled` flags. Missing is unknown,
not enabled: read the explicit `get <id> disabled` property and require a
validated boolean before activation. Never rerun add commands to repair a
read-back format mismatch; reconcile exact owned objects first.
`find` returns an array, not a scalar ID. Verify dynamic leases using explicit
typed `get` and select duplicate defconf comments together with their chain.
Read device-mode before selecting diagnostics: neither router currently
permits `/tool fetch`. Do not enable features to work around that restriction.
Escape the dollar anchor in a quoted RouterOS regex as `\$`. Scoped conntrack
selection is verified before mutation; no broad flush is an acceptable fallback.

Tests:

```sh
.venv/bin/python -B -m pytest -q services/transport/site-to-site
```

Runtime guard: `/etc/wireguard/s2s-pilot/guard.py check`. New WG startup
requires its guard unit and checks the manifest before wg-quick starts.
No global nft flush, existing container change or default/NAT route is used.

See the [approved changeset](../../../docs/architecture/Fethiye_TimeWeb_Pilot_Changeset.md)
and [dated checkpoint](../../../docs/history/2026-10-16-fethiye-timeweb-pilot.md).
The [second-leg changeset](../../../docs/architecture/Nakhimova_TimeWeb_Second_Leg_Changeset.md)
adds one peer without restarting the existing interface.
The [LAN-pair changeset](../../../docs/architecture/Site_to_Site_LAN_Changeset.md)
is a separate phase; client acceptance is tracked independently.
The [egress changeset](../../../docs/architecture/Site_to_Site_Egress_Changeset.md)
keeps client Local mode separate from transport and public Internet gates.
The [bounded trial receipt](../../../docs/history/2026-10-16-egress-trials.md)
records actual client HTTPS/IP results, Local restoration and remaining limits.
