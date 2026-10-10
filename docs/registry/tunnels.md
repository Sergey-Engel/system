---
type: registry
status: current
updated: 2026-10-10
tags: [vpn, clients, wireguard, reality, awg]
---

# Реестр VPN-туннелей и клиентских профилей

Размещение обновлено 10 октября: [clients.json](../../config/inventory/clients.json)
содержит 65 точных файлов, [observations.json](../../config/inventory/observations.json)
определяет 21 устройство для exporter/Grafana. Состав: 36 WG, 11 AWG31,
9 SOCKS и 9 XRAY. Байты опубликованных профилей не менялись. Датированные
результаты приемки ниже не выданы за повторную приемку при переносе.

## Профили по устройствам

Все выпущенные файлы для каждого устройства: **65 профилей в 21 папке**, включая одну папку без подтвержденной привязки к устройству. Наличие файла не подтверждает установку или активное подключение; сведения о приемке приведены в таблицах по типам VPN ниже.

Папки указаны относительно `.local/clients/`. Полный путь складывается из папки и имени файла. Обозначения протоколов, выходов и `RUHOME` расшифрованы в примечаниях ниже.

| Устройство                        | Папка                     | Все профили VPN                                                                                                                                                                                                          |
| --------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **MacBook Sergey**                | `Sergey/MacBook`          | `WG-TW-FX-S-MacBook.conf`<br>`WG-TW-CEN-RUHOME-S-MacBook.conf`<br>`WG-TW-BTH-S-MacBook.conf`<br>`AWG31-FX-S-MacBook.conf`<br>`SOCKS-TW-FX-MacBook.json`<br>`SOCKS-TW-CEN-MacBook.json`<br>`SOCKS-TW-FLEX-S-MacBook.json`<br>`XRAY-TW-FX-TUN-S-MacBook.json`<br>`XRAY-TW-CEN-S-MacBook.json`<br>`XRAY-TW-BTH-S-MacBook.json` |
| **iPhone 12 Sergey**              | `Sergey/iPhone`           | `WG-TW-FX-S-iPhone.conf`<br>`WG-TW-CEN-RUHOME-S-iPhone.conf`<br>`AWG31-FX-S-iPhone.conf`<br>`SOCKS-TW-FX-iPhone12.json`<br>`SOCKS-TW-CEN-iPhone12.json`<br>`SOCKS-TW-FLEX-iPhone12.json`<br>`XRAY-TW-FX-S-iPhone.json`<br>`XRAY-TW-CEN-S-iPhone.json`<br>`XRAY-TW-BTH-S-iPhone.json` |
| **Mac Mini M4 Sergey**            | `Sergey/MacMini`          | `WG-TW-FX-S-Mini.conf`<br>`WG-TW-FX-RUHOME-S-Mini.conf`<br>`WG-TW-CEN-RUHOME-S-Mini.conf`<br>`AWG31-FX-S-Mini.conf`<br>`SOCKS-TW-FX-Mini.json`<br>`SOCKS-TW-CEN-Mini.json`<br>`SOCKS-TW-FLEX-S-Mini.json`<br>`XRAY-TW-FX-S-Mini.json`<br>`XRAY-TW-CEN-S-Mini.json`<br>`XRAY-TW-BTH-S-Mini.json` |
| iPad Pro Sergey                   | `Sergey/iPad-Pro`         | `WG-TW-FX-S-iPadPro.conf`<br>`WG-TW-CEN-RUHOME-S-iPadPro.conf`<br>`AWG31-FX-S-iPadPro.conf`                                                                                                                              |
| iPad 9.7 Sergey                   | `Sergey/iPad-97`          | `WG-TW-FX-RUHOME-S-iPad97.conf`<br>`WG-TW-CEN-RUHOME-S-iPad97.conf`<br>`AWG31-FX-S-iPad97.conf`                                                                                                                          |
| MacBook M3 Sveta                  | `Sveta/MacBook-M3`        | `WG-TW-FX-RUHOME-V-MacBook.conf`<br>`WG-TW-CEN-RUHOME-V-MacBook.conf`<br>`AWG31-FX-V-MacBook.conf`                                                                                                                       |
| **iPhone 16 Sveta**               | `Sveta/iPhone-16`         | `WG-TW-FX-RUHOME-V-iPhone.conf`<br>`WG-TW-CEN-RUHOME-V-iPhone.conf`<br>`AWG31-FX-V-iPhone.conf`                                                                                                                          |
| iPad 9.7 Sveta                    | `Sveta/iPad-97`           | `WG-TW-FX-RUHOME-V-iPad97.conf`<br>`WG-TW-CEN-RUHOME-V-iPad97.conf`<br>`AWG31-FX-V-iPad97.conf`                                                                                                                          |
| DigitalRazor PC                   | `Other/DigitalRazor`      | `WG-TW-FX-DigitalRazor.conf`<br>`WG-TW-CEN-DigitalRazor.conf`<br>`AWG31-FX-DigitalRazor.conf`                                                                                                                            |
| Engel Samsung Pad                 | `Other/Samsung-Pad`       | `WG-TW-FX-SamsungPad.conf`<br>`WG-TW-CEN-RUHOME-SamsungPad.conf`<br>`AWG31-FX-SamsungPad.conf`                                                                                                                           |
| Win Orekhovo                      | `Other/Win-Orekhovo`      | `WG-TW-FX-WinOrekhovo.conf`<br>`WG-TW-FX-RUHOME-WinOrekhovo.conf`<br>`WG-TW-CEN-RUHOME-WinOrekhovo.conf`<br>`AWG31-FX-WinOrekhovo.conf`                                                                                  |
| Apple TV 1                        | `Other/apple-tv-1`        | `WG-TW-FX-apple-tv-1.conf`                                                                                                                                                                                               |
| Apple TV (Fethiye)                | `Other/apple-tv-fethiye`  | `WG-TW-FX-apple-tv-fethiye.conf`<br>`WG-TW-BTH-apple-tv-fethiye.conf`                                                                                                                                                    |
| Apple TV 4K                       | `Other/apple-tv-4k`       | `WG-TW-FX-apple-tv-4k.conf`                                                                                                                                                                                              |
| Apple TV Orekhovo                 | `Other/apple-tv-orekhovo` | `WG-TW-CEN-apple-tv-orekhovo.conf`                                                                                                                                                                                       |
| avg-redmi                         | `Other/avg-redmi`         | `WG-TW-FX-avg-redmi.conf`                                                                                                                                                                                                |
| anv-samsung                       | `Other/anv-samsung`       | `WG-TW-FX-anv-samsung.conf`                                                                                                                                                                                              |
| honor-lana-turk                   | `Other/honor-lana-turk`   | `WG-TW-FX-honor-lana-turk.conf`                                                                                                                                                                                          |
| mariia-mac                        | `Other/mariia-mac`        | `WG-TW-FX-mariia-mac.conf`                                                                                                                                                                                               |
| MikroTik N11 (клиентский экспорт) | `Other/mikrotik-n11`      | `WG-TW-FX-mikrotik-n11.conf`                                                                                                                                                                                             |
| Igor: устройство не определено    | `Other/Igor-Unassigned`   | `WG-TW-BTH-Igor-Unassigned.conf`                                                                                                                                                                                         |

