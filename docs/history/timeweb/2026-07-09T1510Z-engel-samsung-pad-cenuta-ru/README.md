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

Checkpoint после создания нового selector profile `Cenuta+RU` для
`Engel Samsung Pad`.

Создан:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Engel Samsung Pad | `engel-samsung-pad-cenuta-domru.conf` | `10.50.50.35/32` | RU -> BTH/Home/Dom.ru; non-RU -> Cenuta |

Старый legacy profile `engel-samsung-pad-fornex.conf` (`10.10.10.13/32`) не
удалялся.

Полный новый client config скопирован в локальный каталог:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/backups/20260709T151036Z
/opt/wg-router/backups/20260709T151040Z
/opt/wg-router/backups/20260709T151042Z
/opt/wg-router/state/ru_bth_clients.tsv.before-engel-samsung-pad-cenuta-ru-20260709T151036Z
```

## Выполненные действия

```bash
/opt/wg-router/commands.sh backup
/opt/wg-router/commands.sh add-client engel-samsung-pad-cenuta-domru cenuta
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh test-ru-bth 10.50.50.35 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh backup
```

## Проверки

Маршрутизация:

- `10.50.50.35`: RU destination -> `wg-home`, table `300`; non-RU -> `wg-up-cenuta`, table `200`;
- reply из `wg-home` к `10.50.50.35` возвращается через `wg-clients`.

Состояние:

- новый профиль виден в `sessions --interface wg-clients`;
- handshake у нового профиля пока `never`, потому что он еще не импортирован на устройство;
- `10.50.50.35` добавлен в `ru_bth_clients.tsv`;
- `ip rule` содержит `priority 235`;
- `nft table inet ru_bth` содержит `10.50.50.35`.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`.
