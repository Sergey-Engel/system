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

Checkpoint после замены старого legacy profile для `Sveta iPad 9.7` на два
новых selector profiles.

Созданы:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Sveta iPad 9.7 | `sveta-ipad-9.7-cenuta-domru.conf` | `10.50.50.29/32` | RU -> BTH/Home/Dom.ru; non-RU -> Cenuta |
| Sveta iPad 9.7 | `sveta-ipad-9.7-fornex-domru.conf` | `10.50.50.30/32` | RU -> BTH/Home/Dom.ru; non-RU -> Fornex |

Удален:

| Устройство | VPN config | VPN IP | Маршрут |
| --- | --- | --- | --- |
| Sveta iPad 9.7 | `sveta-ipad-9.7-cenuta-domru.conf` | `10.10.10.12/32` | Legacy override: RU -> BTH/Home/Dom.ru; non-RU -> Cenuta |

Полные новые client configs скопированы в локальный каталог:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/commands.sh.before-dot-client-names-20260709T144700Z
/opt/wg-router/backups/20260709T144737Z
/opt/wg-router/backups/20260709T144738Z
/opt/wg-router/apply-ru-bth.sh.before-empty-legacy-set-20260709T144920Z
/opt/wg-router/apply-ru-bth.sh.before-empty-legacy-set-v2-20260709T144955Z
/opt/wg-router/backups/20260709T145036Z
/opt/wg-router/backups/20260709T145039Z
/opt/wg-router/backups/20260709T145041Z
/opt/wg-router/state/legacy_ru_bth_clients.tsv.before-sveta-ipad-9.7-replacement-20260709T144737Z
/opt/wg-router/state/ru_bth_clients.tsv.before-sveta-ipad-9.7-replacement-20260709T144737Z
/opt/wg-router/state/ru_bth_clients.tsv.before-sveta-ipad-9.7-selector-ru-20260709T145033Z
```

## Исправление в процессе

При удалении последнего legacy override файл
`/opt/wg-router/state/legacy_ru_bth_clients.tsv` стал пустым, и прежний
`apply-ru-bth.sh` сгенерировал невалидный пустой `nft` set.

Исправлено:

- `/opt/wg-router/commands.sh` теперь разрешает точку в client names, чтобы
  selector profiles могли сохранять имена вида `sveta-ipad-9.7-*`;
- `/opt/wg-router/apply-ru-bth.sh` теперь корректно обрабатывает пустой
  `legacy_ru_bth_clients.tsv`, не печатая `elements` для пустого `nft` set;
- в [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>)
  добавлено правило, что state-файлы RU-via-BTH могут быть пустыми при
  миграциях.

## Выполненные действия

```bash
WG_ROUTER_CONFIRM_DELETE=yes /opt/wg-router/commands.sh delete-client sveta-ipad-9.7-cenuta-domru.conf
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh add-client sveta-ipad-9.7-cenuta-domru cenuta
/opt/wg-router/commands.sh add-client sveta-ipad-9.7-fornex-domru fornex
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh test-ru-bth 10.50.50.29 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh test-ru-bth 10.50.50.30 77.88.55.88 1.1.1.1
/opt/wg-router/commands.sh backup
```

## Проверки

Маршрутизация:

- `10.50.50.29`: RU destination -> `wg-home`, table `300`; non-RU -> `wg-up-cenuta`, table `200`;
- `10.50.50.30`: RU destination -> `wg-home`, table `300`; non-RU -> `wg1`, table `100`;
- reply из `wg-home` к обоим IP возвращается через `wg-clients`.

Состояние:

- оба новых профиля видны в `sessions --interface wg-clients`;
- handshake у новых профилей пока `never`, потому что они еще не импортированы на устройство;
- старый legacy profile удален из `wg0` и `/opt/wg/clients`;
- `legacy_ru_bth_clients.tsv` сейчас пустой;
- `10.50.50.29` и `10.50.50.30` добавлены в `ru_bth_clients.tsv`;
- `ip rule` содержит `priority 229` и `priority 230`;
- `nft table inet ru_bth` содержит `10.50.50.29` и `10.50.50.30`.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`;
- `Personal/RESOURCE/IT/MIKROTIK/docs/agents/host-state/TimeWeb/commands.sh`;
- `Personal/RESOURCE/IT/MIKROTIK/docs/agents/host-state/TimeWeb/apply-ru-bth.sh`.
