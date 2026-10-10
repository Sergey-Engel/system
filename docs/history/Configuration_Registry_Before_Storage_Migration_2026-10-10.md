---
type: registry
status: historical
updated: 2026-09-23
tags: [vpn, configuration, master, backup]
---

> Historical storage snapshot. Current paths and access: [Quick Guide](../quick-start.md).


# Реестр конфигураций и мастер-копий

## Где находится источник

**Полная локальная мастер-копия новых компонентов находится в System, не на TimeWeb и не в Obsidian.** Root: `${SYSTEM_ROOT}`. Для старого WG runtime остается операционным источником состояния; локальные экспорты и датированные backups не следует выдавать за автоматически синхронизируемый deploy-repository.

Obsidian хранит описание, реестры и безопасные ссылки. System хранит исходные скрипты, реальные конфиги, credentials, manifests, артефакты, backups и клиентские файлы. Runtime на сервере является примененной копией. Совпадение проверяется хешами, не временем изменения файла.

## Карта master -> runtime

Все относительные локальные пути ниже начинаются от System.

| Компонент | Локальный master / сохраненный источник | Примененное размещение |
| --- | --- | --- |
| REALITY, актуальный общий Xray config | VERIFIED snapshot `Mikrotik/backups/timeweb/2026-09-23T082407Z_current-config/`; `transport/timeweb-reality/stage9-bth/config.after` — история, не deploy master | TimeWeb `/opt/timeweb-reality/config.json` |
| REALITY host guard | Тот же VERIFIED snapshot; `transport/timeweb-reality/flex_guard.nft` — источник добавленного узкого разрешения `.39`; stage9 guard исторический | TimeWeb `/opt/timeweb-reality/guard.nft`, `guard.expected`; runtime `inet reality_fornex` |
| Xray binary и unit, исходный выпуск | `transport/timeweb-reality/vendor/`, `stage56-timeweb/` | `/opt/timeweb-reality/xray`, `/etc/systemd/system/xray-timeweb-reality.service` |
| Fornex REALITY peer/guard | `transport/timeweb-reality/stage4-fornex/` | Fornex `wg-exit`, `/opt/wg/config/wg_confs/wg0.conf`; peer `10.20.0.3` |
| Cenuta REALITY peer/guard | `transport/timeweb-reality/stage8-cenuta/` | `/etc/wireguard/wg-cenuta.conf`, `/etc/nftables.conf`, `/etc/reality-c3/` |
| BTH peer/guard и правила MikroTik | `transport/timeweb-reality/stage9-bth/` | Runtime peer `.5` в `wg-relay/wg-home`, `inet reality_b5`, адресные правила роутера |
| BTH recovery и выдача WG BTH | `transport/timeweb-reality/bth_recover.sh`, `refresh_bth_contract.py`, VERIFIED snapshot 23.09; `bth-recovery-release/` исторический | `/opt/timeweb-reality/bth-recovery/`, `wg-relay/wg-home`, `bth-recovery.service/timer` |
| SOCKS-TW-FLEX MacBook | `transport/timeweb-reality/flex_pilot.py`, `provision_flex_pilot.py`, `clients/Sergey/MacBook/SOCKS-TW-FLEX-S-MacBook.json`, VERIFIED snapshot 23.09 | TimeWeb `wg-clients` peer `.39`, `/usr/local/sbin/timeweb-flex-macbook`, `timeweb-flex-macbook.timer`, console section |
| AWG 3.1 config/start | `transport/fornex-awg31/release/` | Fornex `/opt/fornex-awg31/`, RO bind в `fornex-awg31` |
| AWG 3.1 image/build | `transport/fornex-awg31/Dockerfile`, `source/`, `image-id.txt`, `run-command.txt` | Fornex Docker image и контейнер `fornex-awg31` |
| AWG fleet/credentials | `transport/fornex-awg31/fleet.json`, `credentials.json`, 11 `.conf` | 11 peers в AWG 3.1; выдача через `clients/` |
| WG selector | Датированные `Mikrotik/backups/timeweb/`, клиентские `clients/*.conf` | TimeWeb `/opt/wg/config`, `/opt/wg-router`, `state/clients.tsv`, `state/ru_bth_clients.tsv` |
| WG maintenance safety gate | `transport/timeweb-reality/maintenance-wg/commands.sh` | TimeWeb `/opt/wg-router/commands.sh`; старые writers отключены до записей |
| Старые Fornex/Cenuta WG | `Mikrotik/backups/fornex/`, `Mikrotik/backups/cenuta/` | Fornex `wg-exit`; Cenuta host `wg-cenuta` |
| Router Нахимова 11 | Свежий export в `Mikrotik/backups/local/2026-09-13T160248153221Z_current-config/current-config.tar.gz`; старые `Mikrotik/current/router/` и `stage9-bth/router.after.rsc` сохранены как история | MikroTik; fresh text export 2026-09-13 16:02:58 UTC, без нового полного аудита правил |
| Router Орехово | `Mikrotik/current/orekhovo-router/` | Отдельная площадка; не подменять Нахимовой |
| Мониторинг | `monitoring/timeweb-uplinks/`, `monitoring/vpn-connectivity/` | Отдельные deployment/service; см. их README и статус pilot |
| Профили импорта | `clients/`: 36 WG, 16 REALITY, 11 AWG 3.1 | Выданные файлы; их импорт в приложениях устройств подтверждается отдельно |

