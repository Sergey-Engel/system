---
type: verification-checkpoint
topic: mikrotik
system: timeweb
status: complete
created: 2026-06-28
tags:
  - mikrotik
  - vpn
  - timeweb
  - post-update
---

## Scope

Post-update and post-reboot verification of TimeWeb VPS after planned `apt upgrade` and reboot on 2026-06-28.

This checkpoint stores only non-secret operational facts. Private keys, preshared keys, QR codes and full client configs are not stored here.

## Source Command

Executed from local Mac using the Codex audit key:

```bash
ssh -i .local/ssh/codex_timeweb_audit_20260628 -o IdentitiesOnly=yes -o BatchMode=yes root@94.241.171.65
```

## Host State

- Hostname: `6275803-hh441050`.
- OS: `Ubuntu 24.04.4 LTS`.
- Kernel: `6.8.0-124-generic`.
- Check time: `2026-06-28T18:36:50Z`.
- Uptime at check: `up 1 minute`.
- Reboot required: no.
- Normal pending updates: `1`, `qemu-guest-agent` kept back by apt.
- Docker: `29.6.1`.
- Docker Compose: `v5.2.0`.

## Network State

- Public IPv4: `94.241.171.65`.
- Public IPv6: `2a03:6f01:1:2::1:105f`.
- `eth0`: `94.241.171.65/24`, `2a03:6f01:1:2::1:105f/128`, `fe80::4ce6:f8ff:fe46:3789/64`.
- IPv4 forwarding: enabled.
- IPv6 forwarding: disabled.
- Host IPv4 egress check: `94.241.171.65`.
- Host IPv6 egress check: `2a03:6f01:1:2::1:105f`.

## Docker and WireGuard State

- Container: `wg-relay`.
- Image: `lscr.io/linuxserver/wireguard:latest`.
- Status: running after reboot.
- Restart policy from prior audit: `unless-stopped`.
- Published UDP ports:
  - `51820:51820/udp`.
  - `51830:51830/udp`.
- `ss` confirms Docker proxy listening on IPv4 and IPv6 sockets for `51820` and `51830`.

## WireGuard Runtime

- `wg0`: regular client endpoint, `10.10.10.1/24`, listen `51820`.
- `wg1`: Fornex uplink, `10.20.0.1/24`, peer endpoint `103.75.126.143:51821`, fresh handshake after reboot.
- `wg-home`: BTH endpoint, `10.30.30.1/24`, listen `51830`, MikroTik/home peer fresh handshake after reboot.

## Routing Checks

- Container rule for regular clients: `from 10.10.10.0/24 lookup 100`.
- Container table `100`: `default via 10.20.0.2 dev wg1`.
- `ip route get 1.1.1.1 from 10.10.10.1` resolves through `wg1` table `100`.
- Container rule for BTH: `iif wg-home lookup 300`.
- Container table `300`: `default dev wg-home scope link`.
- NAT for regular clients: `10.10.10.0/24` masqueraded on `wg1`.

## Result

Update and reboot were successful. TimeWeb regular WG relay, Fornex uplink and BTH path are operational after reboot.
