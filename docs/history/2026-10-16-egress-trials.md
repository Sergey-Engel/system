---
type: checkpoint
status: bounded-trial-accepted-local
created: 2026-10-16
updated: 2026-10-16
---

# MacBook Фетхие: Пробы Выхода Через Нахимова

## Результат

Ограниченный Local -> Нахимова -> Local принят пользователем на MacBook Air
Sergey. Сейчас Local, все 10 Remote controls выключены. Только его прежний
DHCP lease `192.168.89.197` стал static; IP/MAC/gateway/DNS не менялись.
Deco, Wi-Fi, остальные клиенты, общие defaults/DNS и все 67 профилей сохранены.
Шаг 8 [плана](../tasks/PLAN-fethiye-site-to-site.md) остается In Progress:
это приемка одного направления IPv4/HTTPS, не постоянного Remote или отказов.

## Две Пробы

Время Europe/Istanbul, 16 октября 2026:

| Проба | Наблюдение | Приемка |
| --- | --- | --- |
| 18:27-18:34 | Первая Remote-проба; автоограничение 420 s вернуло Local. Пользователь сообщил браузерный IP `194.61.140.217` и до, и после | Не пройдена; причина расхождения не установлена |
| Между пробами | Пользователь подтвердил `gateway: 192.168.89.1`, interface `en0`, IP `.89.197`; явно разрешил повтор | Подтверждена принадлежность тестового клиента |
| 18:49-18:55 | Свежий terminal `curl -4 --noproxy '*' --max-time 20` к HTTPS api.ipify.org с уникальным query дал `5.18.141.112`; обычная TLS-проверка не отключалась | Remote IPv4/HTTPS подтвержден |
| Вторая Remote-проба | `example.com` с уникальным query открылся в браузере, пользователь ответил «Да, открывается» | Browser HTTPS подтвержден |
| После явного Local | Такой же terminal HTTPS-запрос с новым query дал `194.61.140.217` | Возврат Local подтвержден |

`5.18.141.112` совпал с текущим аутентифицированным UDP endpoint Нахимова,
наблюдаемым TimeWeb. Сам UDP endpoint не заменяет HTTPS-проверку: ее результат
получен отдельно от пользователя. Первый браузерный результат не объявляется
доказанным кэшем, proxy или ошибкой пользователя. Более ранний буквальный ответ
`164.61.140.217` сохранен в истории; текущий `194.61.140.217` подтвержден новой
командой, без исправления исходных свидетельств задним числом.

## Технические Границы

Создан новый scoped writer: ровно 10 typed controls с закрепленными RouterOS
IDs, exact export comparison до/после, отдельно exact static binding.
Все прочие строки конфигурации обязаны совпадать с одобренным baseline.
Remote включает guards первыми, Local снимает их последними; conntrack
очищается только для выбранного адреса. Общий flush не применялся.
Ограничитель 420 s работает на компьютере агента, не в RouterOS scheduler.
Он не является автономным резервированием при выключенном компьютере агента.

До переключения исправлены два способа чтения CLI: ping печатает таблицу
и summary, quoted regex требует `\$`. До их исправления Remote не включался.
Pure tests покрывают неполный/дублирующийся scope, чужой path, внедрение в ID,
нетипизированный flag, границу exact export и порядок mode commands.

На обоих роутерах наблюдались IPIP forward counters и соединения от `.89.197`;
Нахимова видел source-NAT и ответные пакеты. Это подтверждает сетевой путь,
но не заменяет пользовательскую проверку приложения. Drop counters сохранены,
не обнулялись. Последующий Local read-back и inner pings 3/3 прошли.
На Фетхие теперь 25 owned-объектов, на Нахимова 29; static binding сохраняется
при Local. Device-mode/fetch/scheduler/sniffer и старые WG identities неизменны.

## Closure И Backups

Runtime/BTH/monitoring/pilot checks прошли. Старый protected snapshot и весь
S2S host state неизменны: policy/manifest re-sign, service restart и новые
контроллеры не требовались. В console mount namespace все 3 routes ready;
HTTP controls доступны. Unit совпал с current master, tmpfiles с точной
verified pre-change копией: отдельного materialized tmpfiles master не было,
он не создавался для сокрытия отсутствующего источника.

После последнего Local подтверждены два новых stored collector cycles:
оба upstream fresh=1, все четыре probes valid=1, clocks растут, latest valid.
Prometheus видит два S2S peer с правильными device/role mappings. Оба Grafana
ресурса проверены через read-only persisted storage; authenticated UI render
не проверялся, WG telemetry не выдается за IPIP/application health.

Один HTTP-срез показал Cenuta DEGRADED, controls оставались доступны.
Срез сохранен; следующая проверка показала UP без изменения конфигурации.
Это не выдается за исправление причины. Старые внешние ICMP-потери Нахимова
также остаются предупреждением.

| Post-backup | Verified snapshot |
| --- | --- |
| TimeWeb | `2026-10-16T155615Z_current-config`, 386 host files / 61 offline checks |
| Fornex | `2026-10-16T155731Z_current-config` |
| Cenuta | `2026-10-16T155758Z_current-config` |
| Фетхие | `20261016T160037Z-post-egress`, VERIFIED_TRANSFER |
| Нахимова | `20261016T160237Z`, VERIFIED_TRANSFER |

Router current/master/private store синхронизированы; initial Фетхие неизменен.
Encrypted RouterOS backups сверены при переносе; live restore не выполнялся.
Private evidence: `.local/backups/site-to-site/20261016T152005Z-remote-trial/`
и `20261016T154744Z-remote-trial-02/`; точные отчеты и исполненный writer там.
Повторные read-only ping readings, попавшие под имена первой пробы, сохранены
во второй; два исходных sealed receipt восстановлены из canonical bytes,
с журналом SHA. Это исправление размещения evidence, не роутерной настройки.

Локально: 359 tests PASS, включая 38 egress tests. Public repository PASS:
411 public files, 67 profiles, 22 devices; private store VERIFIED: 1072 files,
308 records на момент основной closure. Последующие validation receipts могут
увеличить только число private evidence files. Diff check и public staging dry-run
прошли, `.local` не попадал в staging. Публикация/commit не выполнялись.

Не приняты: controlled fail-closed outage, IPv6-negative test на клиенте,
прикладная нагрузка, throughput/loss SLA, постоянный режим, обратный egress,
автоматический резерв, reboot и restore. Следующий подшаг: отдельно объявленная
проба потери только пилотного удаленного пути, без изменения Deco/старых VPN.