**Правило синхронизации:** при добавлении, отзыве, удалении, переименовании, переносе или изменении назначения профиля обновлять в одной правке и таблицу по устройствам, и соответствующую таблицу по типу VPN. Набор относительных путей в обеих группировках должен совпадать без пропусков и дублей и сверяться с актуальными файлами `.local/clients`. Если меняется наблюдаемая серверная identity, адрес или направление, одновременно обновлять `config/inventory/observations.json`: из него exporter и карточки Grafana получают список устройств, адресов, identity, источников и подписей тоннелей. Отдельный клиентский режим того же REALITY identity, например `TUN` рядом с SOCKS-профилем, в inventory не дублируется. При изменении устройства или направления обновлять также подписи и связанные сведения; параметры и приемку хранить в подробных таблицах по типам VPN, не дублируя их здесь. Изменение реестра само по себе не отзывает серверный доступ.

## Источник и правила учета

Дополнение 2026-09-25: выпущен `Sergey/MacMini/SOCKS-TW-FLEX-S-Mini.json`.
На TimeWeb зарегистрированы отдельные `macmini-socks-flex` и
`10.50.50.41/32`; FLEX fleet и BTH recovery показывают готовность серверного
маршрута. Предыдущая количественная сверка ниже относится к 2026-09-23 и
не включает этот новый профиль. Импорт на Mac Mini и фактический трафик
ожидают проверки пользователем.

