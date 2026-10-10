---
type: backup-snapshot
topic: mikrotik
system: cenuta
status: active
created: 2026-06-28
collected_at_utc: 2026-06-28T20:00:59Z
tags:
  - mikrotik
  - vpn
  - backup
  - wireguard
  - cenuta
---

## Назначение

Read-only snapshot текущего состояния Cenuta VPS на 2026-06-28. Снимок сделан по SSH ключом `.local/ssh/codex_cenuta_audit_20260628`.

## Состав

- `system_inventory.txt` - ОС, hostname, kernel, uptime, RAM, диски, reboot/update status.
- `network_firewall_inventory.txt` - IP-адреса, маршруты, DNS, forwarding, listening sockets, UFW, iptables/nft, netplan, effective SSH config.
- `services_inventory.txt` - failed units, key service states, sockets and timers.
- `wireguard_runtime.txt` - WireGuard module/runtime check and config metadata without secrets.
- `installed_packages.txt` - установленный package snapshot.
- `package_updates_inventory.txt` - pending updates, `apt -s upgrade`, relevant packages and unattended-upgrades logs.
- SHA256SUMS (source reference not migrated) - checksums файлов snapshot.

## Санитизация

Private keys, preshared keys, QR-коды и полные WireGuard/client configs не собирались. Snapshot предназначен для синхронизации в Obsidian/Dropbox.

## Главные выводы из snapshot

- Host: `VM-65a473e7-94a5-4a83-bcd8-161603acf6a0`, `Ubuntu 24.04.3 LTS`, kernel `6.8.0-71-generic`.
- Public IPv4: `89.252.153.129`.
- Public IPv6: не зафиксирован; external IPv6 check не прошел.
- Network interface: `ens3`, `89.252.153.129/24`.
- Default gateway: `89.252.153.1`.
- DNS: `1.1.1.1`, `1.0.0.1`.
- UFW inactive; iptables default policies open.
- IPv4 forwarding disabled.
- IPv6 forwarding disabled.
- WireGuard kernel module loaded, but `wireguard-tools` are not installed.
- Docker not installed.
- Reboot required: yes.
- Pending updates: `48`.
- `apt -s upgrade`: `48 upgraded`, `2 newly installed`, `0 to remove`, `0 not upgraded`.

## Ограничения

Snapshot не является секретным disaster-recovery backup: на Cenuta еще нет WireGuard секретов и активных VPN-конфигов. После настройки WireGuard потребуется отдельный зашифрованный backup секретов.
