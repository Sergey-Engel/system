---
type: maintenance-report
status: completed-with-limitations
updated: 2026-09-27
tags: [vpn, maintenance, backup]
---

# OS Maintenance: 2026-09-27

Follow-up 28 сентября: постоянный recovery и QEMU update — [TimeWeb_Runtime_Recovery_2026-09-28](<TimeWeb_Runtime_Recovery_2026-09-28.md>). Ниже сохранены результаты и ограничения именно этапа 27 сентября.

По поручению пользователя хосты обновлялись последовательно: Cenuta → Fornex → TimeWeb → MikroTik Нахимова. Обновления Ubuntu выполнены в рамках 24.04 LTS, без release-upgrade. Ключи и клиентские VPN-профили не перевыпускались, Docker images не заменялись.

## Итог

| Хост | До | После | Проверка |
| --- | --- | --- | --- |
| Cenuta | kernel 6.8.0-139 | kernel 6.8.0-142; доступные APT updates установлены | Reboot выполнен; WG, nftables, WSS active; dpkg clean; нет failed units / pending packages |
| Fornex | kernel 6.8.0-138; Docker 29.6.1 | kernel 6.8.0-142; Docker 29.8.1, containerd 2.3.6 | Reboot выполнен; все 7 контейнеров Up, DNS healthy; dpkg clean; нет failed units / pending packages |
| TimeWeb | kernel 6.8.0-134; Docker 29.6.1 | kernel 6.8.0-142; Docker 29.8.1 | Reboot выполнен; BTH_CONTRACT_VALID; FLEX ready 3/3; guards VALID generation 16; нет failed units |
| MikroTik Нахимова | RouterOS / RouterBOOT 7.22.1 | RouterOS + wifi-qcom + RouterBOOT 7.24.4 stable | Две перезагрузки; тот же hAP ax3 HKM0BDXYG74; 8 active routes; 3 running WG interfaces; ping 1.1.1.1 3/3, loss 0% |
| MikroTik Орехово | Текущая версия не подтверждена | Не изменён | SSH 192.168.88.1 из текущей внешней сети timeout |

На TimeWeb сохранён существующий explicit hold `qemu-guest-agent`: установлен `1:8.2.2+ds-0ubuntu1.11`, доступен `.18`. Hold не снят, происхождение hold отдельно не подтверждалось.

Fornex `linux-firmware` был kept back из-за новых зависимостей. Выполнен отдельный `install --only-upgrade linux-firmware`: один upgrade и 18 зависимостей, без removals; повторный reboot не требовался.

## Приёмка

- После каждого зарубежного VPS получены два успешных цикла TimeWeb monitoring.
- После TimeWeb reboot получены успешные циклы 17:22:08 и 17:24:09 UTC, следующий 17:26:09 также успешен: обе цели HTTPS gstatic/cloudflare для обоих выходов valid/success, состояния UP, reason ok.
- Pilot, exporter, console, Xray active; FLEX reconcile services завершались success. Выбранные маршруты сохранены: Cenuta / RU-direct ON для всех трёх устройств, включая отдельное override iPhone.
- Локальный SSH консоли восстановлен агентом, launcher READY на http://127.0.0.1:19118/. Grafana `/api/health`: database ok, 13.1.3. Prometheus: все три scrape targets up=1.
- Ручная проверка каждого клиентского приложения и реального пользовательского трафика не проводилась. Server readiness и HTTPS probes не означают повторную client acceptance.

## Backup

Корень приватных архивов: `.local/backups/`. VPS-снимки прошли hash verification и пробное восстановление обязательных файлов во временном локальном каталоге; не являются образами дисков ОС.

