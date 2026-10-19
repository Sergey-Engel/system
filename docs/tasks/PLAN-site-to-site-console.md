---
type: plan
status: in-progress
created: 2026-10-17
updated: 2026-10-17
tags: [mikrotik, site-to-site, console]
---

# PLAN: Управление Межплощадочным Выходом

Статус: In Progress. Пользователь согласовал отдельную вкладку существующей
VPN-панели, dropdown устройств и выбранный список с удалением; исполнение
разрешено сообщением «делай». Направление первого этапа: Фетхие -> Нахимова.

## Задачи

| # | Задача | Приоритет | Зависимость | Статус | Завершение |
| --- | --- | --- | --- | --- | --- |
| 1 | Текущая панель, SSH/topology, сохранение baseline и changeset | P0 | Нет | Аудит выполнен; live baseline Нахимова недоступен | Нет |
| 2 | Guarded multi-device controller и отрицательные тесты | P0 | 1 | Готово локально: 33 теста и повторное security review PASS | 2026-10-17 |
| 3 | Вкладка, статусы, dropdown и список, HTTP/browser тесты | P1 | 1 | Готово локально: HTTP и Chrome desktop/mobile PASS | 2026-10-17 |
| 4 | Scoped доступ и deployment без перевода устройств в Remote | P0 | 2, 3 | Заблокирован: нет SSH/S2S доступа к Нахимова | Нет |
| 5 | Console sandbox, contracts, мониторинг, masters и backups | P0 | 4 | Не начат | Нет |
| 6 | Ограниченный тест MacBook с клиентским подтверждением | P0 | 5 | Не начат | Нет |

## Контекст

[Исходный план](PLAN-fethiye-site-to-site.md), [egress changeset](../architecture/Site_to_Site_Egress_Changeset.md),
[ограниченный outage](../history/2026-10-17-egress-fail-closed.md).
Нынешний preset поддерживает только `.89.197`. Добавление произвольного
клиента требует собственных source/MAC guards, DNS/IPv6 policy, flow и return
rules; отображение списка само по себе не является настройкой маршрута.

## Контракт

- Тоннель постоянно сконфигурирован. Выбор устройств независим от его состояния.
- Только bound DHCP-клиенты bridge Фетхие, не Deco и не весь VPN-каталог.
- Новое устройство Local, Add сохраняет Remote, крестик возвращает Local.
- IP закрепляется существующей DHCP-службой без смены адреса/gateway/DNS.
- Сохраненные правила действуют независимо от браузера/компьютера оператора.
- Remote без пути блокируется; никаких скрытых local fallback.
- Status различает transport, route readiness, сохраненный выбор и read-back;
  running/handshake не называются клиентской HTTPS-приемкой.
- Устаревший выбор/конфигурационный drift/неоднозначный lease отклоняются.
- Все изменения сериализованы; intent сохранен до записи; ошибка не должна
  снимать guards и открывать Local незаметно.

## Deployment И Проверки

TimeWeb выполняет фиксированный controller с pinned SSH trust и отдельными
ключами управления роутерами внутри WG; пароли/старые ключи не ротируются.
Fethiye принимает только TCP 22 с hub `.60.1` на S2S интерфейсе. Отдельные
учетные записи не получают sensitive/policy/reboot прав. Расширение доступа
отдельно фиксируется, не подменяется старым ICMP-only договором.

При генерации host guard SSH-разрешения вставляются только в input/output;
одноименные terminal drop в forward не являются management anchors.
При сравнении export разрешенное снятие disabled flag нормализует только
концевые пробелы строки, но сохраняет все прочие параметры и порядок.

Crash safety: выбранное устройство не исчезает из списка до read-back Local.
Незавершенный Add остается явно Pending (это не обещание fail-closed до
подтверждения guards); его можно продолжить или отменить. Перед DHCP-записью
используется заново прочитанный MAC/IP/server/ID, а не сохраненный ID lease.
Make-static не меняет comment и журналируется как точное разрешенное
преобразование только выбранного lease. Unknown objects с namespace controller
не исключаются из baseline. Хешируются также позиции owned rules относительно
неизменных baseline rules; проверяется полный набор полей новых объектов.
Remove доступен при исправной Фетхие даже при недоступной Нахимова.

Дополнительные gates: сравнивать значения полей и typed flags одновременно
в rows и export, а не только допустимые имена. Для fresh/resumed preparation
проверять anchors и порядок bypass-before-client-route до закрепления хешей.
Порядок проверяется отдельно в rows и в самом export, который хешируется:
два чтения RouterOS не являются атомарным снимком.
Числовой RouterOS JSON нормализуется только для целых конечных значений.
Pending до первой сетевой записи можно отменить без conntrack очистки старого
динамического IP; не сохранять навсегда IP, который не был закреплен.

Перед сетевой записью: свежие VERIFIED backups, live identities, защищенные
host contracts и точный rollback. Тесты pure/controller/HTTP + desktop/mobile
browser. Deploy только затронутых файлов, точные console sandbox/lock paths,
namespace и HTTP read-back. Проверить BTH/monitoring/runtime отдельно; не
переподписывать неизвестный drift. Затем два свежих валидных collector cycles,
Prometheus/Grafana evidence, private store/current и post-backups.

Без клиентского подтверждения не объявлять egress принят для нового устройства.
Физический Remote-тест только MacBook и только ограниченным окном. Обратный
выход, резервный транспорт, массовая миграция и reboot не входят в этот шаг.

## Лог

17 октября: изучена действующая Python HTTP console и прежний single-client
egress. UI интегрируется без замены существующих VPN/FLEX controllers. Вопросов
к пользователю по согласованному интерфейсу нет; устройства пока Local.

Разработаны persistent controller, 17 узких per-device objects, stale revision
refusal, crash recovery, offline Remove и сохранение last-known selection при
отказе backend. Добавлены candidate sandbox/tmpfiles и обязательный backup
coverage, ничего из этого не deployed. [Подробный runbook](../operations/Site_to_Site_Console.md).
Свежие VPS backups VERIFIED: TimeWeb `2026-10-17T090825Z_current-config`,
Fornex `2026-10-17T090940Z_current-config`, Cenuta `2026-10-17T091012Z_current-config`.
Фетхие `20261017T091829Z-pre-egress` VERIFIED_TRANSFER. Попытка backup
Нахимова `20261017T092003Z` BLOCKED по недоступности; новый verified baseline
не получен. Никаких management keys/users/rules пока не создавалось.

Локальный итог: 445 tests PASS, включая 33 managed controller tests и Chrome
desktop/mobile проверки вкладки. Повторный review подтвердил отказ гонки
rows/export до закрепления хешей/enable. Фетхие сохранена в исходном Local,
все 10 controls disabled, ее export и host S2S неизменны. Live console/unit/
tmpfiles побайтово совпали с verified pre-backup; runtime/BTH/monitoring checks
PASS. Доступность самой Нахимова этими contract checks не подтверждается.
Read-only preview работает отдельно, не выполняет production controllers.
Его URL/PID хранятся в `.local/runtime/s2s-console-preview/preview.json`;
это не постоянный адрес действующей панели.
