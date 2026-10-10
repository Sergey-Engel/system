---
type: backup
system: timeweb
created: 2026-06-29T06:49Z
purpose: pre-selector baseline before TimeWeb Cenuta routing implementation
contains_secrets: false
---

# TimeWeb pre-selector baseline 2026-06-29T06:49Z

Sanitized checkpoint before implementing TimeWeb `wg-clients` selector and `wg-up-cenuta`.

Root-only full backup on TimeWeb: `/root/timeweb-pre-selector-backup-20260629T0649Z`.

Files:

- `system_network_runtime.txt` - host/container runtime, routes, ip rules, WireGuard state.
- `configs_sanitized.txt` - selected configs with `PrivateKey` and `PresharedKey` redacted.
- `file_metadata.txt` - file tree metadata and root-only backup path metadata.
- `SHA256SUMS` - integrity manifest.

No private keys, preshared keys, QR codes, or full secret client configs are stored here intentionally.
