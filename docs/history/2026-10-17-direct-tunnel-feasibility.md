# Прямой туннель: самостоятельная проверка 17 октября 2026

## Результат

**DIRECT_TRANSPORT_NOT_QUALIFIED.** Между роутерами возникал прямой
криптографический обмен и отдельные ICMP echo replies, но устойчивую передачу
получить не удалось. Постоянный прямой канал не включён; вся тестовая
конфигурация удалена. Ранее работающая схема через TimeWeb сохранена.

[План и ограничения](../tasks/PLAN-site-to-site-direct.md).
Проверки выполнены агентом без участия владельца и без переключения клиентов.

## Свежие условия

- Сверены обе ранее закреплённые SSH identities и serial роутеров.
- Нахимова: WAN `10.12.20.168/22`, private адрес за NAT провайдера.
- Фетхие: WAN `192.168.68.117/24` за операторским Deco.
- На обеих площадках отсутствуют глобальные IPv6/default IPv6.
- ZeroTier не установлен; на Нахимова также запрещён device-mode.
- На Нахимова device-mode `home` запрещает scheduler, fetch, sniffer,
  bandwidth-test и traffic-gen. Эти ограничения не изменялись.
- Эти факты не доказывают конкретную реализацию NAT, причину фильтрации
  или необходимость изменения тарифного плана провайдера.

## Два ограниченных сетевых эксперимента

| Тест | Состав | Наблюдение |
| --- | --- | --- |
| Новый независимый WG socket | Новые временные WG keys, UDP 51971/51972, `10.60.62.0/30`; внешние mappings получены packet capture на TimeWeb | Нахимова 3/5 echo replies в первой серии; Фетхие 0/5. Ещё четыре серии: 0/5 в обе стороны |
| Существующие поддерживаемые UDP sockets | По одному новому `.62` peer на существующем `wg-s2s-tw`; endpoints площадок, не TimeWeb; прежние peers не менялись | Mutual handshake и ненулевой RX; Нахимова 2/5 echo replies в первой серии, Фетхие 0/5. Ещё четыре серии: 0/5 в обе стороны; RX затем перестал расти |

Во втором тесте current endpoint IP/port на обоих peer совпадали с mappings
другой площадки во всех пяти сериях. TimeWeb не получал peer/AllowedIPs или
маршрута для `.62/30`: relay не подменял прямой тест. Первые echo replies
Нахимова имели RTT приблизительно 122-136 ms. Это не тест скорости.

MTU stage не запускался: условие устойчивой двусторонней передачи не выполнено.
RouterOS `print as-value` не возвращает WG runtime counters/handshake;
во втором тесте они прочитаны явным `get`, отсутствие поля не считалось нулём.

Сетевой результат нельзя уверенно приписать NAT либо фильтрации/DPI: выполненных
наблюдений недостаточно для локализации. Краткий успешный handshake и первые
пакеты не являются эксплуатационной приёмкой.

## Защита и восстановление

- До записей: encrypted backups обоих роутеров, двойная независимая загрузка,
  checksum и exports до/после backup. Статус `VERIFIED_TRANSFER`, не restore drill.
- Первая попытка scheduler add отказала по device-mode до создания туннеля;
  это техническая остановка, не отрицательная сетевая проверка.
- Safe Mode подтверждён в отдельном 40 s lifecycle test на обоих роутерах.
  Использованы штатные login flags `+ct160w40h`, пустой ввод для поддержания
  control session и лимит 300 s. По завершении Ctrl+D выполнял полный undo.
- Ошибки терминальной совместимости и boolean syntax ping исправлялись только
  после cleanup и сверки baseline. Они не считаются отказами прямого канала.
- Разрешались только тестовые ICMP адреса. Forward тестовой подсети и остальной
  input из неё запрещались; LAN/default routes, NAT, DNS, IPv6 и клиентские
  selectors не менялись. Управление из интернета не публиковалось.
- После каждого запуска/остановки exports обоих роутеров совпали с baseline;
  все новые интерфейсы/peers/адреса/filter rules удалены. Hub S2S files,
  runtime configuration и identity неизменны; BTH, monitoring и runtime
  recovery checks PASS. Неизвестный drift не переподписывался.
- Private evidence: `.local/backups/site-to-site/20261017T183703Z-direct/`.
  Начальные конфигурации сохранены отдельно и не перезаписаны.
- Изменений постоянной topology нет: новые entries в inventory/fleet/profile
  catalog не добавляются; baseline/policy publication не требуется после
  доказанного полного отката. Финальные collector/network checks сохраняются
  в том же private пакете; см. раздел ниже.

## Что нужно для постоянного прямого канала

Предпочтительный следующий вариант — доступный входящий UDP на одной площадке:
согласованный проброс одного порта Deco к MikroTik при публичном WAN, либо
публичный WAN на Нахимова с проверкой UDP. Это меняет ограничения текущей задачи
и не выполнено без отдельного разрешения. Покупка услуги провайдера не делалась.

Альтернатива — отдельно квалифицированный NAT traversal transport. ZeroTier на
Нахимова сейчас требует package/device-mode изменений с физическим подтверждением;
не установлен и не представлен как доступный автономный обход.

Управление устройствами через панель остаётся отдельным локальным кандидатом;
этот эксперимент не развёртывал его. Постоянный Remote, автоматический direct/
TimeWeb failover, холодный старт, reboot/restore и клиентские приложения здесь
не принимались. Автоматические часовые проверки остаются на паузе.

## Финальные проверки

- Нахимова -> TimeWeb, gateway Фетхие и WAN gateway: по 5/5 без потерь.
- Фетхие -> TimeWeb, gateway Нахимова и Deco: по 5/5 без потерь.
- Все 67 существующих profile files совпали с закреплёнными checksum.
- Два новых валидных collector cycles после cleanup, timestamps растут;
  все freshness/probe validity values равны 1 для обоих upstream.
- Prometheus: 4/4 valid HTTPS observations, 2/2 fresh upstreams, актуальные
  last-cycle timestamps. Grafana `/api/health`: database OK; новый Direct
  dashboard/его coverage не заявляются, поскольку такой transport не оставлен.
- Повторный полный локальный suite: **454 tests PASS**. В финальном pure
  builder фильтры привязываются к первому статическому объекту, не к dynamic
  FastTrack dummy; это не дополнительный live deployment.
- Private store: **VERIFIED**, 1267 files / 315 records. Repository validation
  **PASSED**: 424 public files, 67 profiles, 22 devices, 1267 private files,
  `problems=[]`; secrets/public boundaries не менялись.
- `git diff --check` чистый; staging dry-run не включает `.local`. Ничего не
  добавлено в index, commit/push не выполнялись; посторонние изменения сохранены.
- Private оператор закрыт (`closed.json`), повторение завершённых live шагов
  запрещено без нового scoped changeset. Clock/check automation не возобновлялась.

## Первичные источники

- [RouterOS WireGuard](https://manual.mikrotik.com/docs/virtual-private-networks/wireguard/).
- [RouterOS Safe Mode и console login options](https://manual.mikrotik.com/docs/management-tools/console/).
- [RouterOS Scheduler](https://help.mikrotik.com/docs/spaces/ROS/pages/40992881/Scheduler).
- [RouterOS Device-mode и физическое подтверждение](https://help.mikrotik.com/docs/spaces/ROS/pages/93749258/Device-mode).
