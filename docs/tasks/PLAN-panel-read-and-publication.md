# PLAN: Загрузка Устройств И Публикация Завершённых Изменений

Дата: 2026-10-22. Разрешение: диагностика пустого списка и commit/push всех
завершённых изменений с исключением секретов и backups. Маршруты не менять.

| Шаг | Задача | Статус |
| --- | --- | --- |
| 1 | Воспроизведение, identity/read-only проверки и замер задержек | Done: HTTP200/7 устройств за90.9s, самостоятельный capture30.06s |
| 2 | Объединение ожидающих read-запросов без stale cache и новые tests | Done:683 tests, concurrent HTTP и browser error regression |
| 3 | Перезапуск только локальной facade, live API/browser, private backup | Done:live reads/вкладка приняты, assignments неизменны; store/local backup VERIFIED |
| 4 | Secret/staged audit, полный suite, commit/push и сверка remote SHA | In Progress:683 tests и44-file staged audit PASSED; publication |

Не менять WireGuard, SSTP, Xray, router rules/списки, selections, ключи или
recovery contracts. POST всегда выполняет собственную свежую проверку.
Новый Refresh после завершения предыдущего не должен получать TTL-cache.