| Хост | Архив относительно корня | SHA-256 |
| --- | --- | --- |
| Cenuta до обновления | `cenuta/2026-09-27T163829Z_current-config/backup.tar.gz` | `3f0d41db5b3d673f78d584fa25d5ca2df16230cad64cd889727bf17d6dcec684` |
| Fornex до обновления | `fornex/2026-09-27T165029Z_current-config/backup.tar.gz` | `3770311223e0fe9577f30eb6a1d2bac37db42ff1e76febadbb2ca845ef8b20c9` |
| TimeWeb до обновления | `timeweb/2026-09-27T165839Z_current-config/backup.tar.gz` | `aea4c14f65eb3c3771aaef5b670dc2a13fbe96297490730c2cd9420c36ed3efd` |
| TimeWeb после восстановления | `timeweb/2026-09-27T172423Z_current-config/backup.tar.gz` | `3f6856ba2a7ff886f59fafbf7b7444d3e78dad690e23ffc4a2e3a4c9101ffe1e` |

Отдельный TimeWeb monitoring snapshot: `timeweb/2026-09-27T165839Z_current-config/monitoring-before.tar.gz`, SHA `f025c341f4b9cf62eb7c55297c8ae83b9580fa083dbabac55ecb591a44a2c017`.

MikroTik Нахимова: `nakhimova/2026-09-27_os-maintenance/before.rsc` (532467 bytes, SHA `3c5ba251ad348247598140249c85cf3409ae320ee0761587f0e3496a8d05b861`), `before.backup` (1053337 bytes, SHA `c35fcdbddb499fcba1df466b670735ecb12e72ef0c6307605ed568ea21643227`). Binary backup скачан по SCP; контрольное восстановление на роутере не выполнялось. Экспорт после обновления сохранён как `after.rsc`. Каталог 700, файлы 600; архив содержит секреты и не зашифрован. [Ограничения RouterOS backup/export](https://help.mikrotik.com/docs/spaces/ROS/pages/40992852/Backup).

Общий локальный сборщик отказал с `client_config_count_not_52`; не подменять его результат отдельным router backup. Preflight локальных masters также выявлял reference drift; этот gate не объявлялся PASSED и не ослаблялся.

## Инцидент TimeWeb во время обслуживания

APT upgrade Docker перезапустил существующий `wg-relay`: container ID и image SHA не изменились, namespace изменился. Потеряны runtime-only `inet ru_bth`, правила RPDB 180/181/190 и host routes зарубежных endpoints. Legacy FORWARD/NAT rules сохранились, но изменили порядок. FLEX fail-closed корректно остановил маршруты, BTH отказал по контракту; мониторинг больше не мог использовать старую namespace-привязку.

Восстановлена только отсутствующая `ru_bth` таблица из свежего проверенного snapshot, три известных RPDB rules, два endpoint routes и исходный порядок конкретных legacy iptables rules. Не выполнялись firewall flush, retired universal WG writers, выключение sandbox или переподписание контракта под повреждённую сеть.

Выявлен дефект FLEX: exception каждый раз добавлял DROP, recovery снимал только один. Контроллер исправлен: повторная quarantine idempotent; routing/guard проверяются до снятия quarantine; удаляются все точные правила своего peer с пределом 256, чужие правила не затрагиваются. Три focused tests passed; пять monitoring rebind tests passed.

Для reboot использован одноразовый `os-maintenance-recovery.service`. Первая попытка отказала: BTH запускался до восстановления FLEX RPDB. Порядок исправлен: base → FLEX → BTH → строго проверенный monitoring rebind. После успешного восстановления unit отключён, pending marker удалён. Постоянное boot-recovery всей актуальной топологии этим обслуживанием не реализовано; старый snapshot нельзя применять к будущему составу туннелей.

Добавлен tmpfiles-файл для семи console lock paths и установка его в `deploy_console.py`: иначе strict ReadWritePaths после reboot обращались бы к отсутствующим файлам `/run`.

## Остаточные риски

- Орехово требует доступного management path; обновление не выполнено.
- Следующий restart TimeWeb / Docker требует свежего scoped recovery и повторной полной проверки. Универсальное устойчивое boot-recovery — отдельная незавершённая работа.
- `backup_local.py` должен проверять состав по текущему реестру вместо hardcoded 52, не обходить отказ.
- Hold qemu-guest-agent сохранён; решение о снятии требует проверки требований провайдера.
