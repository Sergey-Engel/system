---
type: runbook
audience: agent
system: timeweb
status: current
created: 2026-07-09
updated: 2026-09-27
---

# TimeWeb: правила операционных изменений

## Рабочие источники

Начинать с [VPN_HLD](<../architecture/overview.md>), [VPN_Configuration_Registry](<../registry/configuration.md>), [TimeWeb_VPN_Registry](<../registry/tunnels.md>), [Host_Access_Guide](<access.md>). Live host является операционным состоянием; этот Git checkout хранит код/описание, `.local` хранит приватные masters/backups. Исходный Obsidian больше не рабочий SSOT.

TimeWeb содержит обычный WG в wg-relay, отдельный host Xray REALITY и BTH recovery. Команда `wg-status` относится к обычному WG, не полной картине REALITY/AWG.

`/opt/wg-router/commands.sh` обновлен: recreate fallback удален, старые mutators отказывают до записи. Новый полноценный WG writer не реализован. Перед изменением прочитать [TimeWeb_Client_Creation](<TimeWeb_Client_Creation.md>) и [VPN_Maintenance_and_Backup](<maintenance-and-backup.md>): изменение RPDB требует отдельного обновления BTH-контракта. Reference-копии в Obsidian не использовать для deploy. `wg-client-config` выводит полный конфиг/QR: только приватный терминал, не общий журнал.

## После согласованного изменения

1. Сверить runtime, persistent и локальный master, точные адреса/ключевые идентичности и route/guard diff.
2. Синхронизировать соответствующий `.conf` или REALITY `.json` в `.local/clients`; не затрагивать другой транспорт с тем же именем устройства.
3. Обновить реестр и `.local/clients/README.md`.
4. Добавить sanitized checkpoint в существующий `docs/history/timeweb/<timestamp>-<slug>/README.md` либо датированный журнал непосредственно `docs/history/`.
5. Отдельно записать подтверждение устройства; наличие файла/handshake не равно пользовательской приемке.

## Обязательный gate мониторинга при изменении тоннелей

Применяется к созданию, удалению, переименованию, регенерации профиля,
добавлению устройства и изменению маршрутизации любого транспорта (WG,
REALITY/SOCKS/FLEX, AWG). Операция не завершена, пока мониторинг не согласован
с новым составом. Выполнить после deployment, до выдачи итогового отчета:

1. Обновить inventory `config/inventory/observations.json`,
   соответствующие fleet/controller config, реестр профилей и тесты cardinality.
   Проверить фактическое отображение устройств в Grafana/консоли.
2. Сравнить до/после весь защищаемый snapshot: RPDB, route tables, links,
   WG AllowedIPs, firewall, namespace и container identity. Проверить влияние
   отдельно на BTH recovery-контракт и monitoring guard manifest
   `/opt/vpn-monitoring/guards/guard-manifest.json`.
3. Если snapshot изменился, обновить monitoring baseline только на точный
   reviewed diff со свежей резервной копией и rollback; согласовать state
   manifest SHA/generation. Не переподписывать неизвестный drift и не ослаблять
   проверки. Если защищаемое состояние не менялось, записать проверенное
   `baseline update not required`, а не менять generation ради формальности.
4. Для новых переключаемых tables согласовать допустимые defaults batch helper.
   При изменении helper обновить его закрепленный SHA-256 в deployed
   `/opt/vpn-monitoring/pilot/config.json` и локальном master. Обновление только
   BTH-контракта **не обновляет** monitoring-контракт.
5. Перезапустить только затронутые monitoring services. Дождаться минимум
   двух новых циклов (штатно 120 s каждый): для обоих upstream
   `vpn_uplink_observation_fresh=1`, `vpn_uplink_probe_valid=1`, timestamp растет;
   отсутствуют `helper_pre_manifest_invalid`/`helper_revision_changed`.
   Prometheus target UP недостаточен: он может получать невалидные измерения.
   Проверить handshake/counters, причины статуса и данные в Grafana. Реальную
   сетевую деградацию не маскировать ожидаемым UP.
   После проверенного deployment и согласования обоих контрактов обновить
   runtime recovery generation: `python3 /opt/vpn-runtime-recovery/runtime_recovery.py publish`,
   затем `python3 /opt/vpn-runtime-recovery/runtime_recovery.py check`.
   Включить новый policy в verified backup. Timer никогда не публикует
   конфигурацию сам: stale binding должен отказать, а не принять неизвестный drift.
6. Зафиксировать backup, точный diff, generation/hash и результаты циклов
   в checkpoint. При неуспешном gate выполнить согласованный rollback либо
   явно обозначить изменение как незавершенное; не сообщать «готово».

Агент самостоятельно выполняет согласованные deploy, daemon-reload,
точечные restart и проверки; пользователь не должен вручную исправлять
права или перезапускать сервисы для завершения выдачи нового профиля.
При добавлении устройства обязательно обновить allowlist `ReadWritePaths`
консоли для его lock/state/audit paths (только необходимые точные пути),
локальный master unit и deployed unit. Проверить наличие lock-файлов до
старта unit.
Обновить также `/etc/tmpfiles.d/timeweb-console-locks.conf`, чтобы exact lock
paths создавались после reboot. Проверка controller через root SSH недостаточна:
выполнить read-only fleet status внутри mount namespace работающей консоли и проверить
ее HTTP `/state`: все ожидаемые маршруты ready, управление доступно,
нет `Read-only file system`/`Permission denied`. При изменении unit выполнить
`systemctl daemon-reload` и restart только затронутого сервиса, затем повторить
HTTP-проверку. Не отключать `ProtectSystem` ради обхода sandbox.

Инциденты 23 и 27 сентября 2026: выдача FLEX без обновления monitoring
baseline прерывала полезные измерения при работающих exporter/Prometheus.
`services/monitoring/timeweb-uplinks/pilot/audit_macmini_manifest.py` — ограниченный
changeset именно MacMini, не универсальная команда для будущих устройств.

## Ограничения live change

Перед live change требуется свежая восстанавливаемая копия с полным составом новых объектов. Исправленный `run_backup.py/backup_readonly.sh` schema 3 включает AWG31/reality-c3 и проверяет обязательный состав, metadata и источники до/после всего сбора. Подробности: [TimeWeb_REALITY_Backup_and_Rollback](<TimeWeb_REALITY_Backup_and_Rollback.md>).

При любом WG rule/config change учитывать BTH recovery: несовпадение полного контракта после закрепления namespace приводит к fail-closed удалению своего peer .5. Не переподписывать неизвестный drift.

Не выполнять общий firewall/route flush, Docker restart/recreate или массовый отзыв peers как диагностику. Новые установки согласовывать отдельно. Python только `python3 -B`.

Private keys, PSK, UUID credentials, пароли и QR не писать в Obsidian. Full configs и backups только в закрытом System; хранилище архива может содержать до сих пор действующие секреты.
