# Isolated Site-To-Site Pilot

This directory contains the pure, scoped plan builder, its refusal tests and
the deployed root-owned startup guard. It is not a general-purpose WG writer.
The approved one-shot deployment and rollback snapshots are private evidence;
do not rerun them against a new baseline or refresh an old recovery contract.

The separate multi-device console controller is a **local candidate, not deployed**
as of 2026-10-17. Nakhimova became unreachable before the new deployment
baseline could be captured. See the [runbook](../../../docs/operations/Site_to_Site_Console.md)
and [plan](../../../docs/tasks/PLAN-site-to-site-console.md); current routers
must not be treated as already supporting the candidate management access.
Access recovered later on October 17, but the candidate still requires fresh
bootstrap/deployment qualification and has not been installed.

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
  Local IPv4/HTTPS trial and a bounded, DNS-bypassed IPv4/HTTPS IPIP outage
  probe with a separate recovery follow-up are accepted; current mode is Local.
  The first recovery LAN ping 2/3 remains a warning, not a passed gate.
  Pure outage checks pin the IPIP object and exact active RIB route IDs; null
  is not coerced to false. Full WAN/hub outage, IPv6 negative acceptance,
  permanent Remote, reverse egress and application tests remain unaccepted.
- `managed.py`, `router.py`, `controller.py`, `timeweb-s2s`: persistent, locked
  device selection; strict SSH identities, exact owner/field/order checks,
  fresh DHCP binding, per-client mode controls, durable pending operations,
  offline removal and refusal of unknown drift. New selections do not alter
  shared transport, NAT/defaults or other client identities. The legacy preset
  requires a MAC flow qualification before this controller can be deployed.
- `test_managed.py`: fake-router multi-device and crash tests, including fresh
  lease IDs, partial make-static, failed guards, interrupted removal and rule
  movement across baseline anchors. These are not live router acceptance.
- `direct_trial.py` / `test_direct_trial.py`: isolated feasibility builders for
  separate-socket and shared-socket direct WG trials, strict owner cleanup,
  ICMP-only test addresses, test-subnet forward denial and Safe Mode ACK tests.
  Both live candidates were completely rolled back; neither qualified a stable
  direct path. This is not a deployed controller or a repeatable production
  writer. See the [trial receipt](../../../docs/history/2026-10-17-direct-tunnel-feasibility.md).
- `forward_trial.py` / `test_forward_trial.py`: separate Oct18 isolated
  responder/initiator candidate after the owner saved Deco UDP51972 forwarding
  and DHCP reservation. Initial authenticated packets passed, but seven later
  rounds failed both ways. Fully undone; not a permanent transport/controller.
  See the [forward trial receipt](../../../docs/history/2026-10-18-direct-deco-forward.md).
- `direct_diagnostics.py`, `direct_path_probe.py` and focused tests: separate
  temporary packet-boundary observers and same-key source-port rotation.
  Direct WG RX stopped while WAN TX continued; neutral UDP controls passed.
  All scopes undone, no TimeWeb changes. This localizes the external flow loss,
  not a specific DPI/NAT middlebox. See the
  [diagnostic receipt](../../../docs/history/2026-10-18-direct-path-diagnosis.md).
- `sstp_trial.py` / `test_sstp_trial.py`: isolated mutual-TLS SSTP builder and
  certificate/namespace/isolation tests. Oct19 direct TCP443->5443 passed HTTP,
  negative CA/reconnect and ordinary-interval ICMP; 200ms probes timed out.
  All trial objects/certificates removed, TimeWeb unchanged. Not a persistent
  writer or production qualification. See the
  [SSTP receipt](../../../docs/history/2026-10-19-sstp-direct-trial.md).
- `sstp_soak.py` / `test_sstp_soak.py`: read-only observation/acceptance logic
  for the separate thirty-minute trial. Fixed one-second probes, HTTP counter
  freshness, uptime/session continuity and latest Safe Mode prompt validation.
  The live soak and three reconnects/negative CA passed; exact cleanup restored
  both routers, TimeWeb unchanged. This is not persistent routing or a console
  deployment. See the [soak receipt](../../../docs/history/2026-10-19-sstp-direct-soak.md).

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
The [bounded IPIP outage receipt](../../../docs/history/2026-10-17-egress-fail-closed.md)
preserves the first recovery failure and distinguishes later HTTPS recovery
from autonomous failover or general leak protection acceptance.

## Permanent Direct SSTP

`sstp_direct.py` and `direct_access.py`/`direct_controller.py` implement the
independent persistent router path and local device selection. `direct_panel.py`
adds the Direct SSTP tab to the unchanged upstream VPN console through a local
loopback facade; `direct_panel_service.py` owns only two local LaunchAgents.
`direct_private.py` checkpoints approved controller state in the private store.
TimeWeb deployment files, transports and recovery contracts are unchanged.
Current operations and evidence: [runbook](../../../docs/operations/Direct_SSTP.md),
[qualification](../../../docs/history/2026-10-19-sstp-direct-permanent.md).

