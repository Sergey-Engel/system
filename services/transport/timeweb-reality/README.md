# TimeWeb REALITY: эксплуатационный код и исторические снимки

Обновлено 2026-09-23. **Развернуты Fornex, Cenuta, BTH и отдельный FLEX-пилот MacBook**: 16 клиентских REALITY-профилей и 13 независимых server-side identity. MacBook `SOCKS-TW-CEN` функционально проверен пользователем через Cenuta WSS fallback; FLEX выпущен, но ещё не проверен на MacBook. Новые SOCKS-профили Mac Mini и iPhone 12 ожидают импорта и приемки. `SOCKS-TW-FX-Mini` и `SOCKS-TW-FX-iPhone12` разделяют существующие device-specific Fornex identity; отдельные CEN SOCKS identity изолированы. Это не закрывает полную матрицу DNS/IPv6/fail-closed/reboot/stability.

## Действующий выпуск

- TimeWeb: host `xray-timeweb-reality.service`, TCP 443, `/opt/timeweb-reality/config.json`.
- Текущий runtime после 23.09: `/opt/timeweb-reality/config.json`, `/opt/timeweb-reality/guard.nft`, `/opt/timeweb-reality/guard.expected` и `/opt/timeweb-reality/bth-recovery/`. `stage9-bth/`, `stage56-timeweb/` и `bth-recovery-release/` остаются историческими снимками, **не** актуальным deploy master.
- Точка до FLEX: VERIFIED backup TimeWeb `.local/backups/timeweb/2026-09-23T074453Z_current-config/`; итоговая точка после сквозного теста и `PreUp` quarantine: VERIFIED backup `.local/backups/timeweb/2026-09-23T082407Z_current-config/`. Не откатывать этот релиз установкой старого stage9 целиком.
- Клиентские файлы для импорта: .local/clients (source reference not migrated). Исторические staging-клиенты не импортировать.
- Fornex/Cenuta/BTH/FLEX являются встроенными WG outbound одного Xray. Отдельного BTH worker нет.
- Внутренний DNS общий, два DoH через Fornex/Cenuta. BTH не гарантирует DNS-выход через Дом.ру.
- Резервы TimeWeb -> Fornex и TimeWeb -> Cenuta: `wstunnel-fornex-backup/` и `wstunnel-cenuta-backup/`. Native UDP остается основным; controller синхронно переключает relay и userspace Xray peer на mTLS WSS TCP/8443. Для Xray используются `127.0.0.1:51923` (Fornex) и `127.0.0.1:51924` (Cenuta); оба адреса разрешены в live `/opt/timeweb-reality/guard.nft` и `/opt/timeweb-reality/guard.expected`. Частный CA каждого WSS-сервера установлен в system trust store TimeWeb, TLS verification не отключается. Cenuta может войти в WSS резерв после двух квалифицированных native-UDP сбоев и не возвращается в native автоматически; Fornex остается ручным. Мониторинг выводит выбранный транспорт в карточку соответствующего upstream и измеряет WG peer RX/TX вокруг HTTPS batch.

### FLEX-пилот MacBook

25 сентября 2026 FLEX расширен на Mac Mini: `.local/clients/Sergey/MacMini/SOCKS-TW-FLEX-S-Mini.json`, отдельные `macmini-socks-flex` и `10.50.50.41/32`. Серверный маршрут, fleet `3/3 ready`, timer и BTH contract проверены; импорт и сквозной трафик на Mac Mini ещё не подтверждены. Предварительный VERIFIED backup: `.local/backups/timeweb/2026-09-25T054647Z_current-config/`.

- Новый профиль: `.local/clients/Sergey/MacBook/SOCKS-TW-FLEX-S-MacBook.json`. Новая identity `macbook-socks-flex` и WG peer `10.50.50.39/32`; старые профили не переписаны. Стартовое состояние: FX, RU-direct off. Сквозная приемка на MacBook ожидается.
- Операторский код: `flex_pilot.py` установлен на TimeWeb как `/usr/local/sbin/timeweb-flex-macbook`; состояние и audit в `/var/lib/vpn-uplink-pilot/`. `timeweb-flex-macbook.timer` раз в 30 с сверяет RPDB, nft guard и RU-mark после recreate. `wg-clients.conf` добавляет `PreUp` quarantine DROP для `.39` до загрузки peer и держит его до завершения сверки.
- Консоль `http://127.0.0.1:19118/` через `ssh -N timeweb-console` управляет только FX/CEN и RU on/off для этого peer. Общие FX/CEN native/WSS-переключатели остаются отдельными. Прямой RU означает публичный IP TimeWeb, не RUHOME/Дом.ру.
- `bth_recover.sh` теперь проверяет нормализованный Xray-конфиг и допускает только заранее указанные native/WSS endpoint FX/CEN. RPDB закреплен полными baseline с четырьмя фиксированными FLEX-правилами. `refresh_bth_contract.py` предназначен только для осознанного обновления проверенного контракта после ревью, а не для автоматического «исправления» drift.

