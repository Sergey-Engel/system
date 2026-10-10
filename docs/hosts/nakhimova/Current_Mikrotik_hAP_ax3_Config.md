---
type: configuration
status: snapshot-not-live
updated: 2026-09-13
tags: [mikrotik, routeros, bth]
---

# MikroTik hAP ax3: Нахимова 11

## Источник и свежесть

Последний прочитанный сохраненный export: `services/transport/timeweb-reality/stage9-bth/router.after.rsc`; заголовок RouterOS **2026-09-13 13:56:05**, версия **7.22.1**, модель **C53UiG+5HPaxD2HPaxD** (hAP ax3). Это более поздний источник, чем экспорт 9 июля в `System/Mikrotik/current/router/`.

При первоначальном ревью SSH через TimeWeb завершился timeout. **В следующем этапе свежий export успешно получен 2026-09-13 16:02:58 UTC** и проверен в приватном архиве, см. [VPN_Maintenance_and_Backup](<../../operations/maintenance-and-backup.md>). Ниже остается описание ранее прочитанного after-state: новый export сохранен и проверен побайтово, но полный повторный смысловой аудит правил не проводился. Ошибка SSH сама по себе не доказывает отказ BTH data plane.

Орехово, Детская 11 имеет другой MikroTik с таким же LAN IP `192.168.88.1`. Перед командами сверять identity/model/ключ хоста, не определять площадку только по IP.

## Адреса и связи

| Интерфейс | Адрес в export | Назначение |
| --- | --- | --- |
| bridge | `192.168.88.1/24` | Домашняя LAN |
| ether1 | `10.12.20.168/22` | Дом.ру, private WAN/CGNAT |
| wg1 | `10.10.10.24/24` | TimeWeb `94.241.171.65:51820`, legacy Fornex |
| wg-cenuta | `10.50.50.24` | TimeWeb `94.241.171.65:51850`, selector Cenuta |
| wg-home | `10.30.30.2/24` | TimeWeb `94.241.171.65:51830`, BTH |

В export три WG MTU 1420; listen ports 13231 / 13250 / 13232. Домашний main default через `10.12.20.1`; прежний дубликат default отключен. Таблицы `WG1-Route` и `CENUTA-Route` направляют default в соответствующие WG.

## Smart Split домашних устройств

По saved export в `CENUTA_Devices` четыре статических записи:

| IP | Подпись |
| --- | --- |
| `192.168.88.35` | Mac Mini M4 |
| `192.168.88.252` | DigitalRazor PC |
| `192.168.88.11` | AppleTV Gostinnaya |
| `192.168.88.28` | AppleTV Spalna |

`VPN_Devices` не содержит записей в этом export. Обе группы имеют парные mangle rules: private/local bypass, принудительное направление для отдельного назначения, RU bypass, BitTorrent 63450–63459 bypass и маршрут остальных назначений в выбранный WG. NAT применяется на `wg1`, `wg-cenuta` и WAN.

Это описывает политику маршрутизатора, но **не доказывает включенный профиль приложения на Apple TV**. Flow VPN на самом Apple TV ранее удерживал сетевое состояние после некорректного завершения; пользователь сообщил о восстановлении после корректного включения/выключения. Не путать такой клиентский отказ с отказом uplink.

## BTH и REALITY

Прежний WG BTH уже работает через `wg-home` и WAN NAT; это не TODO нового внедрения.

REALITY BTH добавляет источник `10.30.30.5` со стороны TimeWeb. В after-export есть собственные правила `REALITY-B5-*`, включая `REALITY-B5-main`: входящий с wg-home трафик этого source исключается из общей policy-marking обработки и должен использовать домашний main. Правила защиты ограничивают доступ нового source; exact diff хранится в `stage9-bth/router.apply.rsc` / `router.rollback.rsc`.

Не переписывать общие allowed-address, NAT или FastTrack ради удаления одного REALITY peer. Для BTH guard rollback использовать точные собственные комментарии/состояние после свежего audit.

Два старых правила MSS clamping для BTH помечены disabled в export. Для wg1/wg-cenuta есть MSS 1360. Из этого нельзя делать вывод о необходимости изменения MTU без диагностики конкретного пути.

## Эксплуатационные ограничения

- Смена групп влияет на трафик LAN, а не на прямые AWG-профили и не на учетную запись REALITY.
- Новый сеанс проверять отдельно от старого conntrack; не очищать общую таблицу соединений ради одного устройства.
- Перед правкой нужны свежий export и binary backup правильного роутера в System.
- Удалять/переставлять правила по старым порядковым номерам нельзя.
- Firewall/FastTrack оценивать в полном порядке правил, не по одной строке export.

Связи: [VPN_HLD](<../../architecture/overview.md>), [Host_Access_Guide](<../../operations/access.md>), [VPN_Configuration_Registry](<../../registry/configuration.md>), [MikroTik_Quick_Guide](<../../quick-start.md>).