Сверка 2026-09-23: локальные файлы `.local/clients` и серверные peers/идентичности. **64 профиля: 36 WG + 17 REALITY + 11 AWG 3.1.** Новый `SOCKS-TW-FLEX-S-MacBook.json` использует отдельную identity `macbook-socks-flex` и WG peer `10.50.50.39/32` внутри TimeWeb; серверный выбор FX/CEN и RU-direct управляется без переимпорта. Выпущен и статически проверен 23.09, **импорт и сквозная приемка на MacBook ещё не подтверждены**. `SOCKS-TW-CEN-MacBook.json` доказан в работе 2026-09-22: отдельная server identity направляется через `wg-cenuta`, а при резервном транспорте ее WireGuard-пакеты идут через mTLS WSS `127.0.0.1:51924`. В тот же день выпущены независимые `SOCKS-TW-CEN-Mini.json` и `SOCKS-TW-CEN-iPhone12.json`; они ожидают импорта и приемки. `SOCKS-TW-FX-Mini.json` и `SOCKS-TW-FX-iPhone12.json` используют уже существующие Fornex identity соответствующих устройств, поэтому не добавляют серверный доступ; оба ожидают импорта и приемки. `XRAY-TW-FX-TUN-S-MacBook.json` использует уже существующую MacBook/Fornex REALITY identity, но его приемка на macOS не прошла: TimeWeb принял трафик, а ответ не вернулся в клиентское приложение. Профиль не использовать как рабочий. Базовый срез прежних профилей: `services/transport/documentation-audit-20260913/live.json`.

Проверка размещения файлов: **2026-09-15**, после добавления маркера `TW`
к профилям с входом через TimeWeb.
Пути в таблицах ниже относительны к `.local/clients/`.
Это обновление файлового реестра, не повторный аудит серверов и не новая приемка устройств.

## Примечания: размещение и именование

- Структура: `clients/<владелец>/<устройство>/<файл>`. Владельцы: `Sergey`, `Sveta`, `Other`.
- Для устройства используется одна папка со всеми его протоколами и направлениями.
  Примеры: `Sergey/MacBook`, `Sergey/MacMini`, `Sergey/iPhone`, `Sveta/iPhone-16`.
- Формат имени: `ПРОТОКОЛ-[TW-]ВЫХОД[-RUHOME]-УСТРОЙСТВО.расширение`.
- Протоколы: `WG` — обычный WireGuard; `AWG31` — AmneziaWG 3.1;
  `XRAY` — текущий VLESS + REALITY. `AMZ` и `WG3` не использовать:
  первое обозначает приложение, второе неоднозначно.
- `TW` — обязательный входной/relay-узел TimeWeb. Он стоит между протоколом
  и Internet-выходом и показывает, что клиент сначала подключается к TimeWeb,
  а TimeWeb или Xray на нем направляет трафик дальше. В текущем наборе `TW`
  обязателен для всех `WG` и `XRAY`; не ставится только у прямых
  `AWG31-FX-*`, которые подключаются к Fornex напрямую.
