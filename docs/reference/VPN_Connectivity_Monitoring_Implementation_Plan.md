---
type: implementation-plan
status: partial-implementation-acceptance-pending
topic: vpn-connectivity-monitoring
created: 2026-08-17
updated: 2026-09-13
tags:
  - monitoring
  - grafana
  - prometheus
  - wireguard
  - operations
source:
  - "[VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>)"
  - "[Восстановление_доступа](<Восстановление_доступа.md>)"
---

## Статус

Это план оставшейся приемки, **не инструкция заново установить существующий стек**.
Local master уже содержит probe, Compose и Grafana/Prometheus provisioning:
[VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>).
Порядок интерпретации и текущий статус: [VPN_Connectivity_Monitoring_Quick_Guide](<../operations/VPN_Connectivity_Monitoring_Quick_Guide.md>).

Live snapshot (source reference not migrated)
от **2026-09-13 14:45:01 UTC**: аудит не обнаружил TCP listeners на проверенных
портах 3000, 9090, 9105, 19106; 19107 не проверялся.
Пустой `local_docker` не доказывает отсутствие контейнеров: subprocess
returncode проигнорирован, stderr не сохранен. Monitoring LaunchAgents
в отфильтрованном списке не показаны. Это не подтверждение удаленного стека.
Отсутствие команды / exit 127 не означает отказ сервиса.
TimeWeb pilot/exporter отдельно подтверждены как `inactive / dead / disabled`.

Полный прежний план сохранен:
[agents/history/VPN_Connectivity_Monitoring_Implementation_Plan_Before_Review_2026-09-13](<../history/VPN_Connectivity_Monitoring_Implementation_Plan_Before_Review_2026-09-13.md>).
Его Fornex/Cenuta baseline, `utun4`, установка с нуля и обещанные WG-метрики
не применяются автоматически к текущему Mac.

## Уже существует в master

- HTTP host probe `127.0.0.1:9105`, выполняющий пробы по запросу.
- Prometheus job Mac: scrape **10 s**, timeout **8 s**, retention **30d**.
- Grafana dashboard VPN Connectivity с пятью панелями.
- Отдельный TimeWeb job: scrape **30 s**, dashboard pilot.
  Его серверные пробы **120 s**, SQLite policy **7 дней**.

Наличие файлов не закрывает deployment, startup, retention, runtime equality
или клиентскую приемку. В этом ревью тесты/пробы не запускались.

## Этап 1. Полный read-only baseline

После отдельного разрешения на operational-проверку:

1. Получить код возврата и stderr для Docker, listeners и launchd.
   Различать CLI отсутствует, daemon недоступен, контейнер отсутствует,
   контейнер остановлен и приложение не отвечает.
2. Проверить существующие файлы, агенты и процесс 9105, не создавать второго probe.
   Проверить 3000/9090/9105/19106 и отдельно candidate 19107.
3. Сверить текущие site/egress labels, маршрут к цели, public IP и транспорт.
   Не выбирать Fornex/Cenuta только потому, что так написано в старом плане.
4. Сверить local master с фактическим executable/provisioning, сохранить версии.
   Не принимать `latest` в Compose за зафиксированную runtime-версию.

Gate: результаты датированы; неизвестное отделено от отказа.
Проверка metadata маршрута не равна full-device acceptance.

## Этап 2. Сохранность до любых изменений

Проверить объем и содержимое существующей истории, согласованный backup и
восстановление в отдельное хранилище. Не удалять/переименовывать каталог данных
как способ диагностики и не использовать `down -v`.

В master live mounts остаются внутри Dropbox. План переноса за пределы
синхронизации требует отдельного разрешения и проверенного восстановления.
Серверная SQLite 7 дней и Mac Prometheus 30d являются разными хранилищами.
Ни один retention-параметр не гарантирует полноту фактической истории.

## Этап 3. Приемка probe

Проверить фактические ограничения, прежде чем обещать свойства раннего плана:

- `/metrics` запускает пробы и может отвечать дольше 8 s; отдельного cache нет.
- Curl GET/POST проверяют exit, но не ожидаемый HTTP-код и body.
- `utun` определяется обходом интерфейсов, не маршрутом к конкретной цели.
- DNS использует system resolver, не закрепленный WG resolver.
- Нет заявленных ранее WG handshake/TX/RX, error counters и last-success timestamp.
- Latency означает длительность проверки; маленький POST не тест bandwidth.

Это backlog runtime, а не исправления, внесенные документационным ревью.
Изменения collector/probe требуют отдельного решения и тестов.
Python на Mac только `python3 -B`; установки запрещены
без согласования.

## Этап 4. Согласованное возобновление и Grafana

Использовать существующий deployment, не переустанавливать стек.
Не менять VPN, MikroTik, серверы или пользовательские маршруты.
Включение уже установленной службы тоже является runtime-действием и не
разрешается автоматически этим планом.

После согласованного запуска проверить:

- target Prometheus, scrape duration/failures, свежесть результатов;
- источник и labels каждой панели; отсутствие ложного зеленого last-value;
- различие NO DATA и неуспешной сетевой пробы;
- одновременную сохранность dashboard Mac и TimeWeb;
- историю за реально накопленный период, не обещанные 30 дней.

Запрос к probe или публичной цели сам создает сетевой трафик и не является
чистым просмотром документации.

## Этап 5. Длительный baseline и ошибки

В согласованном окне сопоставить реальные симптомы с UTC-временем,
gateway/ICMP/DNS/HTTPS, маршрутом и при необходимости серверными данными.
Не переключать рабочий VPN для искусственного получения старого симптома.

Проверить gaps при выключении Mac/probe/Prometheus, restart, storage failure,
границы временного диапазона и backup/restore. Короткий обрыв 20-30 s может
быть пропущен: 10 s scrape само по себе не гарантирует detection.

Alerts, уведомления и WG telemetry не считать реализованными по старому
чек-листу. Статус Интернета нельзя выводить из одного stale handshake.

## Откат и критерий завершения

Откат касается только согласованно измененных monitoring-компонентов.
Остановка общего локального Prometheus/Grafana затрагивает оба dashboard.
Сохранить данные и provisioning, не удалять volumes и не менять VPN.

Gate завершения: известны runtime-версии, маршрут/labels, ограничения метрик,
реальное coverage, восстановимость данных и результат клиентской проверки.
Не отмечать весь план выполненным по наличию файлов или одному HTTP health.
