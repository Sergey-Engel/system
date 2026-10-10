---
type: implementation-log
status: backup-verified-deployment-not-approved
created: 2026-09-12
updated: 2026-09-12
parent: "[TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>)"
---

## Согласование и результат

После предложения сделать только backup/rollback preparation пользователь ответил «делай». Это **не согласование установки** Xray, новых peers/rules или запуска транспорта.

Созданы и проверены конфигурационные копии трех VPS, составлен manifest исходных объектов и порядок точечного отката: [TimeWeb_REALITY_Backup_and_Rollback](<../operations/TimeWeb_REALITY_Backup_and_Rollback.md>). Установок, новых ключей/профилей, перезапусков и правок действующей конфигурации не было. На VPS записаны только файлы резервных копий.

## LOG

1. 15:46 UTC: SSH по публичным адресам всех трех VPS подтвержден с pinned host keys. Failed units отсутствуют. TimeWeb wg-relay и Fornex wg-exit/Amnezia работают; Cenuta WG/nftables active. На Mac подтверждена `/Users/sergey/.venv`, свободно около 197 GiB.
2. Прочитан штатный TimeWeb backup helper и фактические volume mounts. Для полного согласованного состава использован отдельный configuration-only скрипт: штатный helper сам по себе не включает все host firewall/runtime snapshots. Его команды установки/применения не вызывались.
3. У Fornex обнаружены конфиги Amnezia внутри контейнеров без host mounts. Включены отдельные config archives, не Docker images/export.
4. В System master добавлены `backup_readonly.sh`, `run_backup.py`, затем `prepare_rollback.py`. SSH передает Bash payload через stdin; серверная Python/venv не нужна и не устанавливалась. Команды ограничены timeout, архивирование низкоприоритетное. Секретные данные пишутся только в закрытые backup-файлы.
5. TimeWeb 15:50:34-15:50:41 UTC: архив создан, скачан. Первая локальная проверка остановилась на GNU SHA-256 escaping в именах systemd mount files. Исправлен локальный parser, выполнен `--verify-only` уже скачанного архива; серверный backup не повторялся и конфиг не менялся.
6. Первый Fornex backup `1550Z` целостен, но при проверке полноты выявлен пропуск Unbound `/opt/unbound/etc`. В allowlist добавлен этот путь. Актуальный архив пересоздан 15:53:28-15:53:38 UTC с run `1553Z`; промежуточная копия сохранена, не выбрана для восстановления. Попытка `ps` внутри минимального DNS container дала command not found; это отсутствие утилиты, не отказ DNS. Пакеты не устанавливались.
7. Cenuta 15:52:56-15:53:00 UTC: конфиги и runtime state сохранены через sudo -n; архив скачан, проверен.
8. Локально проверены серверные/локальные SHA-256, внутренние суммы, 409 host files и 78 container files. Восемь protected configs извлечены в private temporary directory и совпали с baseline шага 1. Живое восстановление не выполнялось.
9. При статическом сравнении iptables обнаружены только изменения chain counters и служебных timestamps. Они исключены из сравнения; policy/verdict/rules сохраняются. После этого все 43 проверки до/после прошли: 17 TimeWeb, 17 Fornex, 9 Cenuta. Семь локальных verifier regression checks прошли.
10. Записан `rollback_manifest_20260912.json`: `changes_applied=[]`, apply запрещен. Точные новые peer keys, UID и handles нельзя выдумывать до deployment; их поля остаются пустыми и должны быть заполнены при отдельно согласованном применении.

## Состояние в конце каждого снимка

- TimeWeb: MemAvailable 1473 MiB, диск свободно 18 GiB; сохраняются PID/StartedAt/network namespace wg-relay. Runtime/static WG, routes/rules и firewall до/после совпали за исключением задокументированных динамических полей.
- Fornex: MemAvailable 1406 MiB, свободно 11 GiB; все семь контейнеров без изменения PID/StartedAt/config. WG handshake 1 минута 59 секунд на момент снимка.
- Cenuta: MemAvailable 1642 MiB, свободно 44 GiB; WG/nftables active time неизменен. Handshake 19 секунд на момент снимка.

Это не проверка нового VLESS, всех старых клиентов или полной связности сайтов. Двух снимков недостаточно для доказательства отсутствия временного ABA. Нагрузочный тест, отказоустойчивость, provider console/firewall и полный restore drill не выполнены.

## Следующая граница

Подготовительная часть шага 2 выполнена. Сам deployment и генерация новых credentials не разрешены. Следующее предложение: локальная подготовка и изолированные тесты Fornex-профиля; production изменения и последующие Cenuta/BTH отдельными этапами. Перед ними повторить audit/backup при любом drift и проверить аварийный доступ.
