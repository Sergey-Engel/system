---
type: backup
topic: mikrotik
system: timeweb
status: active
created: 2026-06-29T07:34:00Z
tags:
  - mikrotik
  - vpn
  - backup
  - timeweb
  - wireguard
---

## Назначение

Sanitized checkpoint после добавления единой команды создания WireGuard client configs на TimeWeb.

## Что изменено

- `/opt/wg-router/commands.sh` получил wrapper `add-client <client-name> fornex|cenuta|bth`.
- Для `fornex` и `cenuta` wrapper выполняет полный цикл: generate, render, up, test, export, backup.
- Для `bth` wrapper вызывает существующий `/opt/wg/add-bth.sh`, синхронизирует `wg-home`, экспортирует итоговый конфиг в `/root/wg-client-exports/` и делает backup.
- Добавлена короткая инструкция на TimeWeb: `/opt/wg-router/docs/CLIENT_CREATION.md`.
- В Obsidian добавлена отдельная инструкция: [TimeWeb Client Creation](<../../../operations/TimeWeb_Client_Creation.md>).

## Состав снимка

- `commands_and_docs_sanitized.txt` - sanitized copy of `/opt/wg-router/commands.sh`, `CLIENT_CREATION.md`, `RUNBOOK.md`.
- `runtime_verification.txt` - help/status, non-mutating duplicate/error checks, Docker and UDP listener checks.
- `file_metadata.txt` - metadata for changed remote files and last root-only `/opt/wg-router/backups/` entries.
- `SHA256SUMS` - checksums for local snapshot files.

## Проверки

- `commands.sh help` показывает `add-client <client-name> fornex|cenuta|bth`.
- `add-client` without args returns usage error.
- Duplicate BTH client check returns `BTH client already exists`.
- Duplicate selector client with conflicting route returns route conflict.
- `wg-relay` remains running.
- Published UDP ports remain active: `51820`, `51830`, `51850`.
- Active interfaces remain visible in runtime: `wg0`, `wg1`, `wg-home`, `wg-up-cenuta`, `wg-clients`.

## Секреты

Private keys, preshared keys, QR codes and full client configs are not stored in this snapshot. Secret-bearing configs remain only on TimeWeb root-only paths.

Root-only backup created by the wrapper change:

```text
/opt/wg-router/backups/20260629T073034Z
```
