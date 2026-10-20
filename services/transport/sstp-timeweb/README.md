# Nakhimova - TimeWeb: isolated SSTP transport

Release: **1.1.1** (installed and transport-qualified). Owner: sstp-tw-v1. Installation status and acceptance are
recorded separately in the dated operations report, not inferred from this source.

## Current Qualification

The current installation uses the authorized additional address
**91.222.238.208:443/TCP**, retaining namespace loopback backend TCP5444.
Xray remains bound to 94.241.171.65:443. Deployment followed the approved
[maintenance plan](../../../docs/tasks/PLAN-timeweb-maintenance-newip-sstp.md),
fresh backups/recovery checks and the user's provider-console login. OS updates
and two approved reboots preserved the old VPN configuration, keys, container
ID and image. Both public addresses and the new transport recovered automatically.
Production routing and automatic failover remain disabled.
Qualification: strict 904.9-second bidirectional DF1400 window, 26 successful
samples, unchanged server/proxy processes and PPP ifindex; 512 KiB SFTP in each
direction, bad password/untrusted CA rejection and three reconnects passed.

See the [current report](../../../docs/history/2026-10-20-timeweb-maintenance-sstp-newip.md).

### Earlier Candidate

Earlier on 20 October 2026: **staged and disabled, not accepted for permanent operation**.
Basic TLS/authentication, bidirectional DF1400, application transfer and reconnect
tests passed. The strict ten-minute soak failed a final ICMP sample. TimeWeb had
severe CPU/memory pressure and about 9000 threads in the existing WG container's
shim. Old-service recovery checks were also intermittent or timed out.

Only the new transport was stopped; its namespace/listener were removed and its
autostart is disabled. The router and shared controller baseline were restored
exactly, including removal of the newly imported CA by fingerprint. The server
files and private PKI are preserved as a disabled candidate. No existing WG or
Xray service was restarted or reconfigured.

See [qualification and backups](../../../docs/history/2026-10-20-sstp-timeweb-candidate.md).
Do not activate this candidate by replaying the old one-shot helpers. Further
host maintenance and a fresh deployment/acceptance window require authorization.

## Scope

Independent RouterOS SSTP client, TimeWeb **91.222.238.208:443/TCP**, TLS 1.2 with a dedicated
CA and server-address verification, MSCHAPv2 with an independent random secret.
Client address 10.60.65.2, server 10.60.65.1, MTU/MRU 1400.

This is a parallel transport, not a new default route or automatic failover.
It does not select devices, change the existing Direct SSTP between sites,
or replace WireGuard. Installing this transport does not require an Xray restart;
the separately approved OS maintenance did restart existing services.

## Isolation

- sstp-timeweb-proxy.socket targets only 91.222.238.208:443. Its IP allowlist
  contains the reviewed Nakhimova public source and the TimeWeb self-test source.
- Socket activation passes the public listening descriptor to
  systemd-socket-proxyd in the separate sstp-timeweb network namespace.
- accel-ppp listens on namespace loopback only. Its PPP interface sstptw0
  and probe service also live inside that namespace.
- No root-namespace veth, route, NAT or firewall update is needed. Namespace
  forwarding is disabled and its forward chain drops all traffic.
- Router guards allow only peer ICMP/SSH test traffic and deny LAN transit on
  this new interface. Preserve existing Direct device rules at the head of
  each chain; ignore dynamic FastTrack placeholders when choosing anchors.
- Server-certificate verification plus PPP authentication is **not mutual TLS**:
  this accel-ppp implementation does not require a client certificate.

The fixed public-source allowlist deliberately requires review if Nakhimova's
public IP changes. TLS is not a guarantee against protocol-specific filtering.
SSTP carries TCP over TCP and can degrade under loss compared with WireGuard.

## Files

policy.py generates the narrowly scoped RouterOS policy, server config and
systemd units. namespace.py owns only the named namespace. probe.py serves a
fixed test payload only inside it. build.sh is for an off-host disposable
amd64 builder; do not install build dependencies on the production VPS.

The build pins accel-ppp commit
b8a3c54aa34434312aa0053686ec37a133fb54e6 and Ubuntu 24.04 container digest
sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac.
Its private artifact includes the matching OpenSSL/PCRE runtime libraries.

Private local configuration: .local/config/sstp-timeweb/. The encrypted CA
key stays offline. Only the server certificate/key and PPP secret reach TimeWeb.
Passwords, CA passphrase, bundles, certificates and audit exports belong in the
canonical private store, never in Git.

## Deployment Gate

Deployment is a reviewed changeset, not a blind replay of commands:

1. Verify pinned host/router identities, current policy contracts and fresh backups.
2. Refuse occupied names, address ranges or port. Preserve protected pre-state.
3. Validate units/config, install only the new paths; inspect own service logs.
4. Use RouterOS Safe Mode, create the disabled interface before referencing it
   in rules, compare exact outside-scope exports, then adopt only reviewed
   additive objects into the Direct controller baseline under its shared lock.
5. Require bidirectional DF/MTU, pinned SSH identity and useful application data,
   negative authentication/certificate tests, reconnects and a bounded soak.
6. Enable only the new units after acceptance; confirm unchanged old identities,
   contracts, routing selections, profile hashes, monitoring and post backups.

RouterOS CA import is not covered by ordinary export/Safe Mode rollback.
Track its fingerprint separately and remove only the new certificate on rollback.
Read the calculated fingerprint with certificate get; print as-value omits it.
RouterOS ping scripts print a table before the numeric return; validate the
last return line, not equality against the whole command output.
An empty iproute2 namespace inventory may be blank stdout rather than JSON [].
The parser accepts that case and rejects malformed inventories.
With max-sessions=1 an extra generic TLS connection is intentionally closed
while the authenticated peer is active; do not use that as an outage probe.

## Rollback

Disable only sstp-timeweb on Nakhimova, remove its exact owned rules/profile
and the recorded CA fingerprint after checking that no other object uses it.
Stop/disable only the five sstp-timeweb-* units, stop namespace processes
first, then remove that namespace and only its owned files.
If retiring the added public address, remove only its reviewed netplan overlay
and secondary address after stopping its listener; keep original DHCP/defaults.
Re-adopt the reviewed original Direct baseline after exact outside-scope proof.
Do not flush root firewall/routes, restore an old full-router backup, reboot,
or restart WireGuard, Xray or the existing Docker container.

## Primary Sources

- [MikroTik SSTP](https://help.mikrotik.com/docs/spaces/ROS/pages/2031645/SSTP)
- [accel-ppp source](https://github.com/accel-ppp/accel-ppp/tree/b8a3c54aa34434312aa0053686ec37a133fb54e6)
- [systemd socket namespaces](https://www.freedesktop.org/software/systemd/man/latest/systemd.socket)
- [systemd-socket-proxyd](https://www.freedesktop.org/software/systemd/man/latest/systemd-socket-proxyd.html)
