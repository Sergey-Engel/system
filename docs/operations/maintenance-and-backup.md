---
type: runbook
status: current
updated: 2026-09-28
tags: [vpn, backup, maintenance]
---

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.


# VPN: обслуживание и актуальный backup

## OS maintenance: 27 сентября 2026

Последовательно обновлены Cenuta, Fornex, TimeWeb и MikroTik Нахимова. Результаты, backup и ограничения: [OS_Maintenance_2026-09-27](<../history/OS_Maintenance_2026-09-27.md>).

**Дополнение 28 сентября:** постоянный recovery установлен и проверен реальным restart `wg-relay` и reboot TimeWeb. Процедура и ограничения: [TimeWeb_Runtime_Recovery](<TimeWeb_Runtime_Recovery.md>). Одноразовый recovery 27 сентября остаётся отключённым; его snapshot нельзя применять к изменившейся конфигурации.

Перед плановым рестартом агент проверяет current policy binding, BTH, FLEX, verified backup и готовность recovery service/timer; после рестарта требует два валидных цикла. При изменении топологии агент обязан опубликовать новую reviewed recovery generation до завершения deployment. Container recreate / image replacement не приравниваются к restart и требуют отдельного согласования. Старый `apply-ru-bth.sh` не запускать вслепую: он предшествует FLEX-контракту.

При добавлении устройства также обновлять список разрешённых lock-файлов консоли и `/etc/tmpfiles.d/timeweb-console-locks.conf`: файлы в `/run` исчезают после reboot. `deploy_console.py` теперь устанавливает tmpfiles-конфигурацию.

`backup_local.py` пока содержит устаревшее ожидание 52 клиентских файлов и при текущем составе завершается `FAILED/client_config_count_not_52`. Это не VERIFIED backup. Исправление проверки должно опираться на текущий реестр, а не на отключение gate. Для обслуживания Нахимова отдельно получены свежие export и binary backup.

## Что изменено

- `run_backup.py` / `backup_readonly.sh` обновлены под работающую топологию: обычный WG сохранен, AWG2 не требуется, AWG31 и Cenuta `reality-c3` включены.
- Добавлены обязательные файлы каждого сервиса, проверка целостности, прав/владельцев/ссылок, источников в начале и конце всего сбора, стабильности runtime и локальное пробное восстановление файлов.
- `maintenance_preflight.py --check` сверяет локальные masters с TimeWeb и проверяет BTH через свежий закрепленный namespace. **PASSED не разрешает изменение RPDB и не переподписывает контракт.**
- На TimeWeb обновлен только `/opt/wg-router/commands.sh`: автоматический recreate fallback удален; старые изменяющие функции завершаются `RETIRED` до записи, включая удаление/перегенерацию из меню. Просмотр сессий сохранен. Это защитная блокировка старого writer, не новый универсальный CRUD для WG.
- Одноразовые CLI первоначального REALITY deployment, подготовки recovery и миграции AWG2/AWG31 заблокированы. Исторический код сохранен; обходных флагов нет. Сборка AWG-образа остается отдельной явно запускаемой операцией, не установкой или миграцией.
- Процесс `create-timeweb-vpn-client` обновлен в каноническом `.ai-skills` и workspace-зеркалах Codex/Claude: старые команды создания, удаления, прямой записи TSV и backup больше не предлагаются. User-global legacy-копия не является источником и этим этапом не синхронизировалась.
- Recovery, туннели, firewall, peers и клиентские ключи этим изменением не перенастраиваются. BTH сохраняет строгую проверку полного RPDB.

## Выполнено 13 сентября 2026

**Итог: три VPS и локальный архив VERIFIED.** Все перечисленные пути начинаются от `.local/backups/`.

