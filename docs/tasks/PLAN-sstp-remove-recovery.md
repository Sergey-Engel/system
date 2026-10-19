# PLAN: Незавершенный Remove И Сохраненный Выбор

Статус: Done. Дата: 2026-10-19.

| Шаг | Состояние |
| --- | --- |
| Сопоставить скриншот, audit и текущий state | Done |
| RED: незавершенный Remove не должен скрывать saved pending device | Done: 2 failed до исправления |
| Fresh saved-state response, scoped cleanup reconciliation, phase diagnostics | Done |
| Полный suite, local deploy, live HTTP read-only | Done: 558 passed, Local/state unchanged |

Скриншот относится к старому отказу19 октября14:31:51 Europe/Istanbul.
Current generation11: selected=false/pending=false, Local, status error=null.
Старый Remove завершил отключение правил, но отказал позже. Историческое
`router_command_failed` не содержит точной команды/причины.

Доказанный дефект: после disable код меняет selected=false только в памяти,
затем cleanup/read-back может отказать. Exception handler читает тот же
измененный объект, скрывая saved selected=true/pending=true из UI. Исправить
ответ при ошибке на fresh persisted state; не маскировать отказ/не clear pending.

Дополнительный воспроизводимый edge case: connection ID может исчезнуть
между print/remove. После RuntimeError выполнить только чтение: если ID уже
отсутствует, cleanup достигнут; если остался или read не удался, сохранить
ошибку/pending. Не повторять команды записи, не удалять соседние flows.
Не считать эту гонку доказанной причиной исторического отказа.

Записать phase в private diagnostic. Реальный MacBook не включать в туннель;
проверки с failing fixture, live только GET/строгий read-back. TimeWeb и
маршрутизацию не менять. Pre-edit snapshot:
`.local/backups/site-to-site/20261019T114753Z-remove-recovery/`.

Результат: [протокол](../history/2026-10-19-sstp-remove-recovery.md).
