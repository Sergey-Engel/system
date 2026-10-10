---
type: architecture-index
status: current
topic: mikrotik
updated: 2026-09-23
tags: [mikrotik, vpn, architecture, diagrams]
parent: "[VPN_HLD](<overview.md>)"
---

## Состав схем

[HTML-индекс всех схем с превью](<diagrams/index.html>). Ссылки открывают отдельные схемы в новой вкладке, сохраняя индекс для перехода между ними.

Шесть отдельных схем показывают разные уровни решения о маршруте. Объединение их в одну картинку смешало бы транспортные связи, Linux policy routing, правила Xray и RouterOS.

1. [Транспортная топология](<diagrams/01-topology.html>): узлы, типы профилей и пути выхода в Интернет.
2. [Обычный WG на TimeWeb](<diagrams/02-wireguard.html>): маркировка RU, приоритеты `ip rule`, таблицы 100/200/300 и backend UDP/WSS для FX/CEN.
3. [REALITY: выход профиля и DNS](<diagrams/03-reality.html>): `XRAY-TW-*`, `SOCKS-TW-*`, выбор Fornex/Cenuta/BTH и общий DNS.
4. [Домашний Smart Split](<diagrams/04-home.html>): MikroTik выбирает Дом.ру, Cenuta или Fornex; backend FX/CEN может использовать UDP/WSS.
5. [BTH: передача и восстановление](<diagrams/05-bth.html>): путь через Xray и `wg-home` к MikroTik; WSS fallback на BTH не распространяется.
6. [Переключение транспорта FX/CEN](<diagrams/06-transport-switch.html>): кто принимает решение и какие endpoint меняются между native UDP и mTLS WSS.

Это самостоятельные HTML-файлы Archify. Они не требуют работающей Grafana, серверного collector или локального веб-сервера. Для интерактивного просмотра файл открывается в обычном браузере. Подписи схем русские; фиксированные элементы Viewer и атрибут `html lang` используют английский fallback.

## 1. Транспортная топология

[Открыть интерактивную схему](<diagrams/01-topology.html>).

800 (source reference not migrated)

Основной домашний путь: **устройства LAN → MikroTik → обычный WG → TimeWeb → Cenuta / Fornex → Интернет**. WG поднимает MikroTik, VPN-приложение на домашнем устройстве для этого пути не требуется. `wg-cenuta` подключается к TimeWeb UDP/51850, `wg1` к UDP/51820; домашний Smart Split отдельно может оставить трафик на прямом выходе в Дом.ру.

Вне дома TimeWeb является входом для обычного WG, `XRAY-TW-*` и `SOCKS-TW-*`. Дальше трафик уходит на Fornex, Cenuta либо домой через MikroTik. Прямой AWG 3.1 подключает устройство сразу к Fornex и не зависит от TimeWeb. Между TimeWeb и FX/CEN backend WG может прозрачно использовать native UDP либо mTLS WSS/TCP 8443. Блок «Тот же MikroTik · BTH» показывает вторую роль **того же физического роутера**, а не дополнительное устройство: он принимает BTH-трафик и выводит его через Дом.ру.

Стрелки показывают движение полезного трафика к выходу, а не сторону, инициировавшую handshake. В частности, домашний MikroTik сам поддерживает внешнюю WG-связь с TimeWeb; стрелка BTH от TimeWeb к дому не означает входящее подключение из Интернета к домашнему WAN.

Обычный WG на Fornex сохранен. Удален только старый AWG 2.0. У AWG 3.1 сейчас 11 выданных профилей, не обязательно 11 одновременно подключенных устройств.

## 2. Обычный WG на TimeWeb

[Открыть интерактивную схему](<diagrams/02-wireguard.html>).

800 (source reference not migrated)

Область схемы: сетевой namespace контейнера `wg-relay`, не policy routing хоста Xray. Входы: `wg0` (UDP 51820), `wg-clients` (UDP 51850), `wg-home` (UDP 51830).

`inet ru_bth` маркирует подходящие пакеты значением `0x30`. Это значение mark, а **190 является приоритетом правила**, направляющего их в таблицу 300. Правила 180/181 раньше него сохраняют возврат к клиентским сетям через `main`. Затем действуют legacy/selector-правила выбора таблиц 100 и 200; правило 300 направляет входящий `wg-home` в таблицу 300.

RU split назначен адресам `10.50.50.20–23` и `.26–37`. Адреса `.24`, `.25`, `.38` исключены; legacy-набор пуст. Это не универсальная политика для всех VPN-профилей. REALITY и прямой AWG ее не наследуют.