- Выходы: `FX` — Fornex, `CEN` — Cenuta, `BTH` — через MikroTik / Дом.ру.
  Это фактический выход в Интернет после входа через `TW`, а не адрес
  входного сервера: `XRAY-TW-FX` идет через TimeWeb и выходит через Fornex.
- `RUHOME` — российские направления через дом, остальные через указанный выход.
  Не смешивать с `BTH`, где весь обслуживаемый Интернет-трафик направлен через дом.
- Суффиксы `S` и `V` обозначают Sergey и Sveta. Короткое имя устройства сохраняется
  в файле, чтобы его можно было распознать после скачивания или пересылки.
- Расширения сохраняются: `.conf` для WG/AWG31, `.json` для XRAY.
  Использовать латиницу, цифры и дефисы, без пробелов.
- `TUN` после выхода резервируется для экспериментального системного режима
  Xray. `XRAY-TW-FX-TUN-S-MacBook.json` не прошел приемку в AmneziaVPN на
  macOS и не является рабочим профилем. Отсутствие этого сегмента означает
  SOCKS-профиль, который обслуживает только приложения, использующие его
  локальный proxy. Для такого профиля первый сегмент имени — `SOCKS`, например
  `SOCKS-TW-FX-MacBook.json`. `TUN` не создает новую серверную identity и не
  заменяет одноименный SOCKS-профиль.
- `Other/Igor-Unassigned` содержит прежний BTH-профиль без подтвержденной
  привязки к конкретному устройству. Не назначать его устройству по догадке.
- В `clients` находятся актуальные файлы импорта. Бэкапы, архивы, серверные конфиги
  и технические выгрузки хранятся вне этой папки. Каталоги закрытые, конфиги — секреты.
- Master-файлы в `services/transport` могут сохранять прежние имена. При публикации
  сопоставлять их с текущим путем и применять правило `TW`; не восстанавливать
  плоскую структуру `clients` и не копировать старое имя master-файла механически.
- Таблица миграции с прежними именами, текущими путями и SHA-256:
  `.local/clients-migration-20260915-tw-route-names.json`. В ней зафиксировано
  добавление `TW` к 41 профилю с входом через TimeWeb; содержимое конфигов
  не менялось. `.local/clients-migration-20260914.json` сохраняется как
  история первоначального переноса в папки. Переимпорт уже работающих
  подключений не требуется; их отображаемые имена в приложениях автоматически
  не меняются.
- Подтвержденная привязка BTH `10.30.30.3/32`: это Apple TV (Fethiye).
  Рабочий профиль перенесен в `Other/apple-tv-fethiye` без смены ключей и без
  переимпорта на телевизоре. Для MacBook Sergey 17 сентября выпущен отдельный
  peer `10.30.30.6/32` и новый `WG-TW-BTH-S-MacBook.conf`; он ожидает импорта
  и приемки на устройстве.

Примеры:

```text
clients/Sergey/iPhone/XRAY-TW-FX-S-iPhone.json
clients/Sergey/iPhone/AWG31-FX-S-iPhone.conf
clients/Sergey/MacMini/XRAY-TW-CEN-S-Mini.json
clients/Sveta/iPhone-16/WG-TW-FX-RUHOME-V-iPhone.conf
```

«Есть на сервере» не означает «устройство сейчас подключено». Все 36 WG-профилей сопоставлены с live peers по производной идентичности публичного ключа. Файлы содержат отдельные приватные ключи: импортировать только профиль своего устройства, не публиковать конфиги/QR в Obsidian.

Системные peers и MikroTik учитываются отдельно, а не как еще один клиентский экспорт. При очистке AWG2 **обычные WG-профили, включая устройства вне нового AWG-списка, не удалялись**.

## AWG 3.1: утвержденные 11 устройств

