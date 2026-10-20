# PLAN: Независимый SSTP Нахимова — TimeWeb

Статус: Blocked, кандидат безопасно отключён. Дата: 2026-10-20.
Это результат первой попытки. Последующее согласованное обслуживание и
успешный новый endpoint описаны в [отдельном плане](PLAN-timeweb-maintenance-newip-sstp.md).
Разрешение: пользователь поручил автономно поднять SSTP на отдельном порту,
не менять рабочие WireGuard/Xray, пока без автоматического переключения.

## Контракт

- Отдельный исходящий SSTP client Нахимова и Linux SSTP server TimeWeb.
- Новый свободный TCP-порт; TCP443/Xray, существующие WG peers/routes,
  контейнер `wg-relay`, прямой SSTP Фетхие и пользовательские списки не менять.
- Отдельные identity, PKI, PPP credentials, адреса и owned namespace/units.
  Строгая проверка сертификатов; неизвестный drift не переподписывать.
- Нет default route, LAN forwarding, изменения Cenuta/Fornex/BTH и failover.
  Готовый параллельный транспорт проверяется изолированным трафиком; перенос
  существующих пользовательских маршрутов и UI переключатель — отдельный этап.
- Новые owned фильтры могут разрешать только тестовый ICMP/HTTPS/SSH между
  двумя концами. Публичный management порт роутера не открывать.
- Если isolation требует изменения старых служб/guard contracts вне точного
  additive diff, остановить этот вариант и выбрать более узкую схему.

## Шаги

| Шаг | Задача | Приоритет | Статус |
| --- | --- | --- | --- |
| 1 | Live read-only audit, source/dependency research, fresh verified backups | P0 | Done |
| 2 | Exact changeset/isolation, tests, rollback and certificates | P0 | Done |
| 3 | Guarded additive deployment without old transport restarts | P0 | Выполнен тестовый deployment; затем точный откат роутера и отключение новых служб |
| 4 | Bidirectional ICMP/MTU/useful traffic, negative auth/reconnect/soak | P0 | Базовые тесты PASS; длительная приёмка FAILED, см. протокол |
| 5 | Monitoring/contracts/no-touch proof, post backups, masters and docs | P0 | Копии/документы и no-touch proof выполнены; общий runtime gate не принят |

## Блокировка

На TimeWeb 1 vCPU, 2 ГБ RAM: load 14–28, доступно около 70 МБ,
у containerd-shim существующего wg-relay почти 9000 потоков. Полная
проверка recovery непостоянна/завершается тайм-аутом. Для обслуживания этой
проблемы может потребоваться работа с существующим Docker/WG, что выходит
за разрешённый объём. Эти службы не перезапускались и не перенастраивались.
Постоянный SSTP и автоматическое переключение не включены.
[Протокол и текущее безопасное состояние](../history/2026-10-20-sstp-timeweb-candidate.md).

## Приёмка

Сохранённые exact pre/post снимки persistent/runtime, WG keys/AllowedIPs,
routes/firewall и process/container identities. Новая PKI/сервер и автозапуск
только собственного SSTP сервиса, не автоматический выбор маршрута.
Длительное окно с полезным трафиком и счётчиками; проверка новых handshake
после reconnect и отказ при недоверенном CA/неверном PPP credential.
Нет принятия по одному handshake; реальные пользовательские устройства не
переключать. Два свежих валидных monitor cycles и независимые BTH/monitoring/
runtime contracts; неизвестный drift сохранять, не делать publish ради UP.
Fresh verified backups и синхронный canonical private store, no secret output.

## Откат

Сначала выключить только новый SSTP client. Удалить только exact owned router
objects/fingerprints и новый server service/namespace/listener. Восстановить
pre-state вне своего scope и подтвердить прежний доступ по WG. Не выполнять
общий restore, reboot, firewall/route flush или restart WireGuard/Xray.
