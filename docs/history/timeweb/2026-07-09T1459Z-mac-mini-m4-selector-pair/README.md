---
type: backup-note
topic: mikrotik
system: timeweb
status: active
created: 2026-07-09
tags:
  - mikrotik
  - vpn
  - wireguard
  - timeweb
  - backup
  - operations-log
---

## Назначение

Checkpoint после создания двух новых selector profiles для `Mac Mini M4`.

Созданы:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Mac Mini M4 | `mac-mini-m4-cenuta-domru.conf` | `10.50.50.31/32` | RU -> BTH/Home/Dom.ru; non-RU -> Cenuta |
| Mac Mini M4 | `mac-mini-m4-fornex-domru.conf` | `10.50.50.32/32` | RU -> BTH/Home/Dom.ru; non-RU -> Fornex |

Старый legacy profile `mac-mini-m4-fornex.conf` (`10.10.10.20/32`) не
удалялся.

Полные новые client configs скопированы в локальный каталог:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/backups/20260709T145902Z
/opt/wg-router/backups/20260709T145905Z
/opt/wg-router/backups/20260709T145909Z
/opt/wg-router/backups/20260709T145910Z
/opt/wg-router/state/ru_bth_clients.tsv.before-mac-mini-m4-selector-ru-20260709T145902Z
```

## Выполненные действия

```bash
/opt/wg-router/commands.sh backup
/opt/wg-router/commands.sh add-client mac-mini-m4-cenuta-domru cenuta
/opt/wg-router/commands.sh add-client mac-mini-m4-fornex-domru fornex
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh test-ru-bth 10.50.50.31 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh test-ru-bth 10.50.50.32 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh backup
```

## Проверки

Маршрутизация:

- `10.50.50.31`: RU destination -> `wg-home`, table `300`; non-RU -> `wg-up-cenuta`, table `200`;
- `10.50.50.32`: RU destination -> `wg-home`, table `300`; non-RU -> `wg1`, table `100`;
- reply из `wg-home` к обоим IP возвращается через `wg-clients`.

Состояние:

- оба новых профиля видны в `sessions --interface wg-clients`;
- handshake у новых профилей пока `never`, потому что они еще не импортированы на устройство;
- `10.50.50.31` и `10.50.50.32` добавлены в `ru_bth_clients.tsv`;
- `ip rule` содержит `priority 231` и `priority 232`;
- `nft table inet ru_bth` содержит `10.50.50.31` и `10.50.50.32`.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`.
