---
type: backup
topic: mikrotik
system: timeweb
status: active
created: 2026-06-29T15:05:00Z
tags:
  - mikrotik
  - vpn
  - backup
  - timeweb
  - wireguard
---

## Назначение

Sanitized checkpoint после добавления интерактивной команды просмотра exported WireGuard client config и QR-code.

## Что добавлено

- `/opt/wg-router/commands.sh show-client [exported-config-name]`.
- `/usr/local/sbin/wg-client-config` как короткая команда.
- Обновлены TimeWeb docs: `/opt/wg-router/docs/CLIENT_CREATION.md`, `/opt/wg-router/docs/RUNBOOK.md`, `/opt/wg-router/docs/IMPLEMENTATION_LOG.md`.

## Использование

```bash
sudo wg-client-config
```

После запуска команда:

1. показывает список exported configs из `/root/wg-client-exports/`;
2. предлагает выбрать номер;
3. после `ENTER` печатает полный WireGuard config и QR-code.

Прямой вызов:

```bash
sudo wg-client-config <client-name>-cenuta.conf
```

## Проверки

- `qrencode` установлен на TimeWeb.
- `commands.sh help` показывает `show-client`.
- Non-interactive run без имени config отказывается печатать секреты.
- Interactive run показывает список exported configs и корректно отвергает неверный номер.
- Root-only backup после изменения: `/opt/wg-router/backups/20260629T150512Z`.

## Секреты

Полные client configs, private keys, preshared keys и QR-code не сохранены в этом snapshot.
