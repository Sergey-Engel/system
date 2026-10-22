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
Полный suite, deployment и live read-only результаты фиксируются ниже.
