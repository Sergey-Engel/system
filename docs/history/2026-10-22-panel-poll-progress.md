# Прогресс Опроса Панели4.2.0

22 октября 2026. Пользователь разрешил полосу по завершённым этапам,
название исполняемого этапа со спиннером и прошедшее время. Очередь и ошибки
отдельно, без таймерного увеличения заполнения. Router policy RU4.1.0,
Direct controller3.1.0, рабочие SSTP/WireGuard/Xray и device modes не меняются.

## Этапы И Состояния

Пять одинаковых по весу частей реального capture:

1. Checking Direct SSTP: существующие source/peer проверки Direct.
2. Reading router configuration: source connect/identity и export.
3. Validating router configuration: строгая сверка правил/baseline, включая pending review.
4. Reading devices and assignments: reservations/Wi-Fi, справочник имён, memberships.
5. Checking route readiness: действующие route/interface/server proof checks и сборка view.

Начало следующей части подтверждает завершение предыдущей. Пятая считается
завершённой только после возврата общего результата. Время ожидания не
изменяет completed. Внутри длительного этапа движется только спиннер.
100% означает завершение опроса, а не100% работоспособность каналов.

До входа в capture, в том числе при ожидании общего mutex/controller flock,
показывается отдельное Waiting for another check or operation; текущего
исполняемого этапа в очереди нет. При ошибке сохраняется последняя доказанная
доля, спиннер останавливается, ошибка выводится отдельно. Сбой progress endpoint
показывается отдельно от основного результата: данные не выдумываются и новый
опрос автоматически не запускается. Завершённый/прерванный read останавливает
timers; существующие строки/ошибки действий не стираются фоновым Refresh.

## Контракт И Границы

Основной GET получает случайный `X-Routing-Poll`32hex; отдельный GET
`/routing-progress/{id}` читает только process memory. Он не берёт shared
controller lock и не запускает SSH, probes или новый capture. Final JSON
добавляет poll_progress только при таком header. Старые GET и POST сохранены.
Статусы queued/running/complete/error; поля site,completed,total,stage,
elapsed_seconds,queue_seconds. Никаких exception strings/секретов в ответе.
Неизвестный id404, неверный400, повторный409, заполненный registry429.
Хранилище ограничено64 jobs; terminal записи удаляются через300s.
Restart facade очищает эту временную телеметрию, но не device state.

Ожидающие coalesced GET могут получить общий завершённый результат без
повторного исполнения этапов. Это настоящий результат общей проверки, не
заполнение по таймеру и не устаревший TTL-cache. Следующий отдельный Refresh
по-прежнему выполняет свежую проверку. Progress относится только к read,
а не к операциям Apply/Undo; их CSRF/revision/rollback проверки не меняются.

## Проверки

Unit/HTTP tests: время не увеличивает completed; queue наблюдаема при занятом
controller mutex; последовательность этапов проверяется; ошибки не дают100%;
регистрация/TTL/capacity/id/Host guards; progress endpoint не вызывает execute.
Controller fixture проверяет реальные пять callback и отсутствие route writes
для обеих площадок; drift останавливает callbacks до устройств/routes.
Browser regression: queued0/5, текущий этап/спиннер, неподвижный fill при росте
времени,1/5 и3/5, отдельный observation error, terminal failure без100%,
успешный явный Retry, остановка timers, desktop/mobile без overflow и POST.

## Deployment И Живой Опрос

Первый полный suite:692 passed,47.95s. После заключительной правки условия
success и читаемости dispatch прошли71 focused tests и финальный полный
повтор:692 passed,48.15s. Repository validator PASSED:514 public files,
67 profiles,22 devices;problems=[].

Перезапущена только локальная `com.sergey.sstp-panel`; SSH-forward, серверные
VPN/monitoring/recovery units и RouterOS конфигурации не менялись.
Живой read Нахимова4.2.0 показал0/5 ->1/5 ->2/5 ->3/5 ->4/5 ->5/5.
Финальное время27.16s, все7 устройств доступны в списке. Второй одновременный
GET наблюдался в queued0/5 в течение26.39s и получил тот же checked_at,
без повторного capture. Максимальная задержка отдельного progress GET0.194s
при занятом общем controller lock. Хеши всех трёх device-assignment state
сохранились; POST не отправлялся. Реальная проверка отказов VPN не выполнялась.
Private receipt: `.local/backups/panel-progress/20261022T063546Z/accepted.json`.

В пользовательской вкладке проверены очередь, завершение5/5, затем новый
явный Refresh. Сохранён настоящий исполняемый этап4/5 со спиннером и27s
elapsed: `.local/backups/panel-progress/current-stage.png`. Это не макет.
Название и spinner находятся под полосой; старые строки остаются видимыми,
но все route selectors/Apply/Undo заблокированы до окончания чтения.

Локальная release metadata4.2.0 синхронизирована с canonical store вместе
с read-only receipts: VERIFIED,3685 files,370 records. Состав и результат свежей configuration backup
сохраняются только в private verification.json. Полные exports, credentials,
backups и screenshots не публикуются в Git.

Свежая local configuration backup:
`.local/backups/local/2026-10-22T064000806582Z_current-config/`, VERIFIED.
1022 исходных файла плюс свежий read-only export Нахимова в06:40:12 UTC;
1023 файла пробно восстановлены и сверены. Все67 профилей сохранены;
TimeWeb container identity/image/PID/namespace/start прежние. Это не disk image
и не восстановление на живом хосте. Router/VPN service configuration не менялась.
Итоговый diff whitespace check и repository validator прошли; progress metadata
и backup остаются в закрытом `.local`.

## Уточнение UI4.2.1: Скрытие После Успеха

По запросу владельца блок прогресса целиком скрывается через20 секунд после
успешного чтения без ошибки состояния. Под Refresh остаётся зелёное Updated
со временем checked_at из ответа, не временем скрытия. Полная локальная дата
доступна в tooltip. Это подтверждение чтения, не исправности каждого VPN:
готовность каналов по-прежнему показывается отдельно.

Новый опрос или выбор площадки отменяет предыдущий таймер и зелёную отметку.
HTTP-ошибка или error в результате не скрываются автоматически и не получают
зелёного подтверждения. Таймер не делает запросов. Правила разрешения Apply,
ручного восстановления и существующие назначения не изменены.

Browser regression сначала воспроизвёл отсутствие нового поведения, затем
проверил видимость на19,999ms и скрытие на20,000ms, неизменный timestamp,
повторный опрос, смену площадки, HTTP503/error в JSON и отсутствие лишних GET/POST.
Проверены desktop1280 и mobile390 без горизонтального переполнения.
Полный suite:693 passed,65.51s. Repository validator PASSED,problems=[];
canonical store VERIFIED:3685 files,370 records, release metadata4.2.1.
Перезапущена только локальная facade. RouterOS/TimeWeb/VPN не изменялись;
свежая копия выше относится к4.2.0, новая копия конфигурации роутеров для
этой UI-правки не создавалась. Коммит и push в рамках уточнения не выполнялись.

В текущей пользовательской вкладке реальный опрос завершился за48s:
7 устройств, пустой error, Updated9:51:22 AM. После ожидания более20 секунд
полоса/счётчик/этап исчезли; отметка сохранила исходное время и зелёный цвет
rgb(133,212,124). Screenshot только локально:
`.local/backups/panel-progress/collapsed-success-421.png`.
