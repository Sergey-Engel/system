---
type: registry
status: current
updated: 2026-10-10
---

# Реестр конфигурации

## Источники

Live hosts определяют применённое состояние. Этот checkout хранит исходники
и описание; [.local/secrets.json](../../.local/secrets.json) хранит переносимые
private files. [.local/config/hosts](../../.local/config/hosts) содержит точные
текущие файлы из свежих VERIFIED backups 10 октября, не автоматически обновляемый
mirror. Stage-каталоги и архивы прежних выпусков не являются deployment masters.

| Компонент | Локальный источник / снимок | Live размещение |
| --- | --- | --- |
| TimeWeb Xray | `.local/config/hosts/timeweb/current/host/opt/timeweb-reality/` | `/opt/timeweb-reality/`, `xray-timeweb-reality.service` |
| TimeWeb WG selector | `.local/config/hosts/timeweb/current/host/opt/wg/`, `opt/wg-router/` | `wg-relay`, `/opt/wg/config`, `/opt/wg-router` |
| BTH recovery | Текущий snapshot `opt/timeweb-reality/bth-recovery/`; код `services/transport/timeweb-reality/bth_recover.sh` | `bth-recovery.service/timer`, peer `.5` и полный routing contract |
| FLEX | `services/transport/timeweb-reality/flex_*.py`, fleet и текущие controller/state snapshots | `/usr/local/sbin/timeweb-flex-*`, три controller timers, `timeweb-flex-fleet` |
| Runtime recovery | `services/monitoring/timeweb-uplinks/pilot/runtime_recovery.py`, текущий `opt/vpn-runtime-recovery/` snapshot | `vpn-runtime-recovery`, проверяемая policy generation; timer не публикует policy |
| Monitoring guards/console | `services/monitoring/timeweb-uplinks/`, текущий `opt/vpn-monitoring/` snapshot | Collector/exporter/console и отдельный monitoring manifest |
| Fornex WG/AWG/Amnezia | `.local/config/hosts/fornex/current/host/` и `containers/` | `wg-exit`, `fornex-awg31`, Amnezia containers |
| Cenuta WG/guard | `.local/config/hosts/cenuta/current/host/etc/` | `wg-cenuta`, `/etc/reality-c3`, nftables |
| UDP/WSS | `services/transport/timeweb-reality/wstunnel-*-backup/`; private PKI и свежие host snapshots | Отдельные WG/Xray backend UDP/WSS controllers |
| Нахимова | `.local/config/hosts/nakhimova/current/router-export.rsc` | hAP ax3, serial `HKM0BDXYG74`; свежий sensitive export и encrypted binary backup |
| Орехово | Карточки `docs/hosts/orekhovo/` | hEX RB750Gr3; свежий backup заблокирован недоступностью площадки, старые backups не перенесены |
| Профили | `.local/clients/`, точные байты из secret store | Импорт на устройствах; 65 файлов: 36 WG, 11 AWG31, 9 SOCKS, 9 XRAY |
| Устройства/метрики | `config/inventory/observations.json` | 21 устройство; один inventory для probe и Grafana |
| Профили/checksums | `config/inventory/clients.json` | Реестр выданных файлов; не доказательство активности |
| Local monitoring | `services/monitoring/vpn-connectivity/compose.yaml`, `.local/runtime/monitoring/` | Те же Docker project/container names и закреплённые image digests |
| Mac integration | `scripts/setup_mac.py`, существующие SSH identities в private store | Сгенерированные aliases, три user LaunchAgents, `timeweb-vpn` |

Все пути в backticks относительно корня, кроме явно указанных live `/opt`,
`/etc`, `/usr` paths. Подробное [хранение и перенос](../operations/storage-and-transfer.md).

## Состояние Проверок

65 опубликованных profiles скопированы без изменения байтов и SHA-256.
11 старых AWG aliases в transport сравнивались по параметрам с текущими
клиентскими файлами и не переносились как второй набор профилей.
Текущие VPS snapshots прошли состав, source drift и offline restore checks.
Не переносились старые configs/backups, vendor binaries и stage credentials.

Старый `maintenance_preflight.py` по-прежнему проверяет строгую историческую
форму BTH baseline. На свежих snapshot files он отказал: hash `hostguard`
и общий Xray/hostguard master не совпали с legacy baseline. Это не повод
переподписать контракт. Current runtime recovery `check`, collector и console
проверяются отдельно; см. [отчёт миграции](../migration/2026-10-10-execution-report.md).

## Правила изменений

- WG mutators retired; старый stage или export не использовать как deployment.
- Approved master change обновляет secret store, profile catalog, observation
  inventory, fleet, docs и тесты вместе. Изменение профиля не должно оставлять
  старые identities в мониторинге или stale runtime-policy binding.
- Согласовывать BTH, monitoring manifest, controller hashes и console sandbox
  отдельно. Публиковать только reviewed recovery policy; не auto-accept drift.
- Два fresh valid cycles, console read-back, Grafana device coverage и verified
  backup обязательны; issued/imported/accepted фиксируются отдельно.
- Процедура: [agent workflow](../operations/agent-workflow.md),
  [локальный skill](../../.agents/skills/create-timeweb-vpn-client/SKILL.md).