## Проверенные совпадения

Сверка с серверным срезом 2026-09-13:

| Артефакт | SHA-256 master = runtime |
| --- | --- |
| Общий Xray config после BTH | `a3e79c156ebd548fd4e3ccf0a5727457a0561846293488f9c4caa399eaef06fc` |
| AWG 3.1 `release/awg0.conf` | `f4beca9154a51020ec33ee33118a1aece0cd26cad6d1858f81adc3c03e3313bd` |
| WG maintenance helper после исправления | `087c3b1837ab9d5cd5d375bba59c3ee709cbe3517e6156073a75aabf580633a1` |

Сверка выше относится к срезу 2026-09-13. 17 сентября отдельно подтверждены новый MacBook BTH peer `10.30.30.6/32`, persistent `wg-home.conf`, recovery-contract и таймер; телевизионный peer `10.30.30.3/32` сохранен без смены ключей. Все 11 опубликованных AWG-файлов побайтово совпали с соответствующими мастер-файлами. Это не утверждение, что полностью сверены все файлы ОС, RouterOS или каждый старый backup.

## Статус скриптов

| Скрипт / набор | Разрешенное толкование |
| --- | --- |
| `timeweb-reality/run_backup.py` + `backup_readonly.sh` | Текущий schema-3 backup: обязательный состав хостов/контейнеров, полный интервал source checks, metadata, runtime drift и локальное пробное восстановление. См. [VPN_Maintenance_and_Backup](<../operations/maintenance-and-backup.md>) |
| `prepare_stage3.py`, `prepare_rollback.py`, `prepare_bth_recovery.py` | Исторические CLI заблокированы до действий; не средство обновления текущего поколения/контракта |
| `stage4_fornex.py`, `stage56.py`, `stage8_cenuta.py`, `stage9_bth.py` | Исторические CLI заблокированы; исходные scoped diff оставлены для подготовки отдельно проверенного текущего changeset |
| `stage56_target_update.py`, `issue_stage56_clients.py` | RETIRED до импорта/первой записи; повторный запуск не остановит Xray и не перезапишет профили |
| `bth_recover.sh`, `refresh_bth_contract.py` | Актуальный исходник ограниченного восстановителя BTH и инструмент осознанного обновления live-контракта; исторический `bth-recovery-release/` не применять к текущему Xray |
| `fornex-awg31/prepare.py`, `build.py`, `deploy.py` | `prepare`/`deploy` заблокированы. `build` сохранен как отдельная явно запускаемая сборка, без install/apply |
| `fornex-awg31/finalize.py` | RETIRED: повторный запуск отказывает до записи/сети |
| `fornex-awg31/expand_fleet.py` | Выполненная миграция; CLI и старый sync заблокированы, не general-purpose управление клиентами |
| `fornex-awg31/verify.py --profile ...` | Активный smoke; использует выбранный peer и может изменить его изученный endpoint. Не запускать на профиле работающего устройства |
| `fornex-awg31/rollback.sh` | RETIRED: завершение с ошибкой до Docker, AWG31 не останавливается и AWG2 не восстанавливается |
| `maintenance_preflight.py --check` | Read-only preflight текущего Xray/BTH; не разрешает WG mutations/переподписание контракта |
| `maintenance-wg/commands.sh` | Новый локальный master серверного `/opt/wg-router/commands.sh`: просмотр сохранен, старые mutators и неполный backup отключены, recreate fallback удален |
| `bth_client_changeset.py` | Текущий ограниченный transactional writer для добавления одного WG BTH peer: использует verified backup, допускает только три проверяемых переходных состояния recovery-контракта и не перезапускает `wg-relay` |
| `wg-client-config`, `wg-status` | Просмотр обычного WG; интерактивные старые delete/regenerate завершаются отказом до записи |

