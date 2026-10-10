---
type: operations-report
status: running-pilot
updated: 2026-09-14
---

# Возобновление сбора TimeWeb

## Результат

14 сентября 2026 запущены `vpn-uplink-pilot.service` и
`vpn-uplink-exporter.service`. Интервал 120 секунд, retention 7 дней.
Пять последовательных циклов: 10 записей, Cenuta и Fornex UP.
SQLite quick_check OK, HTTP metrics доступен на `127.0.0.1:19106`.
Память cgroup: collector около 18.4 MiB, exporter 11.5 MiB; перезапусков 0.
Это короткая проверка запуска, не длительная production-приемка.

## Изменения и защита маршрутизации

- Свежий audit и новый manifest; добавлены ровно 22 local-only guard rules
  с приоритетами 31000-31021. Состояние `VALID generation=8`.
- BTH recovery принимает два полных хешированных RPDB inventory:
  исходный и исходный с этими 22 правилами. Частичные наборы, посторонние
  изменения и поврежденные reference-файлы отклоняются.
- Существующие маршруты и клиентские правила сохранены. Проверены пути
  BTH, домашнего Fornex и домашнего Cenuta; VPN-службы не перезапускались.
- BTH HTTPS smoke до и после: HTTP 200, выход `5.18.237.241`.
- Захват 180 секунд, заголовки 96 байт: wg1 134 пакета, wg-up-cenuta 207,
  eth0 0, kernel drops 0. Фильтр охватывал WG source и TCP443/DNS53;
  это не универсальное доказательство отсутствия утечек всех протоколов.
- Автоматический rollback на 15 минут был вооружен перед изменениями
  и отменен после успешных проверок. BTH recovery timer продолжает работать.

## Master и резервные копии

Master: `services/monitoring/timeweb-uplinks` и `services/transport/timeweb-reality`.
Evidence и точный rollback: `services/monitoring/timeweb-uplinks/resume-20260914`.
На сервере: `/root/vpn-monitoring-resume-20260914`.

- Полный backup конфигурации:
  `.local/backups/timeweb/2026-09-14T135811Z_current-config/backup.tar.gz`.
  SHA256 `e7075ccbf5e80fa6a3710efb26600afb91a6cb189a4dc80fed3f223e0fcd1cab`.
  Проверены 323 файла и изолированное восстановление 28 обязательных файлов.
- Дополнительный `resume-20260914/monitoring-before.tar.gz` содержит runtime,
  состояния и историю до запуска. SHA256
  `d1d0e69f9ffb4dfa91f0819f9d4c95818f7b0485fb73fda837359de3e9d9872f`.
  Изолированная SQLite-проверка OK, 80 прежних записей.
- `acceptance.json`, `capture-summary.json`, `change-plan.json` содержат
  проверенные результаты и точный состав изменений.

Установленные `storage.py` и `exporter.py` намеренно оставлены без новых
изменений SQL sync; их копии сохранены как `installed-storage.py` и
`installed-exporter.py`. Остальной проверенный код соответствует master.
Локальные тесты collector прошли; maintenance/preflight/backup suite: 80 passed.

## Ограничения

Все оставшиеся ограничения зарегистрированы как P1: [TimeWeb_Monitoring_Backlog](<../reference/TimeWeb_Monitoring_Backlog.md>).

Автозапуск collector/exporter **disabled**. Guards runtime-only: reboot или
пересоздание namespace требует нового audit/manifest. Expiry DNS не отключен.
WG/firewall ABA не превращен в универсальный generation monitor.
Не проводились reboot, длительный baseline и полная клиентская приемка.
Mac Grafana/Prometheus/SSH forwarding этим шагом не запускались.
Автоматическая подкачка серверной SQL-истории на Mac не включена.

Инструкция просмотра: [TimeWeb_Uplink_Pilot_Quick_Guide](<../operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).
