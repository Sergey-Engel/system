---
type: checkpoint
status: local-candidate-deployment-blocked
created: 2026-10-17
updated: 2026-10-17
tags: [mikrotik, site-to-site, console]
---

# Межплощадочная Вкладка: Локальный Кандидат

Пользователь согласовал вкладку в прежней VPN-панели: статус, dropdown
устройств, выбранный список и крестик для возврата Local. Поручение «делай».
[План](../tasks/PLAN-site-to-site-console.md),
[runbook и границы](../operations/Site_to_Site_Console.md).

## Выполнено Локально

- Вкладки VPN/Site-to-site, lazy status, сохранение выбора при refresh,
  список Remote с удалением, pending/error/unknown и offline Remove.
- Фиксированный guarded controller с persistent selection, строгим SSH trust,
  per-device source/MAC/DNS/IPv6 rules, узким return, fresh DHCP identity,
  отказом stale requests и неизменными чужими profiles/default/NAT.
- Сериализация, durable intent, read-back вместо оптимистичного успеха,
  проверка полных полей и order в rows и export до закрепления hashes.
  Pending до включения guards не выдается за примененный Remote.
- Candidate console sandbox/tmpfiles paths и обязательный полный backup scope.
  Они не deployed и не являются сведениями о текущей установке.
- 445 tests PASS, включая 33 controller tests и реальные Chrome desktop/mobile
  проверки на fixture API. На скриншотах только тестовые устройства, не live
  маршрутизация. HTTP Host/Origin/CSRF и старые VPN/FLEX tests сохранены.
- Независимые повторные reviews и отрицательные reproductions: last rule-order
  race отклоняется до сохранения hashes и любых enable-команд.

## Почему Не Установлено

До первой сетевой записи существующий strict SSH к Нахимова завершился
banner timeout. ICMP TimeWeb -> `.60.2` дал 0/3; старый BTH management TCP
также недоступен. Фетхие -> Deco и Фетхие -> TimeWeb дали по 3/3.
Пользователь не может проверить площадку, наличие питания предполагает;
причина недоступности не установлена. Нет свежего verified baseline Нахимова.
Новые credentials/users/firewall rules не создавались; reboot, recovery
policy publish, изменение существующих users/keys и рестарты не выполнялись.

Read-only финальная сверка: export Фетхие совпал с исходным, все 10 Remote
controls disabled (Local). Host S2S bytes/runtime identity и 67 client profiles
неизменны. Live console.py/unit/tmpfiles совпали с verified pre-backup.
Runtime/BTH/monitoring contract checks PASS; это не доказательство доступности
Нахимова и не клиентская приемка нового controller.

Pre-backups: TimeWeb `2026-10-17T090825Z_current-config`, Fornex
`2026-10-17T090940Z_current-config`, Cenuta `2026-10-17T091012Z_current-config`
VERIFIED. Фетхие `20261017T091829Z-pre-egress` VERIFIED_TRANSFER, без live
restore. Нахимова `20261017T092003Z` BLOCKED; не подменен старой копией.

Private evidence: `.local/backups/site-to-site/20261017T092106Z-console/`.
Receipt: `LOCAL_CANDIDATE_VERIFIED_DEPLOYMENT_BLOCKED_NAKHIMOVA`.
Предпросмотр запущен отдельно и только для чтения; никакие production
controllers из него не запускаются. URL/PID в private runtime metadata.

## Осталось

Восстановить доступность Нахимова, получить свежие backups/baseline;
применить описанный management bootstrap и legacy MAC qualification,
установить controller/console с namespace/HTTP read-back и monitoring gates,
синхронизировать masters/store и проверить Add/Remove на MacBook физически.
Новая вкладка в действующей панели, многоклиентский Remote, reboot и
эксплуатационное постоянство пока не приняты.
