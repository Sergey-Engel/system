---
type: configuration
status: snapshot-not-live
updated: 2026-10-24
tags: [mikrotik, routeros, bth]
---

# MikroTik hAP ax3: Нахимова 11

## Источник и свежесть

### Решение По Обновлению RouterOS: 24 Октября 2026

Live-проверка 24 октября подтвердила serial `HKM0BDXYG74`, RouterOS и
`wifi-qcom` версии `7.24.4 (stable)`. RouterBOOT current/upgrade также `7.24.4`.
Штатная проверка обновлений сообщила о доступной stable `7.25`.

По решению владельца Нахимова пока остается на `7.24.4`: дождаться выпуска
с исправлениями ветки `7.25`, затем отдельно оценить его изменения и
совместимость с действующей конфигурацией. Это не разрешение на автоматическое
обновление. Пакеты не скачивались и не устанавливались, перезагрузка не
выполнялась; VPN, маршруты и назначения устройств не менялись.

Источник новых возможностей и ограничений управления:
[официальный анонс RouterOS 7.25](https://forum.mikrotik.com/t/7-25-stable-is-released/273987).
Наличие исправляющего выпуска само по себе не является подтверждением
совместимости или отсутствия регрессий.

### Предыдущие Проверки

21 октября: SSTP до TimeWeb и два отдельных SSTP-Cenuta-RU/Fornex-RU
установлены; панель4.1.0 также исключает российские IPv4 из Direct в
провайдера Нахимова. RU accept предшествует native forced destination.
Исходные назначения сохранены, включая Direct192.168.88.28.
Transport/keys/BTH/management не переключались. [Текущая IP policy](../../operations/Panel_RU_Direct.md).
Описание19 октября ниже - исторический этап.

Итог19 октября: постоянный `sstp-direct-out` -> Фетхие TCP443,10.60.64.2,
mutual TLS/AES256-GCM/PFS, MTU1400; отдельные Internet filters/NAT/MSS.
Current master обновлен по финальному VERIFIED_TRANSFER encrypted backup.
Local VPN-панель3.0.0 объединяет маршруты: на Нахимова только permanent DHCP
reservations, Standard/Cenuta/Fornex/Direct via Fethiye; на Фетхие Wi-Fi-клиенты,
Standard/Direct via Nakhimova. SSTP остается up. TimeWeb/WG/IPIP не менялись.
[Финальный протокол](../../history/2026-10-19-sstp-direct-permanent.md).
Дополнительно установлен обратный Internet-выход через Фетхие: таблица
`sstp_fethiye`, scoped public SNAT `.64.2`, per-device управление через ту же
панель. Выбранных Direct не было при установке UI; четыре существующих
Cenuta и три Standard сохранены. Пользовательская приёмка Нахимова не
проводилась. [Протокол](../../history/2026-10-19-sstp-reverse-egress.md).
[Единое управление и ограничения](../../history/2026-10-19-unified-device-routing.md).
Следующие абзацы описывают более ранние временные пробы.

19 октября: прямой SSTP client -> Фетхие TCP443 проверен в изолированной
временной конфигурации: TLS с отказом при недоверенном CA, HTTP200,
ordinary interval1s ICMP10/10 и reconnect. Быстрые interval200ms дают timeouts;
длительная/клиентская приёмка не завершена. Все trial objects/certificates/files
удалены, export и trust совпали с исходными; старые WG/TimeWeb/NAT/routes
не менялись. Fresh encrypted backups в private trial evidence, не замена
current master: [отчёт](../../history/2026-10-19-sstp-direct-trial.md).

Позднее19 октября: отдельный30min SSTP soak PASS,305/305 ICMP и35/35 DF1400
в каждую сторону,364 новых HTTP checks без failed, три reconnect и negative CA/recovery PASS.
Все временные objects/certificates/files удалены, export/trust/server settings
исходные, старые TimeWeb/LAN paths5/5 с обеих площадок. Постоянный SSTP/egress
не включён: [полный протокол](../../history/2026-10-19-sstp-direct-soak.md).

17 октября: конфигурация Нахимова после ограниченного IPIP outage совпала
с исходным Local export; WAN/NAT/WG и остальные profiles не менялись.
Latest backup/current `20261017T084227Z`, VERIFIED_TRANSFER, без restore drill.
Remote HTTPS MacBook Фетхие после отдельной recovery-пробы `5.18.141.112`,
финальный Local `194.61.140.217`. Первый recovery LAN ping 2/3 остается
предупреждением; прежние внешние ICMP-потери также не отменены.
[Объем приемки и ограничения](../../history/2026-10-17-egress-fail-closed.md).

Дополнение live-аудита 16 октября 2026: serial `HKM0BDXYG74`, RouterOS
`7.24.4 (stable)`. Fresh export и encrypted binary backup:
`.local/backups/nakhimova/20261016T124635Z/`, VERIFIED_TRANSFER, без restore
drill. Добавлено отдельное плечо `wg-s2s-tw`, `10.60.60.2/29`,
UDP 51860 к TimeWeb `94.241.171.65:51860`, MTU 1420, keepalive 25.
Старые `wg1`, `wg-home`, `wg-cenuta`, NAT/mangle и default routes не менялись;
восемь первоначальных owned-объектов сверены с исходным export.
Последующим подшагом добавлены четыре LAN-объекта и только `.89/24` в
AllowedIPs этого peer. Main route `192.168.89.0/24` через `wg-s2s-tw`,
bridge/WG forward разрешен только между `.88/24` и `.89/24`; без NAT.
Управление через новый интерфейс закрыто, кроме ограниченного ICMP к LAN IP.
MacBook -> `.88.1` подтвержден, входящие сервисы MacBook не приняты.
[Первое плечо Нахимова](../../architecture/Nakhimova_TimeWeb_Second_Leg_Changeset.md),
[текущий LAN changeset](../../architecture/Site_to_Site_LAN_Changeset.md).
Ниже исторический смысловой обзор сентября, не полный повторный аудит всех
групп устройств по октябрьскому export.

Последующий Local-подшаг: `ipip-s2s-egress`, outer `.60.2 -> .60.3`,
inner `10.60.61.1/30`. Peer AllowedIPs добавляет только `.60.3/32`.
Return rule только WAN -> `.89.197` в отдельной table с blackhole;
LAN-initiated путь остается прежним. 29 новых owned-объектов, WAN/default,
NAT/mangle/старые WG не менялись. Post-backup `20261016T143155Z`,
VERIFIED_TRANSFER. MacBook Фетхие остается Local; при внешних ICMP-пробах
наблюдались потери, а ответы `1.1.1.1` для двух имен расходились с TLS reference.
Это не установленная причина отказа провайдера. Общий DNS Нахимова не менялся.
[Полный Local checkpoint](../../history/2026-10-16-egress-local.md).

Позднее 16 октября: ограниченная проба выхода MacBook Фетхие через Нахимова
принята по terminal HTTPS `5.18.141.112` и browser HTTPS. Возврат в Local
подтвержден `194.61.140.217`; сейчас Remote выключен. Конфигурация Нахимова
во время проб неизменна, использован прежний WAN masquerade, не новые NAT/WG.
Latest backup/current `20261016T160237Z`, VERIFIED_TRANSFER.
Отказ канала, обратный выход и постоянный режим не приняты.
[Протокол проб](../../history/2026-10-16-egress-trials.md).

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
