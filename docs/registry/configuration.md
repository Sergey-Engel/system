---
type: registry
status: current
updated: 2026-10-20
---

# Реестр конфигурации

## Источники

Live hosts определяют применённое состояние. Этот checkout хранит исходники
и описание; [.local/secrets.json](../../.local/secrets.json) хранит переносимые
private files. [.local/config/hosts](../../.local/config/hosts) содержит точные
базовую материализацию VERIFIED backups 10 октября. Последующие changesets
обновляют явно указанные masters; это не автоматически обновляемый mirror.
Stage-каталоги и архивы прежних выпусков не являются deployment masters.

| Компонент | Локальный источник / снимок | Live размещение |
| --- | --- | --- |
| SSTP Нахимова - TimeWeb | [Source/runbook](../../services/transport/sstp-timeweb/README.md), [inventory](../../config/inventory/sstp-timeweb.json) | Release1.1.1, 91.222.238.208:443 -> isolated namespace/PPP. Autostart/reboot и soak904.9s/26 samples приняты. Production routing/failover выключены. Старые VPN configs/keys сохранены при согласованном OS maintenance. CPU control plane остаётся высоким. [Протокол](../history/2026-10-20-timeweb-maintenance-sstp-newip.md) |
| Direct SSTP / Device routing | `device_routing.py`, `routing_panel.py`, `direct_*.py`, `sstp_direct.py` в `services/transport/site-to-site/`, `.local/config/sstp-direct/`, отдельный [inventory](../../config/inventory/direct-sstp.json) | Нахимова `.64.2` client -> Фетхие TCP443/5443 `.64.1`; один канал, controller3.0.0. Unified Nakhimova static DHCP: Standard/Cenuta/Fornex/Direct; Fethiye Wi-Fi: Standard/Direct. Facade19118, общий lock, routing intent и независимые Direct state/audit. Два user LaunchAgents. TimeWeb без изменений. [Runbook](../operations/Direct_SSTP.md) |
| LAN device names | [Full-MAC bindings](../../config/inventory/lan-devices.json), `direct_names.py`, rebuildable IEEE snapshot `.local/cache/mac-vendors.json` | Unified UI: только exact inventory, иначе Unknown device. DHCP/IEEE fallback остаётся только в legacy read API. Не VPN inventory, не authority для выбора маршрута |
| TimeWeb Xray | `.local/config/hosts/timeweb/current/host/opt/timeweb-reality/` | `/opt/timeweb-reality/`, `xray-timeweb-reality.service` |
| TimeWeb WG selector | `.local/config/hosts/timeweb/current/host/opt/wg/`, `opt/wg-router/` | `wg-relay`, `/opt/wg/config`, `/opt/wg-router` |
| TimeWeb S2S | `.local/config/hosts/timeweb/current/host/etc/wireguard/` и exact systemd files; [IPIP Local changeset](../architecture/Site_to_Site_Egress_Changeset.md) | Root namespace `wg-s2s`, `10.60.60.1/29`, UDP 51860; Нахимова `.2`, Фетхие `.3`, LAN-пара `.88/24` ↔ `.89/24` и exact protocol 4 outer pair; host services и прочий transit закрыты; Remote client выключен |
| BTH recovery | Текущий snapshot `opt/timeweb-reality/bth-recovery/`; код `services/transport/timeweb-reality/bth_recover.sh` | `bth-recovery.service/timer`, peer `.5` и полный routing contract |
| FLEX | `services/transport/timeweb-reality/flex_*.py`, fleet и текущие controller/state snapshots | `/usr/local/sbin/timeweb-flex-*`, три controller timers, `timeweb-flex-fleet` |
| Runtime recovery | `services/monitoring/timeweb-uplinks/pilot/runtime_recovery.py`, текущий `opt/vpn-runtime-recovery/` snapshot | `vpn-runtime-recovery`, проверяемая policy generation; timer не публикует policy |
| Monitoring guards/console | `services/monitoring/timeweb-uplinks/`, текущий `opt/vpn-monitoring/` snapshot | Collector/exporter/console и отдельный monitoring manifest |
| Fornex WG/AWG/Amnezia | `.local/config/hosts/fornex/current/host/` и `containers/` | `wg-exit`, `fornex-awg31`, Amnezia containers |
| Cenuta WG/guard | `.local/config/hosts/cenuta/current/host/etc/` | `wg-cenuta`, `/etc/reality-c3`, nftables |
| UDP/WSS | `services/transport/timeweb-reality/wstunnel-*-backup/`; private PKI и свежие host snapshots | Отдельные WG/Xray backend UDP/WSS controllers |
| Нахимова | `.local/config/hosts/nakhimova/current/router-export.rsc` | hAP ax3, serial `HKM0BDXYG74`; свежий sensitive export и encrypted binary backup |
| Фетхие | `.local/config/hosts/fethiye/initial/` (неизменный baseline), `current/` обновлен по post-SSTP backup19 октября | hAP ax3 `HM20B6QXS8H`, LAN `.89/24`, прежние WG/IPIP сохранены; новый `sstp-direct-in` `.64.1`, `sstp_direct` table, prepared device controls disabled после проверки; MacBook Local. VERIFIED_TRANSFER без restore drill; [SSTP checkpoint](../history/2026-10-19-sstp-direct-permanent.md) |
| Орехово | Карточки `docs/hosts/orekhovo/` | hEX RB750Gr3; свежий backup заблокирован недоступностью площадки, старые backups не перенесены |
| Профили | `.local/clients/`, точные байты из secret store | 67 файлов: 38 WG, 11 AWG31, 9 SOCKS, 9 XRAY; новые S2S WG относятся к роутерам, не к MacBook |
| Устройства/метрики | `config/inventory/observations.json` | 22 устройства; новый `timeweb-s2s` читает host WG, не контейнер |
| Профили/checksums | `config/inventory/clients.json` | Реестр выданных файлов; не доказательство активности |
| Local monitoring | `services/monitoring/vpn-connectivity/compose.yaml`, `.local/runtime/monitoring/` | Те же Docker project/container names и закреплённые image digests |
| Mac integration | `scripts/setup_mac.py`, существующие SSH identities в private store | Сгенерированные aliases, три user LaunchAgents, `timeweb-vpn` |

