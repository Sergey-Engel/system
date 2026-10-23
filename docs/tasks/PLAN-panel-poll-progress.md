# PLAN: Прогресс Ручного Опроса Устройств

Дата: 2026-10-22. Статус: Done.
Разрешено: реальная полоса завершённых этапов, текущий этап со спиннером,
прошедшее время; отдельные очередь/ошибки. Только локальная панель.

| Шаг | Задача | Статус |
| --- | --- | --- |
| 1 | Read-only анализ синхронного capture и контракт прогресса | Done |
| 2 | In-memory progress, callback реальных этапов, API и focused tests | Done:67 focused tests, read-only callback, HTTP queue/error/lock tests |
| 3 | Полоса/текущий этап/спиннер/время, очередь/error и browser tests | Done:queue, real stages, fixed fill while waiting, failure, timer cleanup, desktop/mobile |
| 4 | Full suite, restart только facade, live read-only proof, документация/backup | Done:692 tests, live API/текущая вкладка, store и local backup VERIFIED |
| 5 | UI4.2.1: скрытие через20 секунд, зелёный checked_at под Refresh, ошибки/повторный опрос | Done:693 tests, validator/store VERIFIED, live UI7 devices, progress hidden and green Updated |

Пять реальных частей: Direct check; source connection/export; strict source
validation; devices/assignments; route readiness/result assembly. Процент
равен доле завершённых частей, а не прогнозу времени. 100% означает завершение
опроса, не исправность всех тоннелей. Нет таймерной прибавки к progress.
Progress endpoint не получает controller mutex/flock, не вызывает SSH и не
запускает новый capture. Нет background Refresh, маршрутных записей, VPN
restart, публикации recovery policy, commit/push без нового запроса.
