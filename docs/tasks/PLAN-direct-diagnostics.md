# PLAN: Локализация Обрыва Direct

**Дата:** 2026-10-18. **Разрешение:** самостоятельные проверки; рабочий TimeWeb не менять.

## Контракт

Новый закрываемый one-shot кандидат, не повторение старых mutating actions.
Отдельный `wg-direct-diag`, `.62.1/.62.2`, порты 51971/51972 только после
свежего identity/baseline/namespace check и encrypted backups двух роутеров.
Deco forward/reservation сохраняются. TimeWeb используется только как
существующий SSH management transport и источник read-only статуса, без
изменения peers/config/routes/firewall/services/contracts.

До эксперимента: совпадение masters и exports, свободный namespace, версии,
device-mode, logging и connection-tracking read-back. Обе Safe Mode сессии,
без takeover, таймер 300 s и Ctrl+D, менее 100 операций на каждом роутере.
Новый interface/peer/address, пять filter правил и два пассивных header log
правила (raw RX и mangle postrouting TX), ограниченные тестовыми UDP портами
и 10 packets/s. Никакого packet payload, global logging changes или sniffer.
Пользовательские маршруты, NAT, DNS и режимы устройств не меняются.

## Гипотезы И Различающие Проверки

- RX с неожиданного публичного IP: смена NAT address против source allowlist.
- Есть TX, нет RX на другом WAN: потеря между WAN точками наблюдения, не
  ошибка маршрута внутреннего ICMP. Отдельно проверить наблюдаемый endpoint.
- Есть RX, нет роста peer RX: firewall/аутентификация/состояние WG.
- Peer RX растёт, ICMP нет: внутренние маршруты/filters/rp-filter/AllowedIPs.
- На отдельном peer после воспроизведения изменить только keepalive 25 -> 1 s:
  A/B короткого idle timeout; не менять оба транспорта сразу.
- Если обрыв вне роутеров: не называть конкретного оператора/DPI без
  разделяющего контроля. Дополнительные контролируемые пробы планировать по
  полученным пакетным данным, не перезапускать закрытый кандидат вслепую.

## Шаги

| # | Шаг | Статус |
| --- | --- | --- |
| 1 | Разобрать последний failure и подготовить безопасные observer tests | Done: 27 focused tests PASS |
| 2 | Fresh preflight, backups и read-only контроль TimeWeb | Done: оба backups VERIFIED_TRANSFER |
| 3 | Воспроизведение с TX/RX headers и keepalive A/B | Done: TX продолжается, WAN RX остановился; 1s не помог |
| 4 | Undo, exact exports/hub/profiles, старые пути, contracts | Done для всех трёх scope: baseline exact, старые пути 5/5 |
| 5 | Два fresh collector cycles, документированный вывод и оставшиеся границы | Done: monitoring/Prometheus/Grafana PASS; store VERIFIED |

## Разделяющий Контроль После Первой Локализации

Первый диагностический кандидат закрыт. Новый кандидат `wg-direct-path`,
owner `s2s-direct-path-20261018`, Нахимова UDP51973, затем только смена своего
listener на 51974 с сохранением keys/peer/address. Фетхие UDP51972 неизменен.
Проверяются свободные дополнительные порты, новые backups и исходный baseline.
Те же guards/изоляция/undo. Header prefixes DP-, чтобы исключить старые логи.

После воспроизведения потери: три нейтральных UDP-пакета с существующего
Fornex SSH к тому же forwarded UDP51972 (без открытия listener/config changes
на Fornex); UDP traceroute Нахимова -> тот же порт, count1/max24/timeout100ms.
Это контроль доступности Deco/направления для другого источника и не-WG UDP,
не проверка WG authentication. Затем смена только тестового исходного UDP-порта:
возобновление или невозобновление передачи отделяет stale tuple от keys/routes.
Никаких изменений TimeWeb. Конкретный оператор/DPI не выводится из одного
отрицательного контроля. Новые scope/rules удаляются и baseline проверяется.

Финальный контроль без WG-кандидата: на Фетхие только один временный passive
raw logger UDP51972, owner `s2s-neutral-control-20261018`, prefix NC-. Нахимова
отправляет SNMP GET к тому же публичному порту: `tries=16 try-timeout=1s`.
Ответ SNMP не ожидается и SNMP server не включается. Это 16 нейтральных UDP
пакетов одной исходной socket/tuple, чтобы сравнить с 7 входящими WG packets.
Нахимова и TimeWeb не меняются. Safe Mode/backup/undo/точная сверка прежние.
Успех одностороннего контроля сам по себе не отличает DPI от всех вариантов
ошибки двустороннего upstream NAT; точный middlebox без внешней трассы не утверждать.

## Итог

Потеря локализована между postrouting TX и remote raw RX. На каждом свежем
WG flow проходит начальный обмен, затем RX прекращается; исходящий TX и
локальный conntrack остаются активны. Смена только source port даёт новый
краткий успех. Нейтральный UDP: 3/3 с Fornex и 16/16 одной tuple из Нахимова.
Вероятна внешняя избирательная фильтрация WG; DPI против upstream NAT/SPI
окончательно не различены. Новый транспорт/постоянный fix не развёртывался.
Все тестовые scope закрыты, TimeWeb unchanged, старые пути 5/5, 67 profiles
unchanged; полный suite 476 PASS. Repository validation PASSED, `problems=[]`.
[Отчёт](../history/2026-10-18-direct-path-diagnosis.md).