Прямой endpoint `103.75.126.143:46056/UDP`, контейнер Fornex `fornex-awg31`. Internet-выход Fornex, TimeWeb и BTH не участвуют. DNS `1.1.1.1, 1.0.0.1`, MTU 1280. В профилях `AllowedIPs = 0.0.0.0/0, ::/0`; это включение IPv6 в маршрут захвата, **не подтверждение рабочего IPv6 Internet**.

| Профиль в .local/clients | IPv4 | Приемка устройства |
| --- | --- | --- |
| `Sergey/MacBook/AWG31-FX-S-MacBook.conf` | `10.83.1.1/32` | Пользователь подтвердил работу |
| `Sergey/iPhone/AWG31-FX-S-iPhone.conf` | `10.83.1.2/32` | Пользователь подтвердил работу |
| `Sergey/MacMini/AWG31-FX-S-Mini.conf` | `10.83.1.4/32` | Перевыпущен 15 сентября; ожидается импорт и приемка на устройстве |
| `Sergey/iPad-Pro/AWG31-FX-S-iPadPro.conf` | `10.83.1.5/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Sergey/iPad-97/AWG31-FX-S-iPad97.conf` | `10.83.1.6/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Sveta/MacBook-M3/AWG31-FX-V-MacBook.conf` | `10.83.1.7/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Sveta/iPhone-16/AWG31-FX-V-iPhone.conf` | `10.83.1.8/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Sveta/iPad-97/AWG31-FX-V-iPad97.conf` | `10.83.1.9/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Other/DigitalRazor/AWG31-FX-DigitalRazor.conf` | `10.83.1.10/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Other/Samsung-Pad/AWG31-FX-SamsungPad.conf` | `10.83.1.11/32` | Выпущен; импорт и проверка на устройстве не подтверждены |
| `Other/Win-Orekhovo/AWG31-FX-WinOrekhovo.conf` | `10.83.1.12/32` | Выпущен; импорт и проверка на устройстве не подтверждены |

Адрес `10.83.1.3` принадлежал тестовому peer; он отозван. Не заполнять пропуск автоматически. Старый AWG2 и его действующие credentials удалены; закрытая retirement-копия оставлена для истории/восстановления. См. [Fornex_AWG31_Operations](<../operations/Fornex_AWG31_Operations.md>).

## REALITY: восемнадцать профилей

Вход `94.241.171.65:443/TCP`, AmneziaVPN / Xray. Пользователь подтвердил работу всех трех выходов на MacBook Sergey и iPhone Sergey. Полная матрица утечек, отказов и перезагрузок не принята.