Все пути в backticks относительно корня, кроме явно указанных live `/opt`,
`/etc`, `/usr` paths. Подробное [хранение и перенос](../operations/storage-and-transfer.md).

## Состояние Проверок

65 исходных profiles сохранены без изменения байтов и SHA-256;
16 октября добавлены два инфраструктурных WG profiles. При включении LAN
у них изменены только AllowedIPs, без ротации ключей и endpoint.
11 старых AWG aliases в transport сравнивались по параметрам с текущими
клиентскими файлами и не переносились как второй набор профилей.
Текущие VPS snapshots прошли состав, source drift и offline restore checks.
Не переносились старые configs/backups, vendor binaries и stage credentials.

16 октября: новый TimeWeb backup `2026-10-16T101524Z_current-config`, VERIFIED,
386 host files, 61 обязательный файл прошел offline restore verification.
Новый контур представлен шестью exact files и runtime/guard captures.
Существующие contracts и защищенный wg-relay snapshot не изменились;
recovery generation/monitoring manifest не переподписывались.
Детали и ограничения: [checkpoint пилота](../history/2026-10-16-fethiye-timeweb-pilot.md).

Второе плечо: post-backup TimeWeb `2026-10-16T120448Z_current-config`, VERIFIED
(386 host files, 61 offline restore checks); Нахимова `20261016T120449Z`,
VERIFIED_TRANSFER. RouterOS Нахимова live `7.24.4`, новый адрес `.2/29`.
LAN и default routes не менялись. [Changeset второго плеча](../architecture/Nakhimova_TimeWeb_Second_Leg_Changeset.md).

Последующий LAN-подшаг: только `.88/24` ↔ `.89/24`, без NAT/default/DNS изменений.
Post-backups TimeWeb `2026-10-16T124355Z_current-config` VERIFIED,
Фетхие `20261016T124357Z-post-s2s-lan` и Нахимова `20261016T124635Z`
VERIFIED_TRANSFER. 65 прочих профилей и старые contracts сохранены;
новая роль `WG-S2S-TW (LAN)` отображается в двух S2S observations.
[Checkpoint и ограничения](../history/2026-10-16-site-to-site-lan.md).

IPIP Local-подшаг: два router profiles добавляют только opposite outer `/32`;
65 остальных profiles и WG identities/endpoints не менялись. TimeWeb guard
и manifest updated, WG config/routes сохранены. Current post-backups:
TimeWeb `2026-10-16T142629Z_current-config`, Фетхие `20261016T143653Z-post-egress`,
Нахимова `20261016T143155Z`. MacBook Local HTTPS принят, Remote Internet нет.
ICMP loss и DNS discrepancy не маскируются WG green;
[подробные gates и evidence](../history/2026-10-16-egress-local.md).

Ограниченные Remote-пробы 16 октября: IPv4/HTTPS и возврат Local приняты
на MacBook; его прежний lease закреплен static. 67 профилей, inventory/fleet,
WG identities и защищенное host state не менялись, re-sign не требовался.
Current post-backups: TimeWeb `2026-10-16T155615Z_current-config`,
Фетхие `20261016T160037Z-post-egress`, Нахимова `20261016T160237Z`.
[Результаты, две попытки и мониторинг](../history/2026-10-16-egress-trials.md).

17 октября: ограниченный IPv4/HTTPS IPIP outage принят с предупреждением
первого recovery LAN ping 2/3. Финальный MacBook Local подтвержден;
router configuration bodies, 67 profiles, inventory/fleet и host contracts
неизменны. Console/Prometheus/persisted Grafana и два post-Local cycles
проверены, re-sign/restart не требовались. Current router backups:
Фетхие `20261017T084141Z-post-egress`, Нахимова `20261017T084227Z`,
оба VERIFIED_TRANSFER. Post VPS backups VERIFIED: TimeWeb
`2026-10-17T083751Z_current-config`, Fornex `2026-10-17T083920Z_current-config`,
Cenuta `2026-10-17T083947Z_current-config`.
[Объем приемки, потери и ограничения](../history/2026-10-17-egress-fail-closed.md).

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
