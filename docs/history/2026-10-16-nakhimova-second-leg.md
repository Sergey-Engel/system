---
type: checkpoint
status: accepted-icmp-only
created: 2026-10-16
updated: 2026-10-16
---

# Нахимова: Второе Служебное Плечо

По разрешению пользователя выполнен подшаг 7A
[общего плана](../tasks/PLAN-fethiye-site-to-site.md).
[Точный scope, результаты и rollback](../architecture/Nakhimova_TimeWeb_Second_Leg_Changeset.md).

Нахимова `HKM0BDXYG74`, RouterOS `7.24.4`: отдельный `wg-s2s-tw`,
`10.60.60.2/29`, к host `wg-s2s` TimeWeb `.1/29`, UDP 51860.
Добавлены восемь owned-объектов; сервер изменил только конфиг peers,
свою nft table и manifest. `wg syncconf` без restart. Старые ключи, LAN,
NAT, mangle, Wi-Fi, default routes и операторский Deco не менялись.

## Проверено

- Новое плечо: ping 3/3 в обе стороны, размер 1400. Первое плечо Фетхие:
  ping 3/3 с TimeWeb, 1400/DF. Интернет самого роутера Нахимова: ping 3/3.
- TCP отрицательные проверки подтверждены host input/output counters;
  реальный transit из отдельного temporary netns отклонен, counter 0 -> 2.
- Защищенный snapshot старого wg-relay, BTH/monitoring/runtime contracts
  не менялись. Их binding/generation не переподписывались. Новый startup
  guard проверен; периодическое восстановление по-прежнему отдельный этап.
- Новый профиль у прежнего устройства `mikrotik-n11`; 67 профилей,
  22 устройства, 49 WG peer observations, из них host S2S 2. Все прежние
  66 профилей совпадают побайтово и по SHA-256.
- Console namespace fleet 3/3 ready; HTTP `/state` и controls PASS.
  Новый controller/sandbox path не нужен: это не FLEX-переключаемый peer.
- Два fresh valid upstream-цикла `12:04:06.568741`, `12:06:08.343353 UTC`.
  Prometheus fresh/present/rate-valid обоих S2S peers PASS; Grafana persisted
  resources обоих dashboards и новое mapping Нахимова проверены read-only.
  Аутентифицированный UI render не проверен; credentials не сбрасывались.
- Post-backup TimeWeb `2026-10-16T120448Z_current-config`: VERIFIED,
  386 host files, 61 offline restore checks, SHA-256
  `99635b46faccfb4ab4aec65d747ff1cff03769269c781dc2d4189938e1136b61`.
- Post-backup Нахимова `20261016T120449Z`: VERIFIED_TRANSFER,
  encrypted binary дважды считан с совпадением; current master синхронизирован.
  Реальный restore и reboot не выполнялись.
- Локальные проверки: 304 tests PASS, repository/link/profile/secret scan PASS,
  private store VERIFIED (664 files, 291 records), `git diff --check` PASS.
  Тесты site-to-site добавлены в общий pytest testpaths.

## Остановки И Исправления

Первый запуск серверного сценария отказал на синтаксической проверке до
каких-либо записей. Исправлено экранирование, добавлен локальный compile
перед отправкой; повторно подтвержден точный исходный baseline.

Первое обновление inventory дало duplicate tunnel code 1 у Нахимова.
Старый code 1 сохранен, новому наблюдению назначен свободный code 2;
renderer и тесты повторно прошли, перезапущен только локальный peer probe.
Сетевая конфигурация из-за этой ошибки не менялась. Сбор данных и Prometheus
проверены после исправления; данные не подменялись ожидаемыми значениями.

## Граница Готовности

Evidence и one-shot writer: `.local/backups/site-to-site/20261016T115422Z-second-leg/`.
Технический подшаг завершен; пользователь подтвердил открытие HTTPS на MacBook
Air Sergey после этого изменения. Подшаг 7A принят в ICMP-only объеме.
LAN-to-LAN, удаленный интернет, резервный
транспорт, failover и общая приемка этапа A еще не выполнены.
