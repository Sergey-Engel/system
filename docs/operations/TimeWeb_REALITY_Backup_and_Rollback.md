---
type: runbook
status: current
created: 2026-09-12
updated: 2026-09-23
---

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.


# REALITY: резервные копии и точечный откат

## Текущий статус

REALITY установлен: Fornex, Cenuta, BTH и пилотный FLEX обслуживаются одним Xray на TimeWeb. Активны BTH recovery и FLEX reconcile timers. Фразы прежней версии «установка не согласована» и «откатывать нечего» относились к подготовке 12 сентября и больше не описывают runtime.

Данный документ **не поручение выполнить откат**. В ревью 13 сентября ничего не откатывалось. Полные исходные материалы прежней версии сохранены в `services/transport/documentation-audit-20260913/before/`.

## Слои восстановления

| Набор | Назначение | Ограничение |
| --- | --- | --- |
| `Mikrotik/backups/timeweb/2026-09-12T1550Z_pre-reality/` | Состояние TimeWeb до REALITY | Не включает последующие изменения |
| `Mikrotik/backups/fornex/2026-09-12T1553Z_pre-reality/` | Выбранный pre-REALITY backup Fornex с Unbound | Не версия 1550Z без полного DNS-состава |
| `Mikrotik/backups/cenuta/2026-09-12T1550Z_pre-reality/` | Состояние Cenuta до нового peer | Не современный after-state |
| `transport/timeweb-reality/stage4-fornex/` | Точный Fornex peer/guard diff | Только свой manifest/поколение |
| `transport/timeweb-reality/stage56-timeweb/` | Первоначальный Xray/host guard | Старее Cenuta и BTH |
| `transport/timeweb-reality/stage8-cenuta/` | Cenuta before/after и host config двух выходов | Старее BTH |
| `transport/timeweb-reality/stage9-bth/` | BTH peer/guards, RouterOS before/after и общий config трех выходов | Runtime peer; контракт зависит от текущей топологии |
| `transport/timeweb-reality/bth-recovery-release/` | Recovery scripts, units, baseline и contract | Не универсальный redeploy |
| `Mikrotik/backups/timeweb/2026-09-23T082407Z_current-config/` | Проверенный configuration snapshot после FLEX | Не полный образ VPS; содержит действующие секреты |
| `transport/timeweb-reality/flex_pilot.py`, `flex_guard.nft` | Логика и границы отдельного peer `.39` | Не заменяют runtime snapshot или живую сверку |
| `transport/fornex-awg31/retirement-backup/` | История удаления AWG2 | Не часть REALITY rollback; не возвращает AWG2 автоматически |

Все пути от System. Архивы конфигурационные, не образы дисков; permissions 700/600 не являются шифрованием.

Для трех выбранных pre-REALITY архивов ранее проверены SHA-256, чтение tar/gzip, внутренние хеши, извлечение защищаемых конфигов и сравнение до/после сбора. Полный disaster-recovery на чистых VPS не проверялся.

**Backup-инструменты исправлены отдельным этапом 13 сентября.** Schema 3 включает AWG31, Cenuta `reality-c3`, startup guards, текущие контейнеры и обязательные файлы каждого сервиса. Добавлены общий завершающий пересчет источников, metadata, предел записи на VPS и локальное пробное восстановление. Команды и критерии: [VPN_Maintenance_and_Backup](<maintenance-and-backup.md>).

Retirement-backup содержит не только отозванные AWG2-ключи, но и действующие AWG31 server/MacBook/iPhone credentials в `credentials.before.json`. Его нельзя считать безопасным для публикации архивом нерабочих ключей.

## Перед любым изменением

1. Проверить независимый SSH и правильные хосты; заранее иметь проверенный доступ к консоли провайдера.
2. Создать свежий configuration backup и скачать в System. Не полагаться только на pre-REALITY копии.
3. Снять hashes активного Xray, guards, WG persistent config; container ID/PID/StartedAt и netns identity; маршруты/rules и **native nftables**, не только iptables.
4. Сопоставить состояние с manifest конкретного этапа и всеми последующими изменениями. При drift остановиться и подготовить новый точный inverse diff.
5. Сохранить старые WG peers, client registries и Docker objects как защищаемые объекты. Содержимое конфигов не печатать в общий журнал.

