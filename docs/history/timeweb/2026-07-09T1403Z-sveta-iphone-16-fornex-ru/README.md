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

Checkpoint после замены старого legacy profile для `Sveta iPhone 16` на новый
selector profile `Fornex+RU`.

Создан:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Sveta iPhone 16 | `sveta-iphone-16-fornex-domru.conf` | `10.50.50.28/32` | RU -> BTH/Home/Dom.ru; non-RU -> Fornex |

Удален:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Sveta iPhone 16 | `sveta-iphone-16-fornex.conf` | `10.10.10.9/32` | Legacy: all -> Fornex |

Полный новый client config скопирован в локальный каталог:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/backups/20260709T140255Z
/opt/wg-router/backups/20260709T140258Z
/opt/wg-router/backups/20260709T140259Z
/opt/wg-router/backups/20260709T140300Z
/opt/wg-router/backups/20260709T140302Z
/opt/wg-router/state/ru_bth_clients.tsv.before-sveta-iphone-16-fornex-domru-20260709T140255Z
```

## Выполненные действия

```bash
/opt/wg-router/commands.sh backup
/opt/wg-router/commands.sh add-client sveta-iphone-16-fornex-domru fornex
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh test-ru-bth 10.50.50.28 77.88.55.88 1.1.1.1
WG_ROUTER_CONFIRM_DELETE=yes /opt/wg-router/commands.sh delete-client sveta-iphone-16-fornex.conf
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh backup
```

## Проверки

Маршрутизация:

- `77.88.55.88` из `10.50.50.28` идет через `wg-home`, table `300`, mark `0x30`;
- `1.1.1.1` из `10.50.50.28` идет через `wg1`, table `100`;
- reply из `wg-home` к `10.50.50.28` возвращается через `wg-clients`.

Состояние:

- `sveta-iphone-16-fornex-domru.conf` виден в `sessions --interface wg-clients`;
- handshake у нового профиля пока `never`, потому что профиль еще не импортирован на устройстве;
- `sveta-iphone-16-fornex.conf` удален из legacy `wg0` и из локального `.local/clients`;
- `10.50.50.28` добавлен в `/opt/wg-router/state/ru_bth_clients.tsv`;
- `ip rule` содержит `priority 228`, `from 10.50.50.28 lookup 100`;
- `nft table inet ru_bth` содержит `10.50.50.28`.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`.
