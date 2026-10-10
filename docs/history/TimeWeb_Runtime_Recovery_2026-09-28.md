---
type: maintenance-report
status: completed
updated: 2026-09-28
tags: [vpn, recovery, maintenance]
---

# TimeWeb Runtime Recovery: 2026-09-28

Выполнено по поручению пользователя: постоянное восстановление после restart/reboot и обновление ранее удерживаемого QEMU agent. Рабочий runbook: [TimeWeb_Runtime_Recovery](<../operations/TimeWeb_Runtime_Recovery.md>).

## Реализация

- Deployment `/opt/vpn-runtime-recovery/`, persistent `policy.json` с SHA-256 binding актуальной конфигурации; state в `/var/lib/vpn-runtime-recovery/state.json`.
- `timeweb-runtime-recovery.service` enabled на boot; timer enabled, 15 s после завершения предыдущего запуска. При прежнем namespace и неизменных bindings — только быстрая проверка, без повторной записи manifest.
- Нет привязки к архиву 27 сентября. Неподтверждённый container ID/image, topology/config drift и чужие правила вызывают отказ. Нет автоматического publish, общего flush или ослабления BTH/monitoring контрактов.
- Сохраняются текущие UDP/WSS и Gateway/RU-direct. FLEX параметры восстанавливаются из per-device state, а не из исторического snapshot. Для WSS поднимаются WG и Xray carriers по transport state.
- В начале recovery ждёт startup links, приостанавливает writer timers, collector и console. Порядок: base rules/routes/RU policy → carriers → FLEX → BTH → monitoring rebind → services.
- Publish/check recovery generation добавлены в agent runbook и канонический skill выдачи туннелей; workspace skill mirrors синхронизированы. Console lock paths требуют соответствующих tmpfiles.
- Backup дополнен recovery code/policy/state/units, monitoring manifests/helper, FLEX state/controllers, transport state и tmpfiles. Verifier требует новый состав при наличии recovery unit. Временные `batch.*` каталоги collector не включены: это scratch, не persistent конфигурация.

## Проверки

- 13 focused unit tests runtime recovery / monitoring rebind; 28 backup/scanner tests; bash syntax check passed.
- Force recovery на действующем namespace прошёл.
- Реальный `docker restart wg-relay`: автоматическое обнаружение в 04:28:49 UTC, `RUNTIME_RECOVERY_VERIFIED` в 04:29:41 UTC, без ручной repair-команды.
- Первый reboot: автоматическое восстановление в 04:32:17 UTC после одного раннего отказа по ещё отсутствующему WG interface. Добавлено явное ожидание links. Финальный reboot: `9e23e306-e8e1-4b6c-b896-5519eab8abec`, recovery 04:38:38 → 04:39:27 UTC, первая попытка success, failed units отсутствуют.
- До финального reboot BTH valid, fleet ready, units без failures; collector cycle 04:34:13 UTC — оба upstream UP/ok, четыре HTTPS checks success.
- Финальные collector cycles: 04:46:09.437856 UTC и 04:48:13.501107 UTC (timestamps 1790570769.4378564 → 1790570893.5011072): оба upstream UP/ok, четыре HTTPS checks success в обоих циклах. Runtime check passed; BTH valid; FLEX 3/3 ready. Это server-side probe acceptance, не проверка приложений клиента.

### Console resource recovery

При финальной проверке в 04:41:31 UTC console превысила cgroup MemoryMax=128M: несколько HTTP requests одновременно запускали fleet subprocesses. HTTP ответ занимал 23.68 s, launcher исчерпал короткие retries. Добавлены общая сериализация reads/writes и shared status cache 5 s с invalidation после команды. CPU/memory/sandbox ограничения не ослаблялись. 13 console tests passed. После deployment шесть simultaneous requests: HTTP 200 для всех, 5.76 s; MemoryPeak=76,013,568 bytes, NRestarts=0. Console source добавлен в required backup scope.

`open_console.sh start` после исправления: READY, существующий managed SSH PID 38313 переиспользован, новый процесс не создан; URL `http://127.0.0.1:19118/`. Последний runtime check passed; QEMU `.18` active.

## QEMU Guest Agent

Обновлён только пакет `qemu-guest-agent`: `1:8.2.2+ds-0ubuntu1.11` → `1:8.2.2+ds-0ubuntu1.18`, без removals или новых dependencies. APT операция success, dpkg clean; service restarted и active после reboot; hold отсутствует. Старый hold документировался ранее, но подтверждённого основания для сохранения в доступных инструкциях и логах не найдено. TimeWeb рекомендует штатный пакет из репозитория ОС: [инструкция провайдера](https://timeweb.cloud/docs/unix-guides/installing-qemu-agent). Provider-side management API из гостя не проверялся.

## Backup

Приватный корень: `.local/backups/`.

- До доработок: `timeweb/2026-09-28T042108Z_current-config/backup.tar.gz`, VERIFIED, SHA `ddc31681857c19616025fa334bf275f17fd19fbd775a1171a267de5122da2580`.
- `2026-09-28T043315Z_current-config` FAILED: collector scratch изменял metadata во время сбора. Gate сохранён, scope уточнён до persistent ownership state; эта попытка не является принятой копией.
- Промежуточная копия `timeweb/2026-09-28T043527Z_current-config/backup.tar.gz` VERIFIED (377 host files, 53 required restore files), SHA `b85ac70c44ffde749ce6c050eef5b242495d0aca83f193c9572d43f0de2af2f7`. После неё добавлена проверка carrier state, поэтому это не final generation.
- Копия после reboot `timeweb/2026-09-28T044057Z_current-config/backup.tar.gz` VERIFIED (379 host files, 54 required restore files), SHA `bafa586d933e6b7876889e0a8f619b4dc13738b96994a48633e91f4b164f19fe`. После неё исправлен console OOM; итоговая копия выполняется отдельно.
- Итоговая копия `timeweb/2026-09-28T044739Z_current-config/backup.tar.gz` VERIFIED: 21,993,488 bytes, 380 host files, 55 required restore files; SHA-256 `64cd7e91d03feb5460e5616de14dcd8a146f03061b1f3338c14a41c6ccb30ae9`. Включает исправление console concurrency и текущую recovery generation.

Клиентские профили и ключи не перевыпускались. Проверка реальных клиентских приложений не проводилась. Новый image/container recreate не считается обычным restart и требует отдельного review/publication. Ошибка общего `backup_local.py` с hardcoded 52 относится к другому gate и этим этапом не исправлялась.
