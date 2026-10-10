---
type: backup-snapshot
topic: mikrotik
system: timeweb
status: active
created: 2026-06-28
collected_at_utc: 2026-06-28T17:31:09Z
tags:
  - mikrotik
  - vpn
  - backup
  - wireguard
  - timeweb
---

## Назначение

Read-only snapshot текущего состояния TimeWeb VPS на 2026-06-28. Снимок сделан по SSH ключом `.local/ssh/codex_timeweb_audit_20260628`.

## Состав

- `system_inventory.txt` - ОС, hostname, kernel, uptime, RAM, диски, reboot/update status.
- `network_firewall_inventory.txt` - IP-адреса, маршруты, DNS, forwarding, listening sockets, UFW, iptables/nft.
- `services_inventory.txt` - running/enabled/failed services, SSH effective config, root SSH metadata.
- `docker_inventory_sanitized.txt` - Docker version, running containers, compose project, networks, sanitized inspect.
- `wireguard_runtime_sanitized.txt` - `wg show` внутри контейнера, container routes/rules, без private key values.
- `configs_sanitized.txt` - санитизированные конфиги из `/etc/wireguard` и `/opt/wg`.
- `config_tree_metadata.txt` - дерево и metadata конфигурационных файлов.
- `config_search_and_cert_metadata.txt` - поиск по WG-портам/маршрутам и metadata key/cert files.
- `installed_packages.txt` - установленный package snapshot.
- `package_updates_inventory.txt` - pending updates и хвост unattended-upgrades logs.
- SHA256SUMS (source reference not migrated) - checksums файлов snapshot.

## Санитизация

Private keys, preshared keys и потенциальные key-like строки в конфигурационных файлах заменены на `<redacted>`. Snapshot предназначен для синхронизации в Obsidian/Dropbox.

## Главные выводы из snapshot

- Host: `6275803-hh441050`, `Ubuntu 24.04.4 LTS`, kernel `6.8.0-111-generic`.
- Public IPv4: `94.241.171.65`.
- Docker container: `wg-relay`, image `lscr.io/linuxserver/wireguard:latest`, restart policy `unless-stopped`.
- Active WG endpoints: `51820/udp` для обычных клиентов и `51830/udp` для BTH.
- Active uplink to Fornex: container `wg1`, peer endpoint `103.75.126.143:51821`.
- IPv4 forwarding enabled, IPv6 forwarding disabled.
- UFW inactive.
- Reboot required: yes.
- Pending updates: `17`.

## Ограничения

Snapshot не является секретным disaster-recovery backup: он не содержит приватные ключи и PSK values. Для полного восстановления WireGuard клиентов потребуется отдельный зашифрованный backup секретов с сервера.
