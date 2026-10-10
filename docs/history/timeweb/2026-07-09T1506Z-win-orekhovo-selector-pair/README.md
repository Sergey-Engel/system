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

Checkpoint после создания двух новых selector profiles для `Win Orekhovo`.

Созданы:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Win Orekhovo | `win-orekhovo-cenuta-domru.conf` | `10.50.50.33/32` | RU -> BTH/Home/Dom.ru; non-RU -> Cenuta |
| Win Orekhovo | `win-orekhovo-fornex-domru.conf` | `10.50.50.34/32` | RU -> BTH/Home/Dom.ru; non-RU -> Fornex |

Старый legacy profile `win-orekhovo-fornex.conf` (`10.10.10.17/32`) не
удалялся.

Полные новые client configs скопированы в локальный каталог:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/backups/20260709T150544Z
/opt/wg-router/backups/20260709T150547Z
/opt/wg-router/backups/20260709T150551Z
/opt/wg-router/backups/20260709T150553Z
/opt/wg-router/state/ru_bth_clients.tsv.before-win-orekhovo-selector-ru-20260709T150544Z
```

## Выполненные действия

```bash
/opt/wg-router/commands.sh backup
/opt/wg-router/commands.sh add-client win-orekhovo-cenuta-domru cenuta
/opt/wg-router/commands.sh add-client win-orekhovo-fornex-domru fornex
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh test-ru-bth 10.50.50.33 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh test-ru-bth 10.50.50.34 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh backup
```

## Проверки

Маршрутизация:

- `10.50.50.33`: RU destination -> `wg-home`, table `300`; non-RU -> `wg-up-cenuta`, table `200`;
- `10.50.50.34`: RU destination -> `wg-home`, table `300`; non-RU -> `wg1`, table `100`;
- reply из `wg-home` к обоим IP возвращается через `wg-clients`.

Состояние:

- оба новых профиля видны в `sessions --interface wg-clients`;
- handshake у новых профилей пока `never`, потому что они еще не импортированы на устройство;
- `10.50.50.33` и `10.50.50.34` добавлены в `ru_bth_clients.tsv`;
- `ip rule` содержит `priority 233` и `priority 234`;
- `nft table inet ru_bth` содержит `10.50.50.33` и `10.50.50.34`.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`.