Controller release 2.0.0 adds the reverse Nakhimova-to-Fethiye direction over
the same bidirectional SSTP connection. `sstp_fethiye` has an isolated default
and blackhole; source SNAT is limited to public destinations. A shared lock
serializes both controllers, while client state, generations, revisions and
audit files remain direction-specific. Legacy forward endpoints are retained;
reverse uses `/s2s-reverse-state` and `/s2s-reverse-action`. The UI never polls
or switches real clients automatically. See the
[reverse acceptance boundary](../../../docs/history/2026-10-19-sstp-reverse-egress.md).

## Unified Device Routing (4.2.2)

Facade4.2.2 canonicalizes a warning-split RouterOS terse path/add pair before
strict comparison. No live baseline is accepted or refreshed. Rule properties,
missing rules and order remain protected; transport readiness is separate.

Facade4.2.1 hides the completed progress block20 seconds after a successful,
error-free read. A green Updated timestamp under Refresh uses the response's
checked_at, not the dismissal time. Failed reads/status errors remain visible
without green confirmation. A new read/site selection cancels the old dismissal;
neither this timer nor its completion starts a network request or changes routes.
Individual unavailable channels do not turn a successful read into a VPN-health
claim. Route action validation and recovery availability are unchanged.

Facade4.2.0 observes the five actual capture phases through an optional read-only
callback. A manual GET can carry a fresh 32-hex `X-Routing-Poll` header; its
final JSON then includes `poll_progress`. GET `/routing-progress/{id}` reads
only local memory without the controller lock or any SSH/network probe.
States: queued/running/complete/error; completed/total count finished phases,
not elapsed-time estimates or healthy tunnels. Errors freeze partial completion.
IDs are one-use, bounded to64 retained jobs and300 seconds after completion;
unknown IDs return404, duplicate IDs409, invalid IDs400, capacity overflow429.
The UI observes progress only during an explicit/initial/site-selection read,
and stops both observation and elapsed timers at completion or failure. It never
restarts a status read automatically. Read IDs, stages and errors cannot write
device modes, credentials or transport configuration. Older headerless GETs
and all POST validation/rollback contracts are unchanged.

Local facade4.1.1 coalesces overlapping same-site GETs only when their check
completed after request arrival. A later Refresh always starts a fresh check;
POSTs are independently validated and invalidate read results. Router policy
and Direct controller versions are unchanged. Failed reads retain existing
rows but disable writes; an initial failed read no longer says Checking.

`device_routing.py` is the single assignment authority; `routing_panel.py`
replaces both Direct lists when `routing_enabled=true`. Nakhimova first/default:
enabled permanent DHCP reservations, including offline; Standard, WG-Cenuta-RU,
WG-Fornex-RU, SSTP-Cenuta-RU, SSTP-Fornex-RU or Direct SSTP-RU via Fethiye.
Fethiye: authorized MikroTik Wi-Fi registrations
only, Standard or Direct SSTP-RU via Nakhimova. Names come only from exact-MAC inventory.
Mode selection requires an explicit Apply; no background Refresh or automatic route changes.

GET `/routing-state/{nakhimova,fethiye}`, POST `/routing-action` with CSRF,
site, device, mode and revision. Legacy Direct HTTP actions return 410; the old
controller action also refuses writes. `routing-state.json` journals intent
before the first write. Only reviewed exact host membership diffs can update
the strict baseline. Unknown result retains pending and permits explicit Standard
recovery or a proven manual rollback for the same MAC/IP/lease; never replay
writes or adopt neighboring drift. Undo restores exact prior memberships,
including disabled entries and comments. A stale binding invalidates Undo.
Direct state and policy controls remain reused under the same shared lock.
Existing WG Split exceptions/transports remain intact; the separately reviewed
TimeWeb split data plane supplies both SSTP modes. Writes to an SSTP mode require
a new HTTPS egress proof; partial readiness does not suppress the healthy exit.
All 36 Nakhimova mode transitions and interrupted operations have strict router
fixture coverage. Live acceptance used one offline permanent device, with both
SSTP assignments and Undo, restoring all original modes. Not browser acceptance.
See [current runbook](../../../docs/operations/Nakhimova_TimeWeb_SSTP_Split.md)
and [original UI receipt](../../../docs/history/2026-10-19-unified-device-routing.md).

RU release4.1 uses the source router's country IPv4 list for all five VPN
choices, including Direct on both sites. RU rules precede the old forced
Russian destination. Direct3.1 marks only non-RU, narrows its old source rule
to the DNS target and admits only scoped RU WAN returns before leak guards.
Legacy configs retain old specs until the explicit ru_bypass_enabled migration.
See [IP policy and limits](../../../docs/operations/Panel_RU_Direct.md).