Схема сокращает список однотипных selector-правил, но не изменяет их порядок. Полная привязка клиентов: [TimeWeb_VPN_Registry](<../registry/tunnels.md>).

## 3. REALITY: выход профиля и DNS

[Открыть интерактивную схему](<diagrams/03-reality.html>).

800 (source reference not migrated)

Один host-процесс `xray-timeweb-reality` принимает TCP/443. Базовые `XRAY-TW-{FX,CEN,BTH}` выбирают один из встроенных userspace-WG outbound: `wg-fornex`, `wg-cenuta`, `wg-bth`. `SOCKS-TW-{FX,CEN}` используют тот же вход REALITY, но создают локальный SOCKS-вход в клиентском приложении; это не отдельный серверный прокси. Для FX/CEN дальнейший backend WG использует native UDP либо loopback WSS endpoint `51923/51924`; для BTH остается `wg-home` через MikroTik.

Внутреннее разрешение имен Xray общее для профилей: DoH `1.1.1.1` идет через Fornex, `1.0.0.1` через Cenuta. Разрешен DNS fallback, но это **не автоматическое переключение выхода пользовательского трафика**. Прямой DNS-запрос клиента следует выбранному outbound; внутренний DNS Xray является отдельным потоком. Для BTH произвольный DNS разрешен пользователем.

