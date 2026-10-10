---
type: archive-index
topic: mikrotik
system: cenuta
status: active
created: 2026-06-28
tags:
  - mikrotik
  - vpn
  - archive
  - cenuta
---

## Назначение

Папка хранит sanitized archive summaries и task checkpoints по Cenuta. Это
история работ и проверок, а не место для полных backup-файлов.

Полные/evidence файлы вынесены в Dropbox:

`.local/backups/cenuta`

## Снимки

- 2026-06-28T1958Z live audit (source reference not migrated) - read-only аудит текущего состояния Cenuta.
- 2026-06-28T2017Z post-update check (source reference not migrated) - проверка после `apt upgrade`, reboot и установки `wireguard-tools`.
- 2026-06-28T2025Z wg-cenuta setup (source reference not migrated) - проверка после настройки hostname, sysctl, nftables и `wg-cenuta`.

## Правило секретов

Полные private keys, preshared keys, QR-коды и client configs в Obsidian не
сохранять. Если понадобится полный секретный backup, хранить его в Dropbox
`System` или отдельном зашифрованном контуре.