## Состав master и история

| Каталог / файл | Роль |
| --- | --- |
| `stage4-fornex/` | Fornex peer 10.20.0.3 и guards, собственный manifest |
| `stage56-timeweb/` | Исходная установка Xray, unit, прежний Fornex-only config |
| `stage8-cenuta/` | Добавление Cenuta; before/after старее BTH |
| `stage9-bth/` | Исторический трехвыходный config, BTH guards, RouterOS exports/diff; не применять к live |
| `bth-recovery-release/` | Исторический helper и контракт до поздних native/WSS и FLEX изменений; не применять к live |
| `bth_recover.sh`, `refresh_bth_contract.py` | Код текущей проверки BTH и инструмент осознанного обновления контракта; live contract хранится на TimeWeb |
| `flex_pilot.py`, `provision_flex_pilot.py`, `flex_guard.nft` | Пилот MacBook, выпуск отдельной identity/peer и политика fail-closed |
| `wstunnel-fornex-backup/` | Master WSS/mTLS-резерва, оба unit-файла и ручной endpoint controller |
| `wstunnel-cenuta-backup/` | Независимый WSS/mTLS-резерв для `wg-up-cenuta`, отдельный CA и ручной controller |
| `vendor/` | Закрепленные binary artifacts и хеши |
| `lab/` | Синтетические ключи, Linux fixtures, результаты лаборатории; не VPS deployment |
| `manifest.json` | Исходный проект/резервы; не современный deploy manifest |
| `rollback_manifest_20260912.json` | Датированная pre-deployment точка, не автоматический откат текущего состояния |
| `*test*/`, `failclosed*/`, `cli-diagnostic*/` | Датированные результаты, включая неудачные; не удалять ради PASS |

## Правила запуска

Python только `python3 -B`. Не запускать старые `prepare*`, `stage56_target_update.py`, `issue_stage56_clients.py` поверх текущего поколения. Это этапные инструменты, не универсальное обслуживание профилей.

Исторические CLI `stage4_fornex.py`, `stage56.py`, `stage8_cenuta.py`, `stage9_bth.py`, `prepare_stage3.py`, `prepare_rollback.py`, `prepare_bth_recovery.py`, `stage56_target_update.py`, `issue_stage56_clients.py` теперь завершаются `RETIRED` до действий. Сохраненный код нужен для исследования исходного diff, а не повторного deployment. Поздние изменения откатываются раньше ранних; не делать общий firewall/route flush.

`run_backup.py all` / `backup_readonly.sh`: текущий schema-3 backup трех VPS. Включает AWG31, Cenuta reality-c3 и обязательный состав каждого контейнера. Проверяет источник за весь интервал, metadata, runtime drift и локальное пробное восстановление; не включает диски ОС, Docker images или monitoring DB. `--verify-only` проверяет локальный архив без SSH. Каталог: `.local/backups/<host>/<UTC>_current-config`.

`maintenance_preflight.py --check`: сверка исторических masters/current runtime и BTH-контракта без переподписания. После FLEX ожидается несовпадение с `stage9-bth`; не запускать старые prepare/deploy для устранения этого различия. `maintenance-wg/commands.sh` - локальный master обновленного серверного helper: просмотр сохранен, старые writers/неполный backup отключены, recreate fallback удален. `apply_maintenance_patch.py` устанавливает только эту проверенную замену helper с hash guard и резервной копией; это не универсальный deploy.

[Текущий порядок обслуживания и backup](<../../../docs/operations/maintenance-and-backup.md>).

BTH recovery закрепляет весь RPDB; при несовпадении после открытия namespace штатный helper удаляет свой peer `.5`. Поэтому даже добавление WG selector rule требует согласованной актуализации контракта. Это fail-closed зависимость, не универсальное автоисправление сети.

## Документы

- [Архитектура и открытые gates](<../../../docs/architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>).
- [Master/runtime registry](<../../../docs/registry/configuration.md>).
- [Backup и порядок отката](<../../../docs/operations/TimeWeb_REALITY_Backup_and_Rollback.md>).
- [Клиентский реестр](<../../../docs/registry/tunnels.md>).

Этот каталог содержит реальные ключи/PSK/UUID; директории 700, секретные файлы 600. Не копировать содержимое в Obsidian, чат или публичный Git.
