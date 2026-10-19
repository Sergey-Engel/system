# Нахимова → Фетхие: обратный Direct SSTP

Дата: 19 октября 2026. Контроллер 2.0.0.

## Объём

По поручению пользователя автономно установлено обратное управление выходом
в Internet через Фетхие. Используется существующий постоянный SSTP с mutual
TLS; второй tunnel/PPP connection не создавался. Transport, сертификаты,
Deco, TimeWeb и прежний forward egress не изменялись. Реальных устройств
Нахимова не переключали; MacBook Air оставлен Local/Фетхие.

Исходные serial `HM20B6QXS8H` / `HKM0BDXYG74` и strict baseline проверены.
DHCP `defconf` на bridge; подсети `.89/24` и `.88/24` соответственно.
Обратный owner `s2s-sstp-reverse-v1`; таблица `sstp_fethiye`, default через
`sstp-direct-out`, blackhole254 без fallback в main/TimeWeb.

13 per-device controls: guard любого публичного non-SSTP выхода, IPv6 forward
и IPv6 DNS block, mangle exemption перед legacy VPN marks, DNS TCP/UDP53,
узкие flow exceptions и source-specific routing rules. SNAT Нахимова
ограничен публичными назначениями `.88/24` -> `.64.2`. Это не расширяет
private management доступ через существующие router-originated SSTP exceptions.
Fethiye scoped accept/masquerade выпускает `.64.2` только в WAN; private
destinations и новые LAN-to-LAN разрешения не добавлены.

## Панель

Та же [локальная панель](http://127.0.0.1:19118/#site-to-site), вкладка Direct
SSTP. Направления имеют отдельные dropdown/selected lists, сообщения операций,
state/generation/revisions/audit. Общий lock защищает обе стороны от гонок.
Строго проверяются конфигурации и зарегистрированные device rules обоих
направлений. Legacy forward endpoints сохранены; reverse endpoints:
`/s2s-reverse-state`, `/s2s-reverse-action`. CSRF, Origin, Host, ограничение
размера запроса и pinned SSH identity не ослаблялись.

Нет фонового обновления. Переключение направления не отправляет Add/Remove;
ошибки сохраняются отдельно до закрытия или новой команды. После неудачи
ответ использует durable state. Initial SSH retry не повторяет записи.

## Проверки

- Preflight и свежие encrypted binary backups обеих сторон VERIFIED_TRANSFER;
  sensitive exports и пароли только private store, не публичный репозиторий.
- Точный additive diff проверен; Safe Mode на обоих роутерах удерживался
  до строгой проверки candidate controllers и подтверждённого commit.
- ICMP: 5/5 обычных и 5/5 DF1400 в каждом направлении.
- Router-originated HTTPS Нахимова -> SSTP -> WAN Фетхие: HTTP301.
  Output mark40 packets, Fethiye scoped exit41 outbound/29 inbound packets.
- Изолированный отказ: отключён только новый reverse default; активен
  blackhole distance254. Свежий Netwatch результат down, failed0 ->1.
  Общий SSTP при этом up; forward/TimeWeb не отключались.
- После enable свежие HTTPS проверки снова up/301; временные объекты удалены,
  device states не менялись. Увеличение failed до2 относится к ограниченному
  окну отрицательного теста, не скрыто как непрерывный успех.
- TimeWeb persistent/runtime/interface identity совпали с pre-snapshot;
  runtime/BTH/monitoring contracts PASS. Recovery policy не публиковалась:
  baseline update not required. Все67 VPN profile bytes сохранены.
- Два новых валидных collector cycles для Fornex и Cenuta; Prometheus
  подтверждает freshness/probe validity и timestamps, Grafana health OK.

## Исправление Проверочного Инструмента

До первого Netwatch замера `done-tests` может быть null. Первая проверка
остановилась на сравнении null с числом; это не доказательство сбоя канала.
Добавлен regression guard: нужен новый числовой counter и явно up/down,
unknown не считается отрицательным результатом.

После enable RouterOS7.24.4 явно сериализовал `disabled=no` в новом default,
тогда как исходный add его не выводил. Доказан единственный семантически
эквивалентный diff, временные объекты отсутствовали. Только эта новая строка
принята в local baseline; чужой drift не подписывался. Builder теперь явно
задаёт disabled=no. Повторный полный отрицательный тест прошёл с точным undo.

## Граница Приёмки

Реальный клиент Нахимова недоступен для проверки, как заранее указал
пользователь. Поэтому физический клиентский MAC/DHCP/DNS/FastTrack/IPv6,
публичный IP браузера и скорость не объявляются принятыми. Add/Remove и
ошибки проверяются автоматическими controller/HTTP/browser fixtures;
маршрут и useful HTTPS проверены с самого роутера.

`/tool fetch` запрещён текущим device-mode Нахимова; ограничение не менялось.
Проверка внешнего IP через fetch не выполнялась. Перезагрузка/restore drill
не проводились. Persistent RouterOS configuration сохранена, SSTP работает
без панели; автоматического failover между транспортами нет.

## Evidence И Откат

Основной private changeset:
`.local/backups/site-to-site/20261019T115624Z-sstp-reverse/`.
Содержит pre-backups, full exports, exact command lists, Safe Mode transcripts,
candidate/installed state, HTTPS/MTU/fail-closed readback, observability и UI
evidence. Финальные paths/counts добавляются в completion receipt.

Финальный gate: 571 tests passed; repository validation PASSED,468 public
files/67 profiles/22 devices, problems=[]. Portable store VERIFIED.
Live UI в headless Chrome: оба направления up, desktop1280x900 и mobile390x844
без overflow/page errors, POST не выполнялись, возврат в VPN-раздел успешен.
В Нахимова видны3 online DHCP-клиента, выбранных0. Обновлённые sensitive
masters обеих площадок и новые encrypted post-backups VERIFIED_TRANSFER:
`.local/backups/site-to-site/20261019T121519Z-sstp-reverse-post/`.
После установки старые hub/LAN пути и direct DF1400 получили по5/5 ответов
с каждой площадки. Браузер пользователя принудительно не обновлялся;
новые controls появятся при следующей загрузке страницы.

Откат обратного направления: сначала подтверждённый Remove его клиентов;
затем удаление только exact reverse namespace и `sstp_fethiye`, восстановление
согласованных local baseline/state. Forward namespace, SSTP/PPP/PKI и
TimeWeb не удалять. Не применять общий restore/flush/reboot.

[Эксплуатация](../operations/Direct_SSTP.md),
[план и итоговые gates](../tasks/PLAN-sstp-reverse-egress.md).