## Правильный порядок отката

Поздние изменения зависят от ранних. Нельзя применить `stage56` или `stage9-bth` поверх текущего четырехвыходного WG config и назвать это точечным откатом. Следующие пункты описывают зависимости, а не готовые команды для текущего runtime.

1. При снятии FLEX сначала зафиксировать текущий desired/runtime state, остановить `timeweb-flex-macbook.timer` и дождаться oneshot. Снять только Xray identity/outbound FLEX, peer `.39`, его `PreUp` quarantine, отдельные RPDB/nft-правила и соответствующее разрешение host guard по проверенному текущему diff; другие identity, peers и транспорты сохранить. Перед изменением RPDB обновить BTH recovery contract в одной согласованной операции: иначе следующий цикл может fail-closed снять BTH peer.
2. При снятии BTH сначала остановить/отключить **bth-recovery.timer** и дождаться завершения oneshot, иначе он может восстановить удаляемые объекты. Подготовить inverse diff от текущего Xray config, а не заменять его историческим `stage9-bth/config.before`.
3. Если требуется убрать Cenuta REALITY, сверить текущий runtime и адресно удалить только новый peer `.3`/source guard и соответствующие Xray users/outbound. Старый peer `.2` сохранить.
4. Для удаления всего REALITY сначала остановить Xray, сохраняя guards до остановки; далее адресно снять собственные объекты TimeWeb и peer `10.20.0.3` на Fornex. Старые `wg-relay`, `wg-exit`, `wg-quick@wg-cenuta` не перезапускать.
5. Обновить локальный master, отозвать соответствующие client credentials и убрать только их действующие экспорты. Историю и backup сохранить.
6. Проверить независимый SSH, старый WG-клиент, оставшиеся REALITY-выходы, routes/rules и контейнерные идентичности; записать фактический diff.

Исторические CLI `stage9_bth.py`, `stage8_cenuta.py`, `stage56.py`, `stage4_fornex.py` теперь заблокированы. Их код и manifests оставлены как материал для отдельно подготовленного текущего inverse diff, а не как готовые команды отката.

## Recovery и отказ

- `bth-recovery.service` нормально имеет `inactive` между запусками; важны Result, exit status, timer и свежесть `/run/bth-recovery-state.json`.
- `restored=false` при успешном цикле означает «изменения не понадобились».
- При смене контейнера/маршрутов/config несовпадающий контракт не должен автоматически приниматься.
- При неуспешном штатном recovery после закрепления namespace helper удаляет только собственный peer `.5`. В контракт входит весь RPDB: новый selector rule может вызвать fail-closed отключение REALITY BTH. `--check` не удаляет peer. Планировать обновление контракта вместе с такими WG-изменениями, а не после необъясненного обрыва.
- Runtime-only BTH peer и guard требуют проверки после reboot/recreate. Контролируемое восстановление своего peer/guard ранее проверялось; полный такой regression не закрыт.
- Без нового согласования recovery нельзя расширять до общего auto-reapply маршрутов, firewall или старых monitoring guards.

## Запрещенные shortcuts

Не выполнять общий `ip route/rule flush`, `iptables -F`, `nft flush ruleset`, восстановление полного старого ruleset поверх работающего Docker, рестарт Docker/network или reboot ради scoped rollback.

Изученный runtime WG endpoint может отличаться от persistent Endpoint. Не применять целиком старый WG config ради удаления одного нового peer. Не отключать SSH host-key verification для «починки» доступа.

Связи: [VPN_Configuration_Registry](<../registry/configuration.md>), [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>), [Host_Access_Guide](<access.md>), [Fornex_AWG31_Operations](<Fornex_AWG31_Operations.md>).
