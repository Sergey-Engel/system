# Remove: Достоверное Состояние После Отказа

Дата: 2026-10-19. Local facade19118 обновлена, реальный MacBook оставлен Local.

## Что Произошло

Присланный скриншот соответствует прежнему неудачному Remove от14:31:51
Europe/Istanbul, не новому действию. Audit затем содержит успешный Remove,
current generation11, selected=false/pending=false. Live status перед правками:
error=null, оба клиента Local. Исторический diagnostic `router_command_failed`
не содержит точной команды; его низкоуровневая причина не установлена.

Найден и воспроизведен дефект отображения отказа: Remove после disable меняет
selected=false в памяти, до финального save. Если cleanup/read-back отказывает,
exception handler раньше формировал status из этого же объекта. Saved state
при этом selected=true/pending=true. Поэтому UI мог одновременно показывать
Pending и No devices selected, скрывая возможность recovery Remove.

## Исправление

Exception handler перечитывает отдельный controller из persisted state внутри
того же lock. Ответ и audit generation соответствуют файлу, без автоматического
clear pending или попытки повторной записи. Неопределенный результат по-прежнему
помечен ошибкой; generic message явно говорит о перечитанном сохраненном выборе.

Дополнительно закрыт воспроизводимый сценарий истечения connection ID между
print/remove: после RuntimeError только fresh read. Если точного ID больше нет,
требуемый cleanup подтвержден. Если остался, принадлежит другой записи или
проверка не удалась, ошибка сохраняется. Нет write retry, broad flush или
удаления соседних flows. Эта гонка не объявляется причиной старого отказа.
Private diagnostic теперь содержит phase: preflight/prepare_device/device_policy/
connection_cleanup/readback/commit/status. Секреты/полный export не выводятся.

## Проверки И Границы

- RED2 failed: непустой saved pending device скрывался; уже исчезнувший flow
  оставлял операцию неподтвержденной. GREEN focused47 passed, full **558 passed**.
- Проверены failed ID still present, исчезновение ID, unavailable recheck,
  ID в другой записи и отсутствие удаления neighbor flow/повтора write.
- Playwright fixture: failed Remove оставляет pending selected device с
  доступной кнопкой recovery; следующий явный Remove завершается. Проверены
  sticky messages/manual refresh/desktop/mobile, без реальных router writes.
- Restart только local `com.sergey.sstp-panel`. Live GET: tunnel up/error=null,
  selected0/pending0, generation11, Local. Config/state hashes совпали с
  pre-edit снимком. Реального Add/Remove в этой задаче не выполнялось.
- Canonical private store VERIFIED:2599 files/344 records.

Evidence: `.local/backups/site-to-site/20261019T114753Z-remove-recovery/`,
pre-edit sources/config/state/audit и `live-verification.json`.
TimeWeb, Deco, SSH-forward и конфигурация роутеров не менялись.
Старое уведомление в уже открытой странице остается до явного dismiss или
новой команды, как ранее запросил пользователь; status обновляется кнопкой.
