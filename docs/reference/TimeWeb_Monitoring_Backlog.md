---
type: backlog
status: open
priority: high
updated: 2026-09-14
---

# Бэклог мониторинга TimeWeb

Все задачи ниже имеют **высокий приоритет P1**, статус OPEN.
Работающий пилот не означает завершенную production-приемку.
Исходное состояние: [TimeWeb_Uplink_Resume_2026-09-14](<../history/TimeWeb_Uplink_Resume_2026-09-14.md>).

| ID | Задача | Критерий закрытия |
|---|---|---|
| MON-01 | Безопасное восстановление после reboot и пересоздания namespace | Новый audit и проверенный manifest, согласованный с BTH; старый manifest никогда не применяется автоматически. Проверены reboot/recreate, отказ проверки, точный rollback и сохранность клиентского трафика. Только затем включить автозапуск collector/exporter. |
| MON-02 | Закрыть ограничения generation monitor | Доказать обнаружение временного WG/firewall ABA либо явно ограничить допустимый scope и отказывать в недоказуемой приемке; fault-injection, cleanup, deadline и поздние RST проверены. |
| MON-03 | Завершить production-приемку | Полные T01-T35, оба uplink, прикладной клиентский regression, BTH и длительный baseline с измеренными RSS/CPU/диском. Короткие UP-пробы не заменяют приемку. |
| MON-04 | Доставлять историю на Mac с догрузкой пропусков | Проверенный incremental sync с курсором, транзакциями, дедупликацией, reconnect/backoff и отображением локальной истории в Grafana; тест Mac offline/online и разрыва в середине batch. Отдельно показывать невосстановимые пропуски старше серверных 7 дней. |
| MON-05 | Подтвердить эксплуатационные границы хранилища | Измерить сутки и 7 дней с запасом, проверить prune, disk-full/corruption/clock/restart и 30-дневную синтетическую нагрузку; 30 дней теста не меняют серверный retention 7 дней. |
| MON-06 | Согласовать master и развернутые версии | Версионированный deployment manifest; явно выделить установленные storage.py/exporter.py и candidate sync. Проверить backup/restore точного runtime и обновление без потери истории. |
| MON-07 | Проверить устойчивость локального просмотра | Grafana/Prometheus/SSH reconnect после сна, перезапуска Mac и потери сети; stale/NO DATA не выдаются за отказ uplink. Проверить доступ только локально, startup и остановку компонентов. |

## Неизменяемые ограничения

- P1 MON-08 (OPEN): перенести peer-счётчики из локального SSH-пилота в
  автономный серверный collector, интегрировать 7-дневную историю и sync;
  проверить положительный трафик MacBook и сброс интерфейса.
  Текущий scope: [MacBook_WireGuard_Fornex_Monitoring](<MacBook_WireGuard_Fornex_Monitoring.md>).

- Клиентские агенты и проверка здоровья с устройств отменены пользователем.
  Не запрашивать SSH-доступ к устройствам ради мониторинга. Поле клиентского
  здоровья удалено; серверные проверки uplink сохраняются отдельно.

- DNS expiry не отключать; при DNS error не продлевать старый snapshot.
- Guards и BTH изменять только после backup и с точным rollback, без общего flush.
- Установки зависимостей и новых серверных компонентов согласовывать отдельно.
- Мониторинг uplink не доказывает работоспособность полного клиентского пути.
- До MON-04 локальный Prometheus не восстанавливает пропуски из серверной SQLite.

Связанные планы: [TimeWeb_Uplink_Monitoring_Architecture_and_Plan](<../architecture/TimeWeb_Uplink_Monitoring_Architecture_and_Plan.md>),
[TimeWeb_Uplink_History_Sync_Plan](<TimeWeb_Uplink_History_Sync_Plan.md>).
