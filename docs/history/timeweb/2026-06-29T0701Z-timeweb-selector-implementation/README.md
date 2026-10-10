---
type: backup
system: timeweb
created: 2026-06-29T07:01Z
purpose: post-implementation checkpoint for TimeWeb Fornex/Cenuta selector
contains_secrets: false
---

# TimeWeb selector implementation checkpoint 2026-06-29T07:01Z

Post-implementation sanitized checkpoint for TimeWeb `wg-clients` selector and `wg-up-cenuta`.

Root-only artifacts on TimeWeb:

- Pre-change full backup: `/root/timeweb-pre-selector-backup-20260629T0649Z`.
- Post-change `/opt/wg-router` backup: `/opt/wg-router/backups/20260629T070316Z`.
- Client exports: `/root/wg-client-exports/client-1-fornex.conf`, `/root/wg-client-exports/client-2-cenuta.conf`.

Implemented:

- Docker published UDP `51850` for `wg-clients`.
- `wg-up-cenuta` to Cenuta `89.252.153.129:51840`.
- `wg-clients` on `10.50.50.1/24` with `client-1` `10.50.50.11/32` and `client-2` `10.50.50.12/32`.
- Policy routing: `client-1` -> table `100`/Fornex, `client-2` -> table `200`/Cenuta.
- IPv6 forwarding remains disabled and client configs do not include `::/0`.

Evidence:

- `runtime_verification.txt` - service, routes, rules, handshakes and metadata.
- `e2e_netns_tests.txt` - temporary namespace WireGuard client tests proving egress and IPv6 behavior.
- `configs_sanitized.txt` - configs and command file with secrets redacted.
- `file_metadata.txt` - file permissions and artifact locations.

No private keys, preshared keys, QR codes, or full secret client configs are stored here intentionally.
