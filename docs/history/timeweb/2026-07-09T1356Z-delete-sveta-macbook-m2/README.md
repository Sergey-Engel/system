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

Checkpoint после удаления неиспользуемого legacy client config:

```text
sveta-macbook-m2-cenuta-domru.conf
10.10.10.8/32
```

Полный client config удален с TimeWeb и из локального каталога:

```text
.local/clients/
```

Секретные private keys и полные configs в Obsidian не включались.

## Серверные backup-и

```text
/opt/wg-router/backups/20260709T135532Z
/opt/wg-router/backups/20260709T135533Z
/opt/wg-router/backups/20260709T135534Z
/opt/wg-router/backups/20260709T135535Z
/opt/wg-router/state/legacy_ru_bth_clients.tsv.before-delete-sveta-macbook-m2-20260709T135532Z
```

## Выполненные действия

```bash
/opt/wg-router/commands.sh backup
WG_ROUTER_CONFIRM_DELETE=yes /opt/wg-router/commands.sh delete-client sveta-macbook-m2-cenuta-domru.conf
/opt/wg-router/commands.sh apply-ru-bth
/opt/wg-router/commands.sh backup
```

Из `/opt/wg-router/state/legacy_ru_bth_clients.tsv` удалена строка
`10.10.10.8/sveta-macbook-m2-cenuta-domru`.

## Проверки

После применения:

- `sessions --interface wg0` не показывает `sveta-macbook-m2-cenuta-domru` и `10.10.10.8`;
- `/opt/wg/clients` и `/root/wg-client-exports` не содержат файлов `sveta-macbook-m2-cenuta-domru`;
- `/opt/wg/config/wg_confs/wg0.conf` не содержит peer `sveta-macbook-m2-cenuta-domru` и `10.10.10.8`;
- `ip rule` и `nft table inet ru_bth` не содержат `10.10.10.8` и `priority 208`;
- в legacy override state остался только `10.10.10.12/sveta-ipad-9.7-cenuta-domru`.

## Локальные документы

Обновлены:

- [TimeWeb VPN Registry](<../../../registry/tunnels.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- Archive (source reference not migrated);
- `docs/registry/tunnels.md`.
