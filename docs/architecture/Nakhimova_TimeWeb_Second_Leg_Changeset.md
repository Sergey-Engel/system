---
type: changeset
status: accepted-icmp-only
created: 2026-10-16
updated: 2026-10-16
---

# Нахимова: второе плечо к TimeWeb

## Согласованный Объем

Основание: пользователь разрешил следующий этап после принятого первого
[ICMP-пилота](Fethiye_TimeWeb_Pilot_Changeset.md). Шаг 7 разделен на 7A
(новое служебное плечо) и 7B (маршруты между LAN после проверки 7A).
Этот changeset реализует только 7A, не удаленный выход в интернет.

Нахимова: serial `HKM0BDXYG74`, hAP ax3, live RouterOS `7.24.4`.
Существующий доступ через `wg-home` сохраняется. Новое плечо:
`wg-s2s-tw`, `10.60.60.2/29`, MTU 1420, локальный UDP 51860,
endpoint `94.241.171.65:51860`, keepalive 25 s, AllowedIPs только
`10.60.60.1/32`. На TimeWeb используется уже работающий host `wg-s2s`;
ключи сервера и Фетхие не менять, интерфейс не перезапускать.

Схема: Нахимова `.2` -> TimeWeb `.1` <- Фетхие `.3`, служебная сеть
`10.60.60.0/29`. Между `.2` и `.3`, LAN и сервисами управления доступа нет.
Deco, LAN, NAT, Wi-Fi, старые VPN и default routes остаются без изменений.

## Проверки До Изменения

- TimeWeb `2026-10-16T113837Z_current-config`: VERIFIED, schema 3;
  Fornex/Cenuta также VERIFIED, отдельно от текущего changeset.
- Нахимова `20261016T114112Z`: VERIFIED_TRANSFER, encrypted binary и export;
  восстановление не выполнялось.
- Сверить текущие шесть owned-файлов с canonical master и guard; проверить
  runtime/BTH/monitoring contracts и защищенный snapshot старого `wg-relay`.
- Сверить свежий export Нахимова, serial, отсутствие нового интерфейса,
  занятого порта/адреса/chain; точный статический anchor `REALITY-B5-input`.
- Сначала RED-контроли ошибочной identity/drift/occupied scope, затем GREEN
  и dry-run nft в отдельном network namespace. При drift остановиться.

## Точные Изменения

TimeWeb: только `/etc/wireguard/wg-s2s.conf`,
`/etc/wireguard/s2s-pilot/guard.nft` и `manifest.json` того же каталога.
Добавить одного peer `.2/32`; разрешить ему только ICMP echo к `.1`.
Существующие пять остальных файлов/метаданные не менять. Заменять только
собственную nft table одной atomic transaction; не делать global flush.
Применить `wg syncconf`, без restart интерфейса или контейнеров.
Startup guard остается обязательным; периодическое восстановление еще не
настроено и относится к отдельному этапу.

Нахимова: интерфейс сначала disabled; добавить два forward drop, custom input
chain с ICMP `.1 -> .2` и final drop, input jump перед проверенным статическим
anchor, адрес и peer. Прочитать guards обратно до enable. Всего восемь owned
объектов, marker `s2s-nakhimova-20261016`. Numeric `place-before=0` запрещен.
Не менять действующие mangle/NAT/маршруты/ключи.

## Откат И Приемка

Откат только после точной сверки ownership и неизменности прочих объектов:
отключить новый интерфейс Нахимова, удалить только восемь owned-объектов;
вернуть три исходных owned-файла и собственную nft table TimeWeb, выполнить
syncconf. Не восстанавливать целиком сервер и не менять старые WG identities.

Обязательны ping в обе стороны с размером 1400, TCP negative с реальными
drop counters, сохранность первого плеча и старых контрактов. Профиль добавить
к существующему устройству `mikrotik-n11`, не создавать дубликат устройства.
Мониторинг: 67 профилей, 22 устройства, 49 наблюдаемых WG peers;
console namespace и `/state`, два свежих валидных upstream-цикла,
Prometheus и сохраненные Grafana resources. Аутентифицированный Grafana UI
без доступной сессии не считать проверенным. Свежие post-backups обязательны.

Физическая проверка MacBook подтверждает отсутствие регрессии, но не заменяет
приемку LAN. 7B получает отдельный changeset и реальные клиентские тесты.
Справка по применению без restart: [wg(8)](https://man7.org/linux/man-pages/man8/wg.8.html).

## Результат 16 Октября

Применено и прочитано обратно: три owned-файла TimeWeb, восемь owned-объектов
Нахимова. Serial/ключевые identities подтверждены; boot ID и ifindex host
интерфейса не изменились. Нахимова <-> TimeWeb ICMP по 3/3, 1400 байт;
первое плечо Фетхие также 3/3, 1400/DF. Отказ TCP подтвержден ростом host
input/output drop counters. Реальный transit из временного netns отклонен:
forward counter 0 -> 2; временные объекты удалены.

Protected snapshot, 66 уже существовавших профилей, BTH/monitoring/runtime
contracts неизменны. Console sandbox fleet 3/3 ready, HTTP `/state` без
заблокированных controls. Новые switchable controllers/locks не требуются.
Два свежих валидных upstream-цикла: `12:04:06.568741` и `12:06:08.343353 UTC`.
Prometheus: оба S2S peer свежи, присутствуют, rate-valid. Grafana: сохраненные
resources главного/detail dashboard и новое tunnel mapping Нахимова проверены
read-only; authenticated UI render не проверен.

Post-backups: TimeWeb `2026-10-16T120448Z_current-config` VERIFIED;
Нахимова `20261016T120449Z` VERIFIED_TRANSFER. Router current master и private
canonical store синхронизированы; полные конфиги/ключи не публиковались.
Evidence: `.local/backups/site-to-site/20261016T115422Z-second-leg/`.
Пользователь подтвердил HTTPS MacBook; 7A принят в ICMP-only объеме. LAN/transit остаются закрыты;
шаг 7B, reboot, восстановление из backup и удаленный Internet-выход не выполнены.
