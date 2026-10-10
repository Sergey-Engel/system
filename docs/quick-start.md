# MikroTik / VPN Quick Guide

Все команды из корня checkout. После установки локальных bindings:

## Запуск консоли

```sh
timeweb-vpn
```

[VPN control](http://127.0.0.1:19118/) открывается автоматически. Команда
запускает один фоновый SSH, повторный запуск использует его же. Terminal
оставлять открытым не требуется. `timeweb-vpn status`, `timeweb-vpn logs`,
`timeweb-vpn stop` показывают состояние/журнал и останавливают только этот SSH.
Журнал: [.local/runtime/timeweb-vpn/launcher.log](../.local/runtime/timeweb-vpn/launcher.log).
Публичный доступ к management портам не открывается.

Первая настройка нового Mac: [перенос и установка](operations/storage-and-transfer.md).
Ручной fallback, если launcher не используется: `ssh -N timeweb-console`.
Не запускать его параллельно с launcher на том же порту.

## Prometheus / Grafana

Docker Desktop должен работать. Проверить или запустить существующий проект:

```sh
docker compose -p vpn-connectivity -f services/monitoring/vpn-connectivity/compose.yaml ps
docker compose -p vpn-connectivity -f services/monitoring/vpn-connectivity/compose.yaml up -d
```

- [Grafana: TimeWeb Uplinks - Pilot](http://127.0.0.1:3000/d/timeweb-uplink-pilot/timeweb-uplinks-pilot?orgId=1&from=now-24h&to=now&timezone=browser&refresh=1m).
- [Prometheus targets](http://127.0.0.1:9090/targets).
- `com.sergey.timeweb-uplink-tunnel` поддерживает отдельный forward 19106;
  probe agents наблюдают хост и устройства. `setup_mac.py --install` ставит
  их в user LaunchAgents, с запуском после входа в macOS.

`UP` у scrape target не доказывает валидность измерений. Для каждого uplink
должны обновляться timestamp, `vpn_uplink_observation_fresh=1` и
`vpn_uplink_probe_valid=1`. `UNKNOWN/NO DATA` означает проблему наблюдений,
не автоматически отказ VPN. `DEGRADED` требует расшифровки причины.
FLEX `READY` означает готовность маршрута, не подключённый телефон/Mac.
Xray activity определяется свежими access events, не наличием профиля.

## Доступ к узлам

[Полная процедура и ограничения](operations/access.md). Существующие aliases:

```sh
ssh timeweb
ssh fornex
ssh cenuta
ssh mikrotik-nakhimova
ssh mikrotik-orekhovo
```

Нахимова доступна из внешней сети через TimeWeb -> `wg-relay` -> `wg-home`
-> `10.30.30.2:22`; proxy настроен в alias. Орехово требует сетевой
доступности своей площадки. Их одинаковые LAN IP `192.168.88.1` не означают
один роутер; перед работой проверить model/serial и host key.

## Только чтение

Сначала определить контур: WG в `wg-relay`, host Xray REALITY/SOCKS/FLEX,
прямой AWG31 на Fornex или маршрутизация MikroTik. `wg-status` не показывает
полную картину Xray/AWG.

На TimeWeb:

```sh
systemctl status xray-timeweb-reality bth-recovery.timer --no-pager
systemctl show bth-recovery -p Result -p ExecMainStatus
docker inspect --format '{{.Name}} {{.State.Status}} {{.State.Pid}}' wg-relay
/opt/wg-router/commands.sh sessions
/usr/local/sbin/timeweb-flex-fleet status
python3 /opt/vpn-runtime-recovery/runtime_recovery.py check
```

Эти проверки не дают разрешения на изменение routing/контрактов. Полные
конфиги, `showconf`, passwords/UUID/QR не выводить в общий журнал.

## Перед изменением тоннелей

Прочитать [agent workflow](operations/agent-workflow.md) и
[локальный skill](../.agents/skills/create-timeweb-vpn-client/SKILL.md).
Свежие backups и проверки: [хранение и восстановление](operations/storage-and-transfer.md).

Legacy `maintenance_preflight.py --check` оставлен fail-closed. При переносе
он выявил расхождение исторического BTH hostguard baseline с текущими файлами.
Не обновлять контракт автоматически ради PASS. Текущий runtime `check` и
legacy static baseline check имеют разный scope; результаты фиксировать отдельно.

Реестры: [профили](registry/tunnels.md), [конфигурация](registry/configuration.md),
[архитектура](architecture/overview.md), [схемы](architecture/diagrams/index.html).