Не запускать старый этапный генератор, чтобы «обновить мастер»: он может создать конфиг без позже добавленных клиентов/выходов.

## Выдача, хранение и обновление

1. Новый change начинаетcя с конкретного approved списка устройств/объектов и свежего audit.
2. Генерировать отдельную идентичность на устройство. Существующие работающие ключи не менять без согласования.
3. Применять точный diff, сравнивать runtime и persistent config. Снять новый checksum/manifest.
4. Опубликовать конфиг в `.local/clients`; обновить [TimeWeb_VPN_Registry](<../registry/tunnels.md>) и соответствующий System README.
5. Записать отдельно подтверждение импорта/работы на устройстве. Не путать публикацию и приемку.
6. Удаление файла не отзывает peer; отзыв должен затронуть runtime, persistent и все активные мастер-копии. Backup остается закрытой историей.

Python: `python3 -B`. Новые зависимости/установки согласовываются отдельно. Конфиги и manifests с секретами: файлы 600, каталоги 700. Эти права не являются шифрованием и не защищают от доступа администратора или получателя Dropbox share.

## Backup и история

- Актуальная проверенная TimeWeb-копия после FLEX: `Mikrotik/backups/timeweb/2026-09-23T082407Z_current-config/` (VERIFIED). Датированные проверенные копии других VPS: `Mikrotik/backups/fornex/2026-09-17T132209Z_current-config/`, `Mikrotik/backups/cenuta/2026-09-17T132238Z_current-config/`. Состав и ограничения backup: [VPN_Maintenance_and_Backup](<../operations/maintenance-and-backup.md>).
- Пре-REALITY конфигурационные архивы: `Mikrotik/backups/{timeweb,fornex,cenuta}/2026-09-12T*`.
- Поэтапные before/after и exact rollback: `transport/timeweb-reality/stage*/`.
- AWG: `transport/fornex-awg31/backup/` и `retirement-backup/`. AWG2-ключи отозваны, но `credentials.before.json` в retirement содержит также **действующие** серверные AWG31 credentials и ключи MacBook/iPhone. Весь архив остается секретным.
- Исходники документов до ревью: `transport/documentation-audit-20260913/before/`, checksum `before/sha256.json`.
- Live evidence ревью: `transport/documentation-audit-20260913/live.json`.

Полный restore drill и автоматическая синхронизация всех runtime-конфигов с master не заявляются. Старый manifest не дает разрешения на применение к новому namespace/поколению.

Связи: [VPN_HLD](<../architecture/overview.md>), [TimeWeb_REALITY_Backup_and_Rollback](<../operations/TimeWeb_REALITY_Backup_and_Rollback.md>), [Fornex_AWG31_Operations](<../operations/Fornex_AWG31_Operations.md>), [VPN_Documentation_Review_2026-09-13](<../history/VPN_Documentation_Review_2026-09-13.md>).
