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

Checkpoint после доработки TimeWeb WireGuard maintenance:

- `wg-status` переведен на новый именованный вывод `/opt/wg-router/commands.sh sessions`;
- `sessions` показывает selector, legacy, BTH и upstream peers с именами, route labels, latest handshake и traffic counters;
- selector `add-client`/`delete-client`/`regenerate-client`/`refresh-clients` применяются мягко через `wg syncconf wg-clients` и runtime `ip rule`/`iptables`;
- полный recreate `wg-relay` оставлен как fallback, если soft reload недоступен или не проходит.

Секретные client configs, private keys, preshared keys и QR-code в этот checkpoint не включались.

## Серверные backup-и

Перед заменой файлов на TimeWeb созданы серверные копии:

```text
/opt/wg-router/commands.sh.before-softreload-sessions-20260709T132817Z
/usr/local/bin/wg-status.before-sessions-20260709T132817Z
```

Также через штатный `/opt/wg-router/commands.sh backup` созданы root-only backup-и:

```text
/opt/wg-router/backups/20260709T132230Z
/opt/wg-router/backups/20260709T133136Z
/opt/wg-router/backups/20260709T133153Z
/opt/wg-router/backups/20260709T133156Z
```

Назначение:

- `20260709T132230Z` - pre-change snapshot до правки;
- `20260709T133136Z` - после создания временного test selector client;
- `20260709T133153Z` - перед удалением временного test selector client;
- `20260709T133156Z` - после удаления временного test selector client.

## Измененные серверные файлы

```text
/opt/wg-router/commands.sh
/usr/local/bin/wg-status
```

Final hashes после проверки:

```text
ecedc5d0535e2bcec4c9341c84ffc1ec836f92d31bd988999511fc50b1764a0b  /opt/wg-router/commands.sh
a75d948b3c5e3ef008e72b675d72041615f2a1d7de025d0cf614f90fc05bedbf  /usr/local/bin/wg-status
```

## Проверки

Выполнено:

```bash
bash -n /opt/wg-router/commands.sh
bash -n /usr/local/bin/wg-status
wg-status
wg-status --active
wg-status --interface wg-clients
sudo /opt/wg-router/commands.sh sessions --json | python3 -m json.tool
```

Результат:

- named status выводит selector `wg-clients`, legacy `wg0`, BTH `wg-home`, `Cenuta upstream`, `Fornex upstream`, `MikroTik Router`;
- JSON валиден;
- `wg-status --active` корректно фильтрует peers без handshake;
- `wg-status --interface wg-clients` показывает только selector clients.

## Live regression test

Создан временный selector client:

```text
name: codex-softreload-test
route: cenuta
ip: 10.50.50.26/32
```

Проверки при создании:

- в логе есть `selector soft reload applied`;
- route check: `ip route get 1.1.1.1 from 10.50.50.26 iif wg-clients` идет через `wg-up-cenuta`, table `200`;
- NAT/FORWARD rules для `10.50.50.26/32` добавлены;
- `docker inspect wg-relay .State.StartedAt` не изменился, контейнер не пересоздавался.

После проверки временный client удален через:

```bash
WG_ROUTER_CONFIRM_DELETE=yes /opt/wg-router/commands.sh delete-client codex-softreload-test-cenuta.conf
```

Проверки после удаления:

- state `/opt/wg-router/state/clients.tsv` не содержит `codex-softreload-test`;
- файлов `codex-softreload-test*` нет в `/opt/wg-router/client-configs` и `/root/wg-client-exports`;
- `wg show wg-clients allowed-ips`, `ip rule`, `iptables -t nat -S`, `iptables -S` не содержат `10.50.50.26`;
- `docker inspect wg-relay .State.StartedAt` не изменился, удаление также прошло без recreate.

## Локальные документы

Обновлены:

- [commands.sh](<../../../../services/transport/timeweb-reality/maintenance-wg/commands.sh>);
- wg-status (source reference not migrated);
- [TimeWeb Client Creation](<../../../operations/TimeWeb_Client_Creation.md>);
- [TimeWeb Parameters](<../../../hosts/timeweb/TimeWeb_Parameters.md>);
- [TimeWeb Configuration](<../../../hosts/timeweb/TimeWeb_Configuration.md>);
- [MikroTik Quick Guide](<../../../quick-start.md>);
- Archive (source reference not migrated).
