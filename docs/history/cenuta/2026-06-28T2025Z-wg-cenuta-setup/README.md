---
type: verification-checkpoint
topic: mikrotik
system: cenuta
status: complete
created: 2026-06-28
tags:
  - mikrotik
  - vpn
  - wireguard
  - cenuta
  - setup
---

## Scope

Post-setup verification for Cenuta `wg-cenuta` host-level WireGuard egress configuration.

This checkpoint is sanitized. Private keys are replaced with `<redacted>`. Full secret handoff config for TimeWeb is not stored in Obsidian.

## Result

- Hostname: `wg-tr-01`.
- OS: `Ubuntu 24.04.4 LTS`.
- Kernel: `6.8.0-124-generic`.
- Reboot required: no.
- Pending updates: `0`.
- Public IPv4: `89.252.153.129`.
- Public IPv6: not present; external IPv6 check failed.
- IPv4 forwarding: enabled.
- IPv6 forwarding: disabled.
- Firewall: `nftables`, enabled and active.
- WireGuard service: `wg-quick@wg-cenuta`, enabled and active.
- WireGuard endpoint: `89.252.153.129:51840/udp`.
- WireGuard interface: `wg-cenuta`.
- WireGuard address: `10.40.40.1/24`.
- Cenuta public key: `3fg6rK3jeTdtGxtr0yX896BhEtH33OvWyx3ncTm6uR0=`.
- TimeWeb peer public key: `OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=`.
- TimeWeb peer allowed IP on Cenuta: `10.40.40.2/32`.

## Files

- `system_network_verification.txt` - host identity, network, public IP, forwarding and update status.
- `runtime_firewall_verification.txt` - service state, sockets, nftables rules and `wg show`.
- `configs_sanitized.txt` - sanitized WireGuard config, sanitized TimeWeb handoff config, nftables and sysctl files.
- SHA256SUMS (source reference not migrated) - checksums.

## Server-Side Secret Locations

The following files exist only on Cenuta and are root-only:

- `/etc/wireguard/wg-cenuta.key` - Cenuta private key.
- `/etc/wireguard/wg-cenuta.conf` - active server config with private key.
- `/root/wireguard-handoff/timeweb-wg-up-cenuta.key` - generated private key for the future TimeWeb peer.
- `/root/wireguard-handoff/timeweb-wg-up-cenuta.conf` - generated future TimeWeb peer config.

Do not copy these secret files into Obsidian. Transfer the TimeWeb handoff config securely when TimeWeb setup begins, then remove or rotate the temporary handoff secret if needed.

## Remaining Work

TimeWeb is not configured in this step. Cenuta is ready to accept the planned TimeWeb peer, but no handshake is expected until TimeWeb `wg-up-cenuta` is created and started.
