# Автоматическое Распознавание Имен По MAC

Дата: 2026-10-19. Установлено в local facade19118.

## Поведение

Exact full-MAC binding -> DHCP hostname -> организация IEEE -> Unknown.
Машиночитаемый [LAN inventory](../../config/inventory/lan-devices.json)
содержит14 подтвержденных/наблюденных MAC bindings из паспорта Фетхие и
истории принятого тестового MacBook. Это отдельный presentation inventory,
не дополнение к22 VPN observation devices или67 выданным профилям.

Для A2:C1:5E:29:F5:8E выводится `MacBook Air (Sergey)`, source=inventory.
Для52:EB:3F:26:E9:5A точного binding нет; locally administered bit установлен,
производитель не ищется, выводится `Unknown device (private MAC)`.
Имена и IP не используются для связывания разных MAC. Подпись не меняет
revision, selection или routing policy. Источник виден в tooltip, MAC
сохранен в dropdown/выбранном элементе. TextContent/Option исключают HTML
интерпретацию имен из DHCP/IEEE.

## IEEE Snapshot

Загружены официальные MA-L/MA-M/MA-S/IAB CSV,58 795 уникальных префиксов.
Две неоднозначные записи сохранены как блокирующие unknown: не выбирается
одна организация и не используется более короткий parent prefix.
Используется наиболее длинное совпадение36/28/24bit, но оно дает организацию,
не конкретную модель/владельца. Private/IEEE Registration Authority не
выдаются за производителя устройства.

Runtime читает только локальный cache; наружу MAC/IP не передаются.
Сетевой refresh вынесен из status/Add. Загрузка ограничена30s/source,
16MB/source, subprocess35s; HTTPS и проверка сертификатов включены.
Сбой не заменяет предыдущий cache. Snapshot `.local/cache/mac-vendors.json`
пересоздаваемый, не credential store; периодическая автоматизация не создана.
Протокол/ограничения в [runbook](../operations/Direct_SSTP.md#имена-по-mac).

Первый Python HTTPS probe не принял certificate chain окружения; проверка
TLS не отключалась. Системный macOS curl выполнил проверенный HTTPS download.
Слишком короткий15s бюджет загрузки и реальные неоднозначные IEEE записи
были выявлены до применения cache и покрыты исправлением/регрессиями.

Источники: [IEEE public listings](https://standards.ieee.org/products-programs/regauth/),
[IEEE local/universal address rules](https://standards.ieee.org/wp-content/uploads/import/documents/tutorials/eui.pdf).

## Состояние И Проверки

- RED: отсутствие resolver и отсутствие inventory name в controller status;
  отдельно воспроизведена неоднозначность реального CSV. GREEN full: **554 passed**.
- Exact/private/unknown, longest prefix, конфликт binding/cache, malformed CSV,
  ошибка download с сохранением cache, отсутствие insecure flags/MAC в URL.
- Изменение имени не меняет selection/revision и не записывает state.
- Playwright fixture включает inventory/private/длинное vendor имя; проверены
  Add/Remove fake backend, sticky errors, manual refresh, отсутствие polling.
- Live HTTP: оба имени и их source корректны, inventory/vendors ready,
  selected0/Local, tunnel up/error=null. Config не менялся, HTTP не изменил state.
- Live browser1280x900/390x844: правильные dropdown labels, page errors0,
  overflow0, router actions0. Restart только local `com.sergey.sstp-panel`.
- Canonical private store VERIFIED:2599 files/344 records.

До правок имен pre-edit snapshot уже содержал generation9, selected=true,
pending=true после неудачного Remove. Все12 controls к тому моменту были
disabled, SSTP running=true. Поэтому первоначальная проверка ожидаемого
Remote была остановлена, а не принята как успешная. Пользователь затем
выбрал обычный выход Фетхие. К моменту агентского повторного Remove уже
завершился успешный Remove generation11; guard остановил повтор до записи.
Проверены selected=false/pending=false и строгий read-back disabled controls.
Причина старого `router_command_failed` при Remove этим naming changeset
не установлена и не объявляется исправленной. Нового клиентского HTTPS/IP
замера агент не выполнял; Local подтвержден состоянием и router-side controls.

Private evidence: `.local/backups/site-to-site/20261019T113109Z-device-names/`:
pre-edit sources/config/state, `pre-deploy-verification.json` (с pending),
`live-http-verification.json` (последующий Local), live screenshots.
TimeWeb, Deco, SSH-forward и транспортные настройки при работе над именами
не менялись; names resolver не отправляет router write commands.