| Объект | Проверенный архив | Размер, байт | Проверка |
| --- | --- | ---: | --- |
| TimeWeb | `timeweb/2026-09-13T155623Z_current-config/backup.tar.gz` | 15869210 | 323 host-файла; 28 обязательных файлов восстановлены во временный каталог |
| Fornex | `fornex/2026-09-13T155623Z_current-config/backup.tar.gz` | 319273 | 126 host-файлов, 76 файлов шести дополнительных контейнеров; 8 обязательных host-файлов восстановлены |
| Cenuta | `cenuta/2026-09-13T155623Z_current-config/backup.tar.gz` | 130792 | 78 host-файлов; 5 обязательных файлов восстановлены |
| Локальные masters и MikroTik | `local/2026-09-13T160248153221Z_current-config/current-config.tar.gz` | 22769381 | 556 исходных файлов, включая 52 профиля, плюс свежий export; все 557 файлов восстановлены и сверены |

Суммарно 39088656 байт сжатых архивов. В каждом каталоге имеется `verification.json`; VPS-копии дополнительно содержат `SHA256SUMS`. Права каталогов/файлов проверены: 700/600.

| Объект | SHA-256 архива |
| --- | --- |
| TimeWeb | `debaa3b843635ff62b6287e8670a2cb744a98738867fb57ff0768bea37881fe9` |
| Fornex | `347b02b529558673b3ec37459cd474e8a8a8a3a1cc714dd2dd63faff752224de` |
| Cenuta | `0585689c72b80d921037b7adf2411854a3d0c9a42b0802a9ce1eebaf9b8b9fc4` |
| Локальный | `5db5d2fb9407648de03b71118d612971ee59904dabcdd321cedbbaba71d29661` |

Свежий текстовый export MikroTik Нахимова получен через закрепленный namespace TimeWeb **16:02:58 UTC**, размер 826668 байт. Он находится только внутри приватного локального архива как `fresh-router/router-export.rsc`; старый `Mikrotik/current` не перезаписан. Binary RouterOS backup не создавался. Получение и побайтовая проверка export не означают полный новый смысловой аудит всех правил роутера.

Первый локальный запуск `2026-09-13T155624868766Z_current-config` завершился `FAILED/source_changed` и не является принятой копией. После окончания правок выполнен новый стабильный снимок; проверки metadata/hash не ослаблялись. Предварительный VPS-снимок `2026-09-13T153528Z_current-config` содержит состояние до замены WG-helper и остается исторической копией schema 2, не текущим schema-3 backup.

Проверки этапа:

- **91 автоматический тест**: 83 для TimeWeb backup/preflight/retirement и 8 для AWG lifecycle. Включены повреждение архива, отсутствующие файлы, metadata/runtime drift, лимиты, ссылки и отказы retired writers до действий.
- Повторная офлайн-проверка трех VPS-архивов завершилась `VERIFIED` без SSH.
- Финальный `maintenance-wg/preflight-final.json` в System: **16:02:24 UTC, PASSED**; совпали текущие Xray/BTH masters, unit generation, namespace и recovery-контракт.
- Единственный замененный серверный файл: `/opt/wg-router/commands.sh`. Xray PID 1265735 и `wg-relay` PID 1181 не изменились; контейнер сохранил время запуска 2026-07-10. Просмотр сессий работает.
- Рабочие ключи и 52 профиля не менялись; пакеты не устанавливались. Мониторинг/Grafana не включались; сетевые стресс-тесты и повторная приемка устройств не проводились.

## Команды на Mac Mini

Python только из штатной `.venv`, установка зависимостей не требуется:

```bash
python3 -B services/transport/timeweb-reality/maintenance_preflight.py --check
```

Свежий конфигурационный backup трех VPS, последовательно, без рестартов:

```bash
python3 -B services/transport/timeweb-reality/run_backup.py all
```

Идентификатор вида `YYYY-MM-DDTHHMMSSZ_current-config` выводится сборщиком. Копии находятся в `.local/backups/{timeweb,fornex,cenuta}/<run>/` и на соответствующем сервере в `/var/backups/timeweb-reality/`.

Повторная офлайн-проверка уже полученной копии:

```text
python3 -B services/transport/timeweb-reality/run_backup.py all <run> --verify-only
```

Не использовать старую команду `commands.sh backup`: неполный старый сборщик отключен. Не обходить ошибку нового сборщика: при `FAILED` сначала исследовать защищенные журналы, исправить причину и сделать новый запуск. Старую или частичную копию нельзя переименовать в актуальную.