| Файл в .local/clients | Устройство | Выход |
| --- | --- | --- |
| `Sergey/MacBook/XRAY-TW-BTH-S-MacBook.json` | MacBook Sergey | MikroTik / Дом.ру |
| `Sergey/iPhone/XRAY-TW-BTH-S-iPhone.json` | iPhone 12 Sergey | MikroTik / Дом.ру |
| `Sergey/MacBook/XRAY-TW-CEN-S-MacBook.json` | MacBook Sergey | Cenuta |
| `Sergey/iPhone/XRAY-TW-CEN-S-iPhone.json` | iPhone 12 Sergey | Cenuta |
| `Sergey/MacBook/SOCKS-TW-FX-MacBook.json` | MacBook Sergey | Fornex; локальный SOCKS, переименован 2026-09-22 без изменения содержимого |
| `Sergey/MacBook/SOCKS-TW-CEN-MacBook.json` | MacBook Sergey | Cenuta; отдельная Reality identity, локальный SOCKS; принято в работе 2026-09-22 через WSS резерв |
| `Sergey/MacBook/SOCKS-TW-FLEX-S-MacBook.json` | MacBook Sergey | Серверный выбор Fornex/Cenuta и RU-direct; отдельная Reality identity и WG peer `10.50.50.39/32`; локальный SOCKS; выпущен 2026-09-23, путь FX/CEN и RU-direct проверен временным Xray с этим JSON, импорт и приемка в AmneziaVPN на MacBook не подтверждены |
| `Sergey/MacBook/XRAY-TW-FX-TUN-S-MacBook.json` | MacBook Sergey | Fornex; экспериментальный системный TUN, приемка 2026-09-22 не прошла, не использовать |
| `Sergey/iPhone/XRAY-TW-FX-S-iPhone.json` | iPhone 12 Sergey | Fornex |
| `Sergey/iPhone/SOCKS-TW-FX-iPhone12.json` | iPhone 12 Sergey | Fornex; локальный SOCKS, использует существующую iPhone/Fornex identity, выпущен 2026-09-22; ожидает импорта и приемки |
| `Sergey/iPhone/SOCKS-TW-CEN-iPhone12.json` | iPhone 12 Sergey | Cenuta; отдельная Reality identity, локальный SOCKS, выпущен 2026-09-22; ожидает импорта и приемки |
| `Sergey/iPhone/SOCKS-TW-FLEX-iPhone12.json` | iPhone 12 Sergey | Общие Gateway и RU-direct с индивидуальными исключениями `Default`/явное значение; отдельные identity `iphone12-socks-flex` и WG peer `10.50.50.40/32`; серверный маршрут проверен, импорт и клиентский трафик ещё не подтверждены |
| `Sergey/MacMini/XRAY-TW-BTH-S-Mini.json` | Mac Mini M4 Sergey | MikroTik / Дом.ру; выпущен, ожидается импорт и приемка |
| `Sergey/MacMini/XRAY-TW-CEN-S-Mini.json` | Mac Mini M4 Sergey | Cenuta; выпущен, ожидается импорт и приемка |
| `Sergey/MacMini/XRAY-TW-FX-S-Mini.json` | Mac Mini M4 Sergey | Fornex; выпущен, ожидается импорт и приемка |
| `Sergey/MacMini/SOCKS-TW-FX-Mini.json` | Mac Mini M4 Sergey | Fornex; локальный SOCKS, использует существующую Mac Mini/Fornex identity, выпущен 2026-09-22; ожидает импорта и приемки |
| `Sergey/MacMini/SOCKS-TW-CEN-Mini.json` | Mac Mini M4 Sergey | Cenuta; отдельная Reality identity, локальный SOCKS, выпущен 2026-09-22; ожидает импорта и приемки |
| `Sergey/MacMini/SOCKS-TW-FLEX-S-Mini.json` | Mac Mini M4 Sergey | Общие Gateway и RU-direct с индивидуальными исключениями `Default`/явное значение; отдельные identity `macmini-socks-flex` и WG peer `10.50.50.41/32`; серверный маршрут `ready` 2026-09-25, импорт и клиентский трафик не подтверждены |

Это JSON для импорта в AmneziaVPN, не конфигурация обычного WG. Имя `Server1` в приложении можно менять без смены серверной идентичности. Встроенный DNS общий для REALITY-выходов; BTH не предоставляет доступ к домашним приватным подсетям. Детали: [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>).

## Обычный WG: legacy, 15 профилей

Endpoint `94.241.171.65:51820/UDP`, интерфейс `wg-relay/wg0`; источники `10.10.10.0/24` направляются в таблицу 100. В срезе native RU-list для legacy пуст.