Private/reserved назначения, IPv6 и публичные адреса трех VPS запрещены общей политикой Xray. Поэтому REALITY BTH дает домашний выход в Интернет, но не доступ к приватной LAN. Подробности host/source guards: [VPN_HLD](<overview.md#защита-от-прямого-выхода>).

## 4. Домашний Smart Split

[Открыть интерактивную схему](<diagrams/04-home.html>).

800 (source reference not migrated)

Область: MikroTik hAP ax3, Нахимова 11, LAN `192.168.88.0/24`. В VPN-группах порядок обработки: локальный bypass, принудительное назначение `195.133.216.210` в выбранный туннель, RU bypass, P2P bypass для 63450–63459, затем выбранный WG. P2P-исключение проверяет source/destination port для TCP и UDP.

В `CENUTA_Devices` находятся `.35` Mac Mini, `.252` DigitalRazor, `.11` Apple TV Гостиная и `.28` Apple TV Спальня. `VPN_Devices` пуст, поэтому ветка Fornex показана пунктиром как настроенная, но без назначенных этой группе устройств. Это не означает, что сам Fornex выключен.

`CENUTA-Route` использует `wg-cenuta` к TimeWeb UDP/51850; `WG1-Route` использует `wg1` к TimeWeb UDP/51820. Затем серверные правила выводят трафик на соответствующий зарубежный VPS. Для REALITY BTH правило `REALITY-B5-main` принимает источник `10.30.30.5` с `wg-home` раньше общего split, сохраняя домашний выход.

Схема описывает конфигурацию роутера, не состояние Flow VPN или другого приложения непосредственно на Apple TV.

## 5. BTH: передача и восстановление

[Открыть интерактивную схему](<diagrams/05-bth.html>).

800 (source reference not migrated)

Путь данных: AmneziaVPN → TimeWeb Xray → userspace-WG с source `10.30.30.5` → `172.19.0.2:51830` в `wg-relay` → MikroTik `10.30.30.2` → NAT в Дом.ру. Ответ идет в обратном направлении через `wg-home` и Xray, не через зарубежный выход.

Контракт и `bth-recovery` расположены на TimeWeb host. Пунктир от recovery обозначает управление peer/guard, не передачу пользовательских пакетов. Таймер раз в 120 секунд проверяет контракт и ограниченно восстанавливает собственные объекты. При несовпадении контракта после закрепления namespace он удаляет свой peer `.5`, закрывая BTH. Даже изменение selector rules может затронуть этот контракт.

Старые обычные WG BTH-клиенты `.3–4` показаны отдельно: это не профили REALITY MacBook/iPhone. Recovery нельзя останавливать как «мониторинг». Его проверка не доказывает универсальное обнаружение временных изменений и возврата состояния (ABA).

## 6. Переключение транспорта FX/CEN

[Открыть интерактивную схему](<diagrams/06-transport-switch.html>).

800 (source reference not migrated)

Контроллер на TimeWeb получает результаты handshake, peer probe и HTTPS-проверок. Он меняет только endpoint двух backend-контуров: обычного `wg-relay` и userspace-WG внутри host Xray. В native режиме это внешние UDP endpoint Fornex/Cenuta; в запасном - локальные WSS listeners, которые ведут по mTLS WSS/TCP 8443 на соответствующий сервер.

Для Fornex переход на WSS выполняется оператором вручную. Cenuta может перейти на WSS после двух подтвержденных сбоев; возврат в native UDP всегда остается отдельным ручным действием после проверки. Клиентские имена, profiles и server identities не меняются. BTH в этот механизм не входит.

## Где расположены модули

- **TimeWeb host:** `xray-timeweb-reality`, встроенные WG outbound, общий DNS, UID firewall и WSS loopback `51923/51924` для Xray; `bth-recovery.timer` и контракт.
- **TimeWeb / Docker `wg-relay`:** обычные WG-интерфейсы, native nft `inet ru_bth`, RPDB, таблицы 100/200/300, WSS loopback `51921/51922` и BTH.
- **Fornex / Docker `wg-exit`:** WG UDP/51821, NAT и mTLS WSS server TCP/8443. **Отдельно** `fornex-awg31`: AWG 3.1 UDP/46056.
- **Cenuta host:** `wg-cenuta`, UDP/51840, NAT и mTLS WSS server TCP/8443.
- **MikroTik:** домашние WG-интерфейсы, mangle, routing tables, WAN NAT в Дом.ру.
- **Mac Mini / System:** мастер-копии схем и конфигураций. Grafana/Prometheus не участвуют в передаче туннельного трафика; в схемы данных не включены.

## Источники и границы

Базовый срез серверной конфигурации: **13.09.2026 14:45 UTC**, `services/transport/documentation-audit-20260913/live.json`; для этой редакции дополнен runtime-проверками WSS и transport controller от **23.09.2026**. Xray сверяется с `services/transport/timeweb-reality/stage9-bth/config.after`. RouterOS: свежий export **13.09.2026 16:02:58 UTC**, член `fresh-router/router-export.rsc` в backup `.local/backups/local/2026-09-13T160248153221Z_current-config/current-config.tar.gz`.

При подготовке схем из свежего RouterOS export повторно прочитаны группы устройств, mangle и маршруты. Это целевая сверка изображенных решений, не полный аудит RouterOS и не повторная проверка доступности всех туннелей. Схемы отражают конфигурационный срез, **не live-статус** и не закрывают отложенные reboot/recreate/fail-closed тесты.

Текстовые источники: [VPN_HLD](<overview.md>), [TimeWeb_Parameters](<../hosts/timeweb/TimeWeb_Parameters.md>), [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>), [VPN_Configuration_Registry](<../registry/configuration.md>), [VPN_Maintenance_and_Backup](<../operations/maintenance-and-backup.md>). Секреты, ключи, UUID клиентов и импортируемые конфиги в HTML/PNG не включены. Публичные IP и структура внутренней сети оставлены для эксплуатационного смысла; это не материал для открытой публикации без дополнительной редакции.

## Мастер-копии и проверка

Мастер JSON, HTML-индекс, инструкции пересборки и receipts в System (source reference not migrated). HTML и контрольные PNG находятся рядом с этой заметкой в `diagrams/`. Сгенерированные HTML схем не редактируются вручную: изменение начинается с JSON, затем повторяются validate, deliver и browser check. Индекс является отдельным статическим HTML; его мастер хранится в System, опубликованная копия совпадает побайтно.

Для каждого из шести HTML выполнены детерминированная и автоматическая браузерная проверки; дополнительно вручную просмотрены обновленная REALITY и новая transport-схема:

- Детерминированная приемка Archify `architecture`, профиль `showcase`: **9/9**, ноль ошибок и предупреждений композиции.
- Автоматическая проверка Chrome: **passed**, без выхода за viewport 1440×900, 1600×1000, 1920×1080 и 2048×1320; светлая/темная темы сняты на обоих крайних размерах.
- Визуальный просмотр контрольных PNG для `03-reality` и `06-transport-switch`: **passed**, проверены маршруты, подписи, блоки, нижняя область и читаемость. Для остальных схем текущая приемка ограничена Archify и Chrome visual-check.

HTML-индекс проверен отдельно: шесть ссылок, двенадцать превью, наличие локальных файлов и побайтное совпадение с мастер-копией. Проверки Archify `9/9` относятся к схемам, а не к индексу; отдельная браузерная приемка индекса не выполнялась.

Точные SHA-256 JSON/HTML и область проверок: delivery-receipts.json (source reference not migrated). Исходные браузерные receipts `*.visual-check.json` рядом с HTML намеренно содержат `visualReview: pending`: автоматический инструмент не выдает визуальное заключение. Результат отдельного просмотра указан в delivery receipts. Ручная проверка поиска, focus/passport и экспорта через встроенный браузер не выполнена: доступ к `file://` отклонен его политикой; это не переопределяет успешно полученные ранее Chrome receipts.
