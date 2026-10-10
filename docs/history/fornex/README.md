---
type: archive-index
topic: mikrotik
system: fornex
status: active
created: 2026-06-28
tags:
  - mikrotik
  - vpn
  - archive
  - fornex
---

## Назначение

Папка хранит sanitized archive summaries и task checkpoints по Fornex. Это
история работ и проверок, а не место для полных backup-файлов.

Полные/evidence файлы вынесены в Dropbox:

`.local/backups/fornex`

## Снимки

- 2026-06-28T1410Z live audit (source reference not migrated) - read-only аудит текущего состояния Fornex.

## Правило секретов

Полные private keys, preshared keys, QR-коды и client configs в Obsidian не
сохранять. Если понадобится полный секретный backup, хранить его в Dropbox
`System` или отдельном зашифрованном контуре.