| Файл в .local/clients | IPv4 | Выход | RU split на TimeWeb |
| --- | --- | --- | --- |
| `Other/DigitalRazor/WG-TW-FX-DigitalRazor.conf` | `10.10.10.6/32` | Fornex | Нет |
| `Sergey/iPhone/WG-TW-FX-S-iPhone.conf` | `10.10.10.7/32` | Fornex | Нет |
| `Sergey/iPad-Pro/WG-TW-FX-S-iPadPro.conf` | `10.10.10.10/32` | Fornex | Нет |
| `Other/Samsung-Pad/WG-TW-FX-SamsungPad.conf` | `10.10.10.13/32` | Fornex | Нет |
| `Other/apple-tv-1/WG-TW-FX-apple-tv-1.conf` | `10.10.10.14/32` | Fornex | Нет |
| `Other/apple-tv-fethiye/WG-TW-FX-apple-tv-fethiye.conf` | `10.10.10.15/32` | Fornex | Нет |
| `Other/Win-Orekhovo/WG-TW-FX-WinOrekhovo.conf` | `10.10.10.17/32` | Fornex | Нет |
| `Other/apple-tv-4k/WG-TW-FX-apple-tv-4k.conf` | `10.10.10.18/32` | Fornex | Нет |
| `Sergey/MacMini/WG-TW-FX-S-Mini.conf` | `10.10.10.20/32` | Fornex | Нет |
| `Other/avg-redmi/WG-TW-FX-avg-redmi.conf` | `10.10.10.21/32` | Fornex | Нет |
| `Other/anv-samsung/WG-TW-FX-anv-samsung.conf` | `10.10.10.22/32` | Fornex | Нет |
| `Other/honor-lana-turk/WG-TW-FX-honor-lana-turk.conf` | `10.10.10.23/32` | Fornex | Нет |
| `Other/mikrotik-n11/WG-TW-FX-mikrotik-n11.conf` | `10.10.10.24/32` | Fornex | Нет |
| `Sergey/MacBook/WG-TW-FX-S-MacBook.conf` | `10.10.10.25/32` | Fornex | Нет |
| `Other/mariia-mac/WG-TW-FX-mariia-mac.conf` | `10.10.10.26/32` | Fornex | Нет |

Apple TV (Fethiye) подтвержден пользователем по активному BTH peer `10.30.30.3/32`; это не вывод по порядковому имени файла.

## Обычный WG: selector, 18 экспортов

Endpoint `94.241.171.65:51850/UDP`, интерфейс `wg-relay/wg-clients`. RU split подтвержден native nftables `inet ru_bth`; таблица 100 дает Fornex, 200 Cenuta, mark `0x30` направляет RU в таблицу 300 / BTH.

| Файл в .local/clients | IPv4 | Выход для остального Internet | RU split на TimeWeb |
| --- | --- | --- | --- |
| `Sergey/iPhone/WG-TW-CEN-RUHOME-S-iPhone.conf` | `10.50.50.20/32` | Cenuta | Да |
| `Sveta/iPhone-16/WG-TW-CEN-RUHOME-V-iPhone.conf` | `10.50.50.21/32` | Cenuta | Да |
| `Sergey/MacBook/WG-TW-CEN-RUHOME-S-MacBook.conf` | `10.50.50.22/32` | Cenuta | Да |
| `Sergey/iPad-Pro/WG-TW-CEN-RUHOME-S-iPadPro.conf` | `10.50.50.23/32` | Cenuta | Да |
| `Other/DigitalRazor/WG-TW-CEN-DigitalRazor.conf` | `10.50.50.25/32` | Cenuta | Нет |
| `Sveta/MacBook-M3/WG-TW-CEN-RUHOME-V-MacBook.conf` | `10.50.50.26/32` | Cenuta | Да |
| `Sveta/MacBook-M3/WG-TW-FX-RUHOME-V-MacBook.conf` | `10.50.50.27/32` | Fornex | Да |
| `Sveta/iPhone-16/WG-TW-FX-RUHOME-V-iPhone.conf` | `10.50.50.28/32` | Fornex | Да |
| `Sveta/iPad-97/WG-TW-CEN-RUHOME-V-iPad97.conf` | `10.50.50.29/32` | Cenuta | Да |
| `Sveta/iPad-97/WG-TW-FX-RUHOME-V-iPad97.conf` | `10.50.50.30/32` | Fornex | Да |
| `Sergey/MacMini/WG-TW-CEN-RUHOME-S-Mini.conf` | `10.50.50.31/32` | Cenuta | Да |
| `Sergey/MacMini/WG-TW-FX-RUHOME-S-Mini.conf` | `10.50.50.32/32` | Fornex | Да |
| `Other/Win-Orekhovo/WG-TW-CEN-RUHOME-WinOrekhovo.conf` | `10.50.50.33/32` | Cenuta | Да |
| `Other/Win-Orekhovo/WG-TW-FX-RUHOME-WinOrekhovo.conf` | `10.50.50.34/32` | Fornex | Да |
| `Other/Samsung-Pad/WG-TW-CEN-RUHOME-SamsungPad.conf` | `10.50.50.35/32` | Cenuta | Да |
| `Sergey/iPad-97/WG-TW-CEN-RUHOME-S-iPad97.conf` | `10.50.50.36/32` | Cenuta | Да |
| `Sergey/iPad-97/WG-TW-FX-RUHOME-S-iPad97.conf` | `10.50.50.37/32` | Fornex | Да |
| `Other/apple-tv-orekhovo/WG-TW-CEN-apple-tv-orekhovo.conf` | `10.50.50.38/32` | Cenuta | Нет |

