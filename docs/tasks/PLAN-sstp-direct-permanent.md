# PLAN: Постоянный SSTP И Управление

Статус: Done. Создано: 2026-10-19. Завершено: 2026-10-19.

| Шаг | Приоритет | Состояние | Зависимость |
| --- | --- | --- | --- |
| Контекст, live baseline, границы | P0 | Done | Нет |
| Guarded transport/controller, тесты | P0 | Done | Baseline |
| Backups, установка, read-back, reconnect | P0 | Done | Тесты |
| Локальная вкладка действующей панели | P0 | Done | Controller |
| Live проверки, store, masters, реестры, отчет | P0 | Done | Все выше |

## Решение И Границы

Разрешение пользователя: постоянный прямой SSTP и управление в панели,
самостоятельно. TimeWeb не менять: ни файлы, службы, firewall, маршруты,
профили, monitoring/recovery contracts. Существующий SSH proxy через него
используется только как прежний канал управления Нахимова.

Нахимова client -> TCP443 публичного адреса Фетхие -> существующий Deco
forward -> 192.168.68.117:5443. Внутри 10.60.64.0/30, MTU1400,
mutual TLS1.2/AES-GCM/PFS, отдельные CA/PPP credentials. Сертификаты 825 дней,
предупреждение в панели за 30 дней. Без отключения проверки имени/цепочки.
Публичный IP закреплен в SAN: смена адреса требует контролируемого перевыпуска,
не автоматического доверия новому endpoint. В панели показывается расхождение.
Сессия постоянна независимо от наличия выбранных клиентов; RouterOS сохраняет
конфигурацию и переподключается. Reboot не выполняется, restart persistence
проверяется конфигурационно и переподключением, не выдается за reboot drill.

Панель: локальная loopback facade сохраняет действующий VPN-раздел через
неизмененную серверную HTTP-панель и добавляет вкладку Direct SSTP. Сервер
TimeWeb не разворачивается и не перезапускается. Запуск после входа macOS
через собственный LaunchAgent. Секреты только в private store; CSRF/Host/Origin,
allowlisted действия, один writer, revision/read-back, no optimistic selection.

## Выбор Устройств

Только DHCP-клиенты bridge Фетхие. MAC+IP, статическая аренда; частный MAC
другой сети не сопоставляется по имени. Add: сначала IPv6/DNS/leak guards,
затем lookup-only в отдельной таблице; Remove: сначала остановка remote
маршрутизации, затем снятие guards. При сбое pending сохраняется; нет
автоматического перехода на TimeWeb или местный Интернет. Старые IPIP/WG,
LAN routes, default и старые remote controls не редактируются.

Новые scoped NAT на обоих концах используют внутренний адрес Фетхие,
исключая изменение существующих return policies Нахимова. Оба направления
SSTP проходят собственные forward chains до FastTrack. Доступ в чужие LAN
по новому тоннелю закрыт, management сохранен по старому пути.

## Приемка И Откат

Fresh encrypted backups, strict serial/host keys, отдельный Safe Mode на
каждом роутере; commit только после exact outside-scope diff и трафика.
Ошибки до commit: undo плюс явное удаление только новых импортированных
сертификатов/файлов. Изменения выбранных устройств сериализованы, read-back.
Проверить bidirectional ICMP/DF1400/HTTP, reconnect, fail-closed при отключенном
только SSTP, HTTP API/CSRF/браузер desktop+mobile. Клиентская HTTPS-приемка
без фактического запроса с устройства не заявляется. Два свежих monitoring
цикла, contracts и TimeWeb identity unchanged; publish policy не нужен,
если его защищаемый snapshot не изменился. Финальные backups/store verify.

Общая пропускная способность, физический reboot и поведение отсутствующих
клиентов не доказываются локальными тестами. Никаких вопросов пользователю
для штатных проверок; незавершенные gates явно фиксируются.

## Лог Исполнения

Первый запуск остановлен до включения SSTP на создании новой routing table
в ROS7.19 (параметр comment исключен). Safe Mode убрал конфигурацию;
сертификаты импортируются отдельно и удалены явно. Обнаруженная при cleanup
сериализация целого keepalive как60.0 исправлена на60 и покрыта регрессией.
Exact baseline восстановлен: exports/certificates/server settings обеих
площадок совпали, hub и remote LAN5/5 с каждой. Новая попытка имеет отдельный
private scope, fresh preflight и encrypted backups. TimeWeb не изменялся.
Focused suite44/44 перед первой установкой; compatibility suite29/29 после
исправлений. Установка нового namespace не разрешает rerun старого scope.

Итог: постоянный SSTP committed, HTTPS/outage/recovery через отдельную таблицу
прошли; live Add/Remove MacBook Air через API success=true/true, все Local.
Playwright desktop/mobile и VPN-tab PASS.521 tests, repository validator452
public files/67profiles/22devices без проблем; private store VERIFIED.
Два свежих collector cycles и все три TimeWeb contracts PASS, прежний
console MainPID92204 сохранен. Финальные encrypted backups обеих площадок
VERIFIED_TRANSFER, current masters и local launch bindings синхронизированы.
Подробнее: [финальный протокол](../history/2026-10-19-sstp-direct-permanent.md).
