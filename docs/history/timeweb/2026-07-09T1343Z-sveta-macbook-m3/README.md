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

Checkpoint после создания двух новых selector client configs для нового
устройства `Sveta MacBook M3`.

Созданы:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Sveta MacBook M3 | `sveta-macbook-m3-cenuta-domru.conf` | `10.50.50.26/32` | RU -> BTH/Home/Dom.ru; non-RU -> Cenuta |
| Sveta MacBook M3 | `sveta-macbook-m3-fornex-domru.conf` | `10.50.50.27/32` | RU -> BTH/Home/Dom.ru; non-RU -> Fornex |

Полные client configs скопированы в локальный каталог:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/commands.sh.before-sveta-macbook-m3-20260709T134158Z
/opt/wg-router/backups/20260709T134158Z
/opt/wg-router/backups/20260709T134235Z
/opt/wg-router/backups/20260709T134238Z
/opt/wg-router/backups/20260709T134329Z
/opt/wg-router/state/ru_bth_clients.tsv.before-sveta-macbook-m3-20260709T134257Z
/opt/wg-router/state/ru_bth_clients.tsv.before-sveta-macbook-m3-20260709T134328Z
```

## Проверки

Выполнено на TimeWeb:

```bash
/opt/wg-router/commands.sh add-client sveta-macbook-m3-cenuta-domru cenuta
/opt/wg-router/commands.sh add-client sveta-macbook-m3-fornex-domru fornex
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh test-ru-bth 10.50.50.26 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh test-ru-bth 10.50.50.27 77.88.55.88 1.1.1.1
```

Результат:

- `10.50.50.26`: RU destination -> `wg-home` / table `300`; non-RU -> `wg-up-cenuta` / table `200`.
- `10.50.50.27`: RU destination -> `wg-home` / table `300`; non-RU -> `wg1` / table `100`.
- Оба IP добавлены в `/opt/wg-router/state/ru_bth_clients.tsv`.
- Оба client configs видны в `sessions --interface wg-clients`; handshake пока `never`, потому что устройство еще не импортировало профили.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`.