Дополнительно в серверном срезе есть peer MikroTik `10.50.50.24`, без отдельного текущего экспорта в `.local/clients`. Он не входит в RU-list данного среза. Таким образом в срезе `wg-clients` содержит 19 peers при 18 клиентских файлах.

## Обычный WG BTH: три экспорта

Endpoint `94.241.171.65:51830/UDP`, DNS в файлах `192.168.88.1`. Это прежний WG BTH, не REALITY BTH.

| Файл в .local/clients | IPv4 | Выход | RU split |
| --- | --- | --- | --- |
| `Other/apple-tv-fethiye/WG-TW-BTH-apple-tv-fethiye.conf` | `10.30.30.3/32` | Дом.ру / BTH | Нет |
| `Other/Igor-Unassigned/WG-TW-BTH-Igor-Unassigned.conf` | `10.30.30.4/32` | Дом.ру / BTH | Нет |
| `Sergey/MacBook/WG-TW-BTH-S-MacBook.conf` | `10.30.30.6/32` | Дом.ру / BTH | Нет, ожидает импорта |

Еще два peer `wg-home`: MikroTik `10.30.30.2` и встроенный WG outbound Xray `10.30.30.5`. Всего live `wg-home` содержит 5 peers.

## Служебные связи

| Узел | Интерфейс / peer source | Роль |
| --- | --- | --- |
| TimeWeb wg-relay | `wg1 / 10.20.0.1` | Обычный WG uplink Fornex |
| Fornex wg-exit | Peers `10.20.0.1`, `10.20.0.3` | Старый relay и REALITY |
| TimeWeb wg-relay | `wg-up-cenuta / 10.40.40.2` | Обычный WG uplink Cenuta |
| Cenuta wg-cenuta | Peers `10.40.40.2`, `10.40.40.3` | Старый relay и REALITY |
| TimeWeb Xray | `10.30.30.5` | REALITY BTH |
| MikroTik | `10.30.30.2` | Домашний WG peer и BTH Internet-выход |

## DNS, IPv6 и принятие изменений

В большинстве прежних WG-экспортов DNS `1.1.1.1, 8.8.8.8`, в WG BTH домашний DNS. IPv6-адреса и `::/0` встречаются в конфигурациях, но наличие этих строк не является приемкой IPv6, fail-closed или отсутствия утечек.

При выдаче/отзыве синхронно проверять: серверный peer, persistent config, локальный master, опубликованный файл в .local/clients и этот реестр. Новый файл не означает установленный профиль. Удаление локального файла не отзывает серверный доступ.

Подробности хранения: [VPN_Configuration_Registry](<configuration.md>). Создание обычного WG: [TimeWeb_Client_Creation](<../operations/TimeWeb_Client_Creation.md>). Архитектура: [VPN_HLD](<../architecture/overview.md>).
