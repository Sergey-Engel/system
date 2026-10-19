# PLAN: Ошибка Add И Обновление SSTP-Панели

Статус: Done. Дата: 2026-10-19.

| Шаг | Состояние |
| --- | --- |
| Read-only журнал и локализация | Done |
| Регрессии revision и сообщений | Done: RED, GREEN, 531 passed full suite |
| Исправление controller/UI, локальный deploy | Done: только local facade |
| Автоматическая браузерная и live read-only проверка | Done: fixture и рабочий HTTP |

В `last-error.json` ошибка `device_list_changed_refresh_and_retry`:
отказ до записи состояния/сетевых настроек. Общий revision включает весь
DHCP-список, hostname/online и lease IDs. Несвязанные изменения инвалидируют
команду для выбранного MAC. UI каждые15s перерисовывает статус и стирает
верхний текст ошибки; нижнее сообщение дублируется и остается без явного
подтверждения. Пользователь просит не обновлять окно без клика.

Исправление: per-device revision с MAC/IP/lease ID/state generation/config
identity, повторная проверка target binding перед первым write. Старый общий
revision принимается только при точном совпадении с fresh snapshot.
Action error отделяется от текущего состояния и получает понятное сообщение.
На вкладке только начальное чтение, явный Refresh и read-back после команды;
никаких фоновых обновлений/самостоятельного скрытия ошибки. Ошибка снимается
крестиком или новой явной командой. Новые зависимости не нужны.

TimeWeb, SSTP и настройки роутеров не менять. Автопроверки UI выполняются
с test fixture backend, live проверка только GET/отказ stale nonce до записи.
После исправления нельзя автоматически добавлять пользовательский ноутбук:
текущий неуспешный выбор не считается разрешением на повторную запись.
Backup существующего local controller/config/state/audit, тесты, точечный
restart только `com.sergey.sstp-panel`, HTTP и canonical store verification.

Итог: [протокол исправления](../history/2026-10-19-sstp-panel-add-fix.md).
