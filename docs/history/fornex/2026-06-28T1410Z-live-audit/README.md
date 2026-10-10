---
type: backup-manifest
topic: mikrotik
system: fornex
status: active
created: 2026-06-28
backup_kind: sanitized-read-only
tags:
  - mikrotik
  - vpn
  - backup
  - fornex
---

## Назначение

Read-only backup текущего состояния Fornex VPS, снятый через SSH audit key 2026-06-28 около `14:10-14:22 UTC`.

## Scope

Снимок включает:

- OS, hostname, uptime, disk, memory, reboot/update state.
- IP addresses, routes, forwarding, listening sockets, UFW, iptables.
- Running/enabled services, selected SSH effective config.
- Docker runtime, compose project, networks and sanitized inspect.
- WireGuard runtime inside container.
- Sanitized `/opt/wg/docker-compose.yml`.
- Sanitized active `wg0.conf`.
- Sanitized generated peer/template configs.
- Metadata and search results for config ports, BTH/wg-home markers and cert/key filenames.
- Installed package list.
- SHA256 checksums for backup files.

## Files

- `system_inventory.txt` - OS/resources/reboot/update state.
- `network_firewall_inventory.txt` - addresses, routes, forwarding, sockets, UFW, iptables.
- `services_inventory.txt` - services and SSH effective selected settings.
- `docker_inventory_sanitized.txt` - Docker status, network, sanitized inspect.
- `wireguard_runtime_sanitized.txt` - `wg show`, container routes and forwarding.
- `opt_wg_tree.txt` - metadata tree for `/opt/wg`.
- `docker-compose.yml.sanitized` - sanitized compose file.
- `wg0.conf.sanitized` - active WireGuard config with private/preshared keys redacted.
- `peer_configs_sanitized.txt` - generated peer/template configs with secrets redacted.
- `config_search_and_cert_metadata.txt` - port/BTH search and certificate/key file metadata.
- `installed_packages.txt` - package list.
- `post_reboot_verification_2026-06-28T1436Z.txt` - post-reboot service/WireGuard verification.
- `post_upgrade_verification_2026-06-28T1447Z.txt` - post-upgrade/post-second-reboot verification.
- `SHA256SUMS` - local checksums.

## Secret Handling

This backup is intentionally not a full secret backup.

- `PrivateKey` is replaced with `<redacted>`.
- `PresharedKey` is replaced with `<redacted>`.
- Certificate/private key file contents are not copied.
- `/root/.ssh/authorized_keys` content is not copied; only metadata is captured in `services_inventory.txt`.

## Key Findings

- Active VPS IP: `103.75.126.143`.
- Active WireGuard endpoint: `103.75.126.143:51821/udp`.
- Active container: `wg-exit`.
- Active WireGuard interface: `wg0`, `10.20.0.2/24`.
- Relay peer endpoint in config: `94.241.171.65:51820`.
- Relay peer live endpoint observed: `94.241.171.65:63431`.
- BTH/wg-home was not found live.
- Generated peer configs still reference `103.75.126.143:51820`; active publish/listen uses `51821`.
- Post-reboot verification succeeded: kernel `6.8.0-124-generic`, `wg-exit` running, UDP `51821` listening, relay peer handshake fresh, external IPv4 `103.75.126.143`, reboot-required `no`.
- Post-upgrade verification succeeded: OS `Ubuntu 24.04.4 LTS`, updates pending `0`, reboot-required `no`, `wg-exit` running, UDP `51821` listening, relay peer handshake fresh, external IPv4 `103.75.126.143`, end-to-end tunnel confirmed by user.
