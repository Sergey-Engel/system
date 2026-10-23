# MikroTik / VPN Quick Guide

23 октября: Direct и SSH Фетхие восстановлены, добавлен локальный SSH из
Deco68/24; свежие копии и границы проверки —
[checkpoint публикации](history/2026-10-23-publication-checkpoint.md).

Текущая панель4.2.2: все VPN-режимы имеют суффикс-RU. Российские IPv4
идут в местный WAN исходной площадки, включая Direct обоих направлений.
Mode IDs и назначения не менялись. [IP-набор и правила](operations/Panel_RU_Direct.md).
Опрос показывает пять фактических этапов: полоса, текущий этап со спиннером
и прошедшее время. Очередь и ошибки отображаются отдельно. Прогресс не растёт
от времени;100% означает завершение опроса, не исправность всех тоннелей.
Через20 секунд после успешного опроса блок прогресса скрывается. Под Refresh
остаётся зелёная отметка Updated со временем проверенных данных. При ошибке
нет зелёного подтверждения и автоматического скрытия; новый Refresh отменяет
старый таймер. Готовность каждого тоннеля показывается отдельно.
Фоновый Refresh не включён; [контракт и проверки](history/2026-10-22-panel-poll-progress.md).
23 октября исправлен разбор terse export с предупреждением interface not ready:
перенос пути раздела не считается config drift. Сам baseline не обновлялся,
изменения правил/порядка по-прежнему блокируются.
[Диагностика и границы](history/2026-10-23-panel-export-warning.md).
22 октября: одновременные чтения статуса объединяются без TTL-cache;
новый Refresh после завершения получает свежую проверку. POST остаётся
отдельной транзакцией. [Диагностика списка устройств](history/2026-10-22-panel-read-and-publication.md).

21 октября: [панель](http://127.0.0.1:19118/#site-to-site) обновлена до
device routing4.1.0. Для Нахимова доступны Standard, WG-Cenuta-RU,
WG-Fornex-RU, SSTP-Cenuta-RU, SSTP-Fornex-RU и Direct SSTP-RU via Fethiye.
Только явный Apply, проверка выхода и Undo. BTH и управление остаются WG;
исходные назначения устройств сохранены, автоматического failover нет.
Фетхие: по-прежнему только Wi-Fi MikroTik, Standard/Direct SSTP-RU via Nakhimova.
RU-direct проверен изолированными пробами с роутеров, не с реальных устройств.
[Эксплуатация и ограничения](operations/Nakhimova_TimeWeb_SSTP_Split.md),
[проверки и свежие копии](history/2026-10-21-sstp-split-manual-routing.md).
Описания 19-20 октября ниже относятся к предыдущим этапам.

20 октября: TimeWeb обновлён с двумя согласованными перезагрузками;
прежние VPN восстановились. Добавлен отдельный SSTP Нахимова - TimeWeb
на **91.222.238.208:443/TCP**, без маршрутизации устройств и автоматического
переключения. Это не Direct SSTP между площадками.
[Обслуживание и приёмка](history/2026-10-20-timeweb-maintenance-sstp-newip.md),
[свежие копии и публикация](history/2026-10-20-timeweb-publication-checkpoint.md).

19 октября: [Direct SSTP](http://127.0.0.1:19118/#site-to-site) установлен
постоянно, управление добавлено локально в ту же VPN-панель. Вкладка
Device routing объединяет Direct и Split (controller3.0.0). Nakhimova первая:
только permanent DHCP reservations, режимы Standard / Split Cenuta /
Split Fornex / Direct via Fethiye. Fethiye: только Wi-Fi MikroTik,
Standard / Direct via Nakhimova. Имя из справочника + IP, явная галочка Apply.
Исходные назначения не менялись: четыре Cenuta и три Standard на Нахимова,
на Фетхие Standard, выбранных Direct нет. TimeWeb не менялся.
[Протокол единого UI](history/2026-10-19-unified-device-routing.md).
[Сводный checkpoint, backups и границы восстановления](history/2026-10-19-routing-release-checkpoint.md).
[Использование и ограничения](operations/Direct_SSTP.md).
[Обратное направление: проверка с роутера, без реального клиента](history/2026-10-19-sstp-reverse-egress.md).
Прежний server-side S2S candidate ниже не разворачивался: вместо него
используется локальная facade, не требующая изменения TimeWeb.

Фетхие: [паспорт действующей сети](hosts/fethiye/network-passport.md)
(частичное обследование до установки MikroTik).

Планируемый мост Нахимова 11 - Фетхие: [архитектура и варианты каналов](architecture/Nakhimova_Fethiye_Site_to_Site_Design.md).

Вкладка управления устройствами межплощадочного выхода реализована локально,
но пока не установлена на сервер. Доступ к Нахимова 17 октября восстановился;
панель не развёртывалась и требует свежей deployment qualification. Текущая
VPN-панель не изменена. [Статус и порядок установки](operations/Site_to_Site_Console.md).
Прямой канал после проброса Deco неустойчив: потеря локализована на внешней
UDP-доставке WG, нейтральные контроли проходят. Точный DPI/NAT/SPI middlebox
не установлен, рабочий TimeWeb сохранён:
[диагностический отчёт](history/2026-10-18-direct-path-diagnosis.md).

Все команды из корня checkout. После установки локальных bindings:

## Запуск консоли

```sh
timeweb-vpn
```

[VPN control](http://127.0.0.1:19118/) открывается автоматически. Команда
при настроенном Direct SSTP использует два локальных LaunchAgents: facade
и SSH-forward. Повторный запуск использует их же. Terminal оставлять открытым
не требуется. `timeweb-vpn status`, `timeweb-vpn logs`, `timeweb-vpn stop`
относятся только к локальной панели и forward, не останавливают сам SSTP.
Журнал: [.local/runtime/timeweb-vpn/launcher.log](../.local/runtime/timeweb-vpn/launcher.log).
Публичный доступ к management портам не открывается.

Первая настройка нового Mac: [перенос и установка](operations/storage-and-transfer.md).
Ручной VPN-only fallback без локальной facade: `ssh -N timeweb-console`.
Не запускать его параллельно с новой панелью на том же19118 порту.

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
