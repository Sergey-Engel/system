---
type: runbook
status: legacy-wg-change-gated
created: 2026-06-29
updated: 2026-09-27
tags: [wireguard, timeweb, runbook]
---

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.


# TimeWeb: создание клиента обычного WireGuard

## Область применения

Этот runbook относится **только к обычному WG** на UDP 51820/51850/51830. Он не создает REALITY, AWG 3.1 и не обслуживает удаленный AWG2. Выбор системы и текущие клиенты: [TimeWeb_VPN_Registry](<../registry/tunnels.md>).

Исторический helper находится на TimeWeb `/opt/wg-router/commands.sh`. При разработке он применял selector мягко через syncconf, но имел **fallback на полный recreate wg-relay**. После добавления REALITY BTH это особенно опасно: runtime-only peer и guards зависят от namespace.

**После отдельного исправления 13 сентября add/delete/regenerate и остальные старые mutators заблокированы на входе в функции.** Recreate fallback удален. Просмотр сохранен. Для добавления WG BTH peer появился ограниченный проверенный changeset `bth_client_changeset.py`: он применяет только заранее описанное добавление, требует свежий verified backup и проводит BTH recovery-контракт через проверяемые переходные состояния без перезапуска `wg-relay`. Это не универсальная замена старому helper: delete, regenerate, selector-маршруты и любой новый сценарий требуют отдельного reviewed changeset. Порядок работы: [VPN_Maintenance_and_Backup](<maintenance-and-backup.md>).

Даже без recreate изменение selector rules меняет полный RPDB, закрепленный BTH recovery-контрактом. При его несовпадении следующий штатный recovery удаляет peer `.5` (fail-closed). Поэтому план выдачи WG должен учитывать согласованное обновление BTH-контракта; не подписывать неизвестный drift автоматически.

## Подготовка

**Обязательное условие завершения:** после любого изменения состава профилей
выполнить [agents/runbooks/TimeWeb_Agent_Operations](<agent-workflow.md#обязательный-gate-мониторинга-при-изменении-тоннелей>).
Обновить inventory и проверить оба контракта: BTH recovery и monitoring
baseline; дождаться двух свежих валидных циклов и данных в Grafana.

1. Проверить SSH TimeWeb по [Host_Access_Guide](<access.md>), актуальный реестр, endpoint и свободный адрес.
2. Снять свежий backup persistent config, client registry/exports, native nftables и routes/rules; сохранить в System.
3. Сверить живой helper и предусмотреть BTH recovery/контракт, если операция может менять защищаемое состояние.
4. Определить route: `cenuta` / `fornex` selector или `bth` для обычного WG BTH. RU split настраивается отдельно; суффикс имени не заменяет rule/list.
5. Подготовить точный обратный diff. Не использовать общий firewall/rule flush.

## Исторический синтаксис заблокированных операций

Этот синтаксис оставлен для узнавания старых команд. Сейчас они возвращают `RETIRED`, даже после устного согласования; обходного флага нет. Нужен отдельный current changeset, если для операции нет уже проверенного ограниченного writer:

```text
/opt/wg-router/commands.sh add-client <client-name> cenuta
/opt/wg-router/commands.sh add-client <client-name> fornex
/opt/wg-router/commands.sh add-client <client-name> bth
/opt/wg-router/commands.sh delete-client <config-name>
/opt/wg-router/commands.sh regenerate-client <config-name>
```

Regenerate меняет ключи и делает прежний импорт нерабочим. Delete должен отзывать серверный peer, а не только удалять файл. Проверять фактическое поведение текущей версии helper перед запуском.

## Экспорты и выдача

На сервере встречаются:

- Selector: `/root/wg-client-exports/`.
- Legacy: `/opt/wg/clients/`.
- WG BTH: `/opt/wg/clients_bth/`.

Готовый файл проверить и скачать в **`.local/clients`**, chmod 600. Это постоянный каталог выдачи; Downloads и временный QR не являются master.

`wg-client-config` / `commands.sh show-client` могут показывать полный config и QR, а интерактивно также удалять/перегенерировать клиента. Использовать только в приватном терминале; не отправлять вывод в Obsidian/чат.

## Проверка

| Route | Endpoint | Ожидаемый IPv4 для выбранного Internet-теста |
| --- | --- | --- |
| cenuta | `94.241.171.65:51850/UDP` | `89.252.153.129` |
| fornex | `94.241.171.65:51850/UDP` | `103.75.126.143` |
| bth | `94.241.171.65:51830/UDP` | Внешний адрес Дом.ру в момент теста |

Сверить runtime peer и persistent block, route rules/native RU-list, существующие peers и старты контейнеров. На клиенте проверить DNS, HTTPS, внешний IP, IPv6-поведение и нужные private exceptions. `::/0` в файле не гарантирует отсутствие IPv6 leak во всех клиентских реализациях.

Read-only helper: `wg-status`, `wg-status --active`, `wg-status --interface wg-clients`, `/opt/wg-router/commands.sh sessions --json`. Свежий handshake не равен проверке браузера.

После выдачи синхронизировать master/export/реестр; отдельно записать подтверждение устройства. Полный порядок хранения: [VPN_Configuration_Registry](<../registry/configuration.md>). Для BTH изменения не считать созданный 17 сентября writer общим CLI: он привязан к одному reviewed changeset и не применяется к другим устройствам без новой реализации и тестов. Новые контуры: [Fornex_AWG31_Operations](<Fornex_AWG31_Operations.md>), [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>).
