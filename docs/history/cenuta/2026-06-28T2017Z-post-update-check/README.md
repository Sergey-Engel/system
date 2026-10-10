---
type: verification-checkpoint
topic: mikrotik
system: cenuta
status: complete
created: 2026-06-28
tags:
  - mikrotik
  - vpn
  - cenuta
  - post-update
---

## Scope

Post-upgrade, post-reboot and `wireguard-tools` installation verification of Cenuta VPS on 2026-06-28.

This checkpoint stores only non-secret operational facts. WireGuard private keys, preshared keys and client configs are not present on the server yet and are not stored here.

## Host State

- Hostname: `VM-65a473e7-94a5-4a83-bcd8-161603acf6a0`.
- Target hostname remains: `wg-tr-01`.
- OS: `Ubuntu 24.04.4 LTS`.
- Kernel: `6.8.0-124-generic`.
- Check time: `2026-06-28T20:18:46Z`.
- Uptime at check: `up 3 minutes`.
- Reboot required: no.
- Pending normal updates: `0`.

## Network State

- Public IPv4: `89.252.153.129`.
- Public IPv6: not present; external IPv6 check failed.
- `ens3`: `89.252.153.129/24`, link-local IPv6 `fe80::1c00:97ff:fe00:3c5e/64`.
- IPv4 forwarding: disabled.
- IPv6 forwarding: disabled.

## WireGuard State

- `wireguard-tools`: installed.
- `wg`: `/usr/bin/wg`.
- `wg-quick`: `/usr/bin/wg-quick`.
- `wg` version: `wireguard-tools v1.0.20210914`.
- Kernel module `wireguard`: loaded.
- Active WireGuard interfaces: none.

## Result

Upgrade and reboot were successful. Cenuta is ready for the next setup stage: hostname, IPv4 forwarding, firewall policy and host-level `wg-cenuta` configuration.