Отдельная копия локальных masters/52 профилей с одной попыткой свежего RouterOS export:

```bash
python3 -B services/transport/timeweb-reality/backup_local.py
```

Результат сохраняется в `.local/backups/local/`. `PARTIAL` означает, что локальные файлы могут быть успешно проверены, но свежий export роутера не получен; смотреть поля `local_backup` и `router`. `Mikrotik/current` помещается в `supplemental`, а не выдается за свежий снимок. Автоматической подмены старым export нет.

## Состав и проверка

- Host archives: persistent WG, реестры/скрипты, compose, systemd, firewall, сетевые настройки, SSH-конфигурация и ключи хоста, нужные authorized_keys, Xray binary/config/guards, полный BTH release/contract, AWG31, Cenuta PreUp guards.
- Fornex: отдельный состав каждого существующего контейнера, включая Xray, обычный WG, OpenVPN PKI, IPsec и Unbound. Обязательные пути проверяются независимо от manifest самого архива.
- Runtime evidence: контейнеры, образы/идентификаторы, сети, адреса, маршруты, rules, native nftables, iptables, текущие WG/AWG configs, unit states. Изученные WG Endpoint и счетчики могут меняться; изменения ключей, маршрутизации, процесса/namespace не принимаются как обычный шум.
- Проверяются checksum скачивания, все обычные файлы, права/владельцы и symlink metadata. Специальные Unbound device nodes сохраняются только как строго проверенные метаданные; на Mac не создаются.
- Пробное восстановление происходит только в приватном временном каталоге Mac. Архивные скрипты не исполняются; ни один файл не восстанавливается поверх живого сервера.
- На VPS ограничены время, объем сбора и запас диска; имеется lock против одновременных backup-запусков. Автоматическое удаление старых копий не включено.

`BTH --check` использует существующий advisory lock и временные файлы в `/run`. Это не абсолютно беззаписная проверка, но она не меняет peers, rules, постоянные конфиги или units. Сбор является последовательным срезом каждого хоста, не распределенной транзакцией всех VPS.

Полные ключи остаются только в System/защищенных серверных архивах. Каталоги 700, файлы 600; это **не шифрование**. Архивы не включают диски ОС, Docker images, monitoring DB и настройки кабинетов провайдеров. Их восстановление на чистом VPS требует отдельного плана и проверки доступности нужных образов.

## Как теперь менять WG / REALITY / AWG

1. Свежий backup и `maintenance_preflight --check`, согласованный точный список изменений.
2. Подготовить новый текущий diff, а не запускать старую миграцию. Отдельно учесть весь BTH recovery-контракт: selector rule/config может привести к удалению peer `.5` следующим циклом recovery.
3. Для обновления контракта необходим согласованный change window, проверка текущего состояния против ожидаемого diff и точный rollback. Нельзя автоматически подписывать обнаруженный drift или отключать fail-closed ради UP.
4. После применения проверить runtime/persistent/master, неизменность чужих peers и служб, синхронизировать `.local/clients` и [TimeWeb_VPN_Registry](<../registry/tunnels.md>).
5. Зафиксировать отдельную клиентскую приемку и новый backup после изменения. Наличие архива не заменяет проверку работы устройства.

Старые универсальные WG mutator-команды по-прежнему намеренно заблокированы. Для добавления одного WG BTH peer реализован ограниченный `bth_client_changeset.py`: он работает только с заранее reviewed changeset, fresh verified backup и трехшаговым проверяемым переходом recovery-контракта. Он не является универсальным инструментом для delete/regenerate, selector-маршрутов или произвольной выдачи клиента; для них требуется отдельная реализация и тесты.

Связи: [VPN_Configuration_Registry](<../registry/configuration.md>), [TimeWeb_REALITY_Backup_and_Rollback](<TimeWeb_REALITY_Backup_and_Rollback.md>), [TimeWeb_Client_Creation](<TimeWeb_Client_Creation.md>), [Fornex_AWG31_Operations](<Fornex_AWG31_Operations.md>).
