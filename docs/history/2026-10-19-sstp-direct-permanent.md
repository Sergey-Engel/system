# Постоянный Прямой SSTP И Локальная Панель

19 октября 2026. Разрешение: постоянный прямой SSTP, управление в прежней
панели, самостоятельные проверки; рабочий канал через TimeWeb не менять.

## Применено

Namespace `s2s-sstp-direct-v1`. Нахимова `sstp-direct-out` -> TCP443
`194.61.140.217` -> сохраненный владельцем Deco forward -> Фетхие
`192.168.68.117:5443`, `sstp-direct-in`. Внутри `10.60.64.2`/`.1`,
MTU1400. Mutual TLS1.2, AES256-GCM/PFS, отдельный CA и PPP secret.
Сертификаты825 дней, предупреждение за30 дней, проверка SAN/цепочки включена.
Client enabled, add-default-route=no, keepalive10s. Конфигурация сохранена
на обоих роутерах; отсутствие панели не останавливает SSTP.

Отдельная таблица Фетхие `sstp_direct`: default через SSTP и blackhole254.
Новые scoped filters/NAT/MSS только для нового канала. Для выбранных клиентов:
MAC/IP/static DHCP, source lookup-only, DNS и IPv6/leak guards до FastTrack.
Старые WG/IPIP, LAN routes, default routes и старые selectors не менялись.
Два новых NAT rules исключают изменение старой return policy Нахимова.

Панель доступна локально на19118, вкладка Direct SSTP. VPN-раздел остается
живым содержимым прежней серверной панели через отдельный loopback-forward
19119. Серверные files/services/units/sandbox TimeWeb не разворачивались
и не перезапускались. Local facade и SSH forward запускаются двумя user
LaunchAgents после входа macOS. `timeweb-vpn` открывает эту же панель.
State/intent/audit сериализованы локальным controller и сохраняются privately.
Dropdown показывает только bound DHCP-клиентов bridge MikroTik, не Deco.

## Проверки

- Начальные ICMP5/5 и DF whole-IP1400 5/5 в каждую сторону; после отдельного
  client disable/enable ICMP снова5/5 в каждую сторону. Все30 ответов получены.
- Дополнительно к ранее принятому30min soak выполнен новый router-originated
  HTTPS egress test: ответ301, при выключенном только SSTP свежий статус down
  и failed-tests увеличился0->1, активен exact `:blackhole`, distance254;
  после восстановления свежий status up/301. У Netwatch поле HTTP code может
  сохранять прежний301 при down: вывод основан на status и новых счетчиках,
  не на одном cached code.
- Тестовый output mark дал26 packets; Nakhimova scoped Internet forward
  counters53 исходящих/51 входящий packet. Временные mark/NAT/input exception,
  Netwatch и прочие self-test objects удалены; экспорты после восстановления
  совпали с permanent baseline. Пользовательские устройства этим тестом не
  переключались. Netwatch ROS7.19 source-only проба не была принята как
  доказательство пути; окончательная проба использовала exact output mark.
- Через реальный HTTP API выполнены Add и Remove известного MacBook Air:
  `A2:C1:5E:29:F5:8E`, `192.168.89.197`, ответы success=true/true.
  Read-back Remote, затем Local; pending=false, prepared=true, selected=false.
  Это проверка controller/routing, не новый HTTPS-запрос с самого MacBook.
- Live Playwright desktop1280x900 и mobile390x844: страница не пустая,
  горизонтального overflow нет, переключение VPN/Direct SSTP работает,
  page errors отсутствуют. Скриншоты сохранены в private changeset backup.
- Два новых валидных collector cycles, Prometheus4 valid/2 fresh series,
  свежие timestamps обоих upstreams, Grafana database health=ok. Это gate
  неизмененного мониторинга, не новая SSTP-карточка Grafana.
- TimeWeb protected files/WG config/runtime/interface identity unchanged;
  runtime, BTH и monitoring contracts PASS. Recovery policy не публиковалась:
  защищаемое состояние TimeWeb не менялось.67 прежних client profiles
  сохраняют SHA-256; SSTP PKI/PPP учитываются отдельно как infrastructure.
- Локальные тесты:521 passed. Финальные encrypted backups обеих площадок:
  `.local/backups/site-to-site/20261019T102819Z-sstp-permanent-post/`,
  VERIFIED_TRANSFER (повторное чтение binary, SHA-256, export unchanged),
  masters обновлены. Старые hub/LAN paths5/5 с обеих площадок. Local launch
  bindings сохранены, Umask077; перезапущены только два локальных агента.
  Canonical store:2590 files/344 records VERIFIED после этого этапа.
- Repository validator:452 public files/67profiles/22devices, problems=[];
  diff-check clean, staging dry-run не включает private files. Live Host/Origin
  gate отклонил посторонний Origin кодом403. Прежняя серверная console active,
  MainPID92204 тот же, что до изменений. Финальный HTTP `/s2s-state`:
  available=true, SSTP up, error=null, выбранных устройств нет.
  После сохранения финального completion и scoped operator evidence canonical
  store содержит2598 files/344 records, VERIFIED; private scripts имеют mode600.

## Исправления Во Время Установки

До commit два запуска завершились exact rollback: ROS7.19 routing table
не принимала comment; пустой mangle не имеет static anchor для place-before.
При cleanup целый keepalive60.0 из JSON требовал CLI60. Третий запуск прошел
сетевые gates, но проверка удаления import files остановилась: RouterOS уже
удалила успешно импортированный файл. Все три rollback вернули exports,
certificates/trust/server settings и старые hub/LAN paths5/5 с обеих сторон.

Четвертый запуск был committed с подтвержденным выходом из Safe Mode обоих
роутеров. Построение локального metadata затем встретило многострочный source
существующего RouterOS script: shell tokenizer к чужим source lines неприменим.
Исправлена только локальная проекция: чужие строки сохраняются для hash без
tokenization; собственные объекты продолжают проверяться строго. Metadata
завершен read-only по обоим live exports/cert fingerprints и commit evidence,
без повторной установки или подписи неизвестного drift.

Первый UI Add выявил omitted default `disabled=no` в ROS export. Операция
осталась Pending; exact recovery вернул только тестовый MacBook в Local.
Исправлен implicit default, добавлена регрессия; повторные live Add/Remove
прошли штатно. Последний full suite521/521. Перезапускалась только новая
локальная facade, не службы TimeWeb. Все изменения и восстановление выполнены
без участия пользователя, без reboot/широкого restore/flush.

## Источники И Ограничения

Private scope `.local/backups/site-to-site/20261019T101232Z-sstp-permanent-v4/`:
commit transcripts, initial pings, installed.json, HTTPS/outage, live UI API,
visual evidence и observability. Свежие recent exact-baseline encrypted
pre-backups повторно проверялись перед retry; новые финальные encrypted
post-backups выполняются отдельно. Пароли, PKI, полные exports только `.local`
и canonical store. [Runbook](../operations/Direct_SSTP.md),
[infrastructure inventory](../../config/inventory/direct-sstp.json).

Физический reboot/потеря питания, throughput/нагрузка и пользовательское
приложение на MacBook не проверялись. Статус route-ready не заменяет клиентскую
HTTPS-приемку. Endpoint в SAN по IP: при смене публичного адреса Фетхие нужен
контролируемый перевыпуск и connect-to update; автоматической DDNS/renewal
системы нет. Новая конфигурация не расширяет всю Deco-сеть и не переводит
автоматически все устройства на новый выход. Итоговый выбор пустой, SSTP up.
