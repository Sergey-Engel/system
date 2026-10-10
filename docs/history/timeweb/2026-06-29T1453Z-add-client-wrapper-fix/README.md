---
type: backup
topic: mikrotik
system: timeweb
status: active
created: 2026-06-29T14:53:00Z
tags:
  - mikrotik
  - vpn
  - backup
  - timeweb
  - wireguard
---

## Назначение

Sanitized checkpoint после исправления `add-client` wrapper и дозавершения создания первого реального Cenuta-routed client config.

## Инцидент

Команда:

```bash
sudo /opt/wg-router/commands.sh add-client sergey-iphone-12 cenuta
```

Первый запуск зарегистрировал клиента и применил `wg-clients`, но остановился перед export/backup с ошибкой:

```text
[wg-router] ERROR: unknown client:
```

## Причина

В `render_clients()` переменные циклов назывались `name` и `route`. В Bash `local` переменные имеют dynamic scope, поэтому вложенная функция затирала аргументы `add_selector_client()`. После `up` wrapper вызывал `test-client` с пустым именем.

## Исправление

- Внутренние переменные циклов переименованы в `client_name`, `client_route`, `client_ip`, `client_pub`, `client_created`.
- Старый скрипт сохранен на TimeWeb: `/opt/wg-router/commands.sh.pre-render-variable-fix-20260629T145241Z`.
- Повторная команда для `sergey-iphone-12 cenuta` прошла idempotent.

## Результат

- Client: `sergey-iphone-12`.
- Route: `cenuta`.
- IP: `10.50.50.20/32`.
- Route check: source `10.50.50.20` -> table `200` -> `wg-up-cenuta`.
- Export: `/root/wg-client-exports/sergey-iphone-12-cenuta.conf`.
- Root-only backup: `/opt/wg-router/backups/20260629T145317Z`.

## Состав снимка

- `commands_log_docs_sanitized.txt` - sanitized `commands.sh`, `IMPLEMENTATION_LOG.md`, `CLIENT_CREATION.md`.
- `runtime_verification.txt` - `test-client sergey-iphone-12`, export/backup metadata, status excerpt.
- `file_metadata.txt` - public client inventory and changed file metadata.
- `SHA256SUMS` - checksums for snapshot files.

## Секреты

Private keys, preshared keys, QR codes and full client configs are not stored in this snapshot.
