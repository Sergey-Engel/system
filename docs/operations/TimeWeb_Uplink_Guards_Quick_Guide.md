---
type: quick-guide
status: historical-deployment-current-guards-unverified
created: 2026-09-11
updated: 2026-09-13
---

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.


## Текущий статус

Состояние служб: [TimeWeb_Uplink_Pilot_Quick_Guide](<TimeWeb_Uplink_Pilot_Quick_Guide.md>).
Live snapshot (source reference not migrated)
от **2026-09-13 14:45:01 UTC** подтверждает выключенные collector/exporter
(`inactive / dead / disabled`) и наличие каталогов состояния.

**Активность 22 guard rules, generation и ownership этим снимком не проверены.**
Каталог `/var/lib/vpn-uplink-guards` не доказывает applied state.
Нельзя писать «guard layer активен» или «ожидается generation=5» как текущий факт.

Исторически 2026-09-11 были установлены `guardctl.sh`, manifest и 22 правила
в namespace `wg-relay`; позже в тот же день был развернут ограниченный
collector с серверной `.venv`. Утверждение «collector и .venv еще не установлены»
описывает только ранний этап, не текущее отсутствие запущенного процесса.
Серверный Prometheus не входил в пилот.

Протокол и исходные проверки:
[agents/history/TimeWeb_Uplink_Guards_Deployment_2026-09-11](<../history/TimeWeb_Uplink_Guards_Deployment_2026-09-11.md>).
Master: [System/timeweb-uplinks](<../../services/monitoring/timeweb-uplinks/README.md>).

## Контракт guard helper

Helper проверяет boot, container identity, PID/start и network namespace;
сравнивает baseline, точные rules и ownership hash. Старый manifest после
reboot/recreate или изменения VPN-конфигурации нельзя считать применимым.
Auto-reapply guards не реализован ни разовым helper, ни daemon.

`check` подтверждает совпадение manifest с наблюдаемой конфигурацией,
**не доступность Интернета**. Generation возвращается из state, его нельзя
подменять фиксированным историческим числом. Даже `check` создает/открывает
каталог/lock, поэтому это не строго беззаписная команда обследования.
В данном документационном ревью helper не запускался.

`REFUSED manifest_invalid`, `namespace_generation_changed` и подобные
ошибки означают непригодность условий измерения, не remote DOWN.
Отсутствующая команда (`command not found` / exit 127) является ошибкой
диагностического окружения, не доказательством сетевого отказа.
При конфликте ownership, priority или lock нельзя удалять lock/state,
выполнять flush или ослаблять проверки.

## Разовая проба и batch

Разовый `guardctl.sh probe` использует interface-bound IPv4 HTTPS,
pinned target, нормальную TLS-проверку; curl connect timeout 3 s, total 5 s.

- `VALID_OBSERVATION curl_exit=0` с ожидаемым HTTP-кодом: валидный успех
  этого запроса, не приемка всего VPN.
- `VALID_OBSERVATION curl_exit=28`: валидный timeout, не успех канала.
- `UNKNOWN ... result_discarded`: результат нельзя использовать, даже
  если сырой curl успел вернуть HTTP 200.
- `UNKNOWN ... request_not_started` / `REFUSED`: проба не дала
  достоверного сетевого результата.
- Exit 0 helper обозначает валидность наблюдения, не UP.

Одноразовый target snapshot имеет expiry. После истечения его нужно заново
разрешить/проверить; нельзя бесконечно продлевать старую запись.
В локальном master постоянного daemon **реализован** TTL-aware DNS refresh.
Это отдельный контракт, а не автоматическое обновление старого файла
`/opt/vpn-monitoring/guards/probe-targets.json`.

Пилот использует отдельный `candidate/guardctl-batch.sh` и
`batch_probe.sh`; рабочий разовый helper не заменяется этим файлом.
Цикл 120 s, общий deadline 45 s; каждое upstream имеет две HTTPS-цели,
direct control служит сравнением. Batch снимает `wg show transfer` до и после
HTTPS: сохраняются только RX/TX-дельты без peer key и payload. Односторонняя
дельта от 128 bytes является диагностикой, а не основанием менять транспорт.
WG/firewall ABA не покрыт универсально.
Для разового helper не обещать все дополнительные проверки batch.

## Согласованный откат или возобновление

Это порядок будущих действий оператора, не команда выполнить их сейчас.

1. До любых изменений проверить текущий namespace, manifest, ownership,
   точный inventory rules и список процессов, способных запускать пробы.
2. Для отката остановить новые пробы. Helper rollback удаляет только
   совпавшие собственные rules 31000-31021/protocol 242.
   При чужих/дублированных rules или другой identity операция отказывается.
3. Проверить итоговый state и фактические rules. Повторный rollback рассчитан
   на уже отсутствующие собственные правила, но generation может измениться.
4. Не трогать routes, WG, клиентские rules, NAT и общий firewall ради мониторинга.
5. Для возобновления нужен свежий audit, backup, проверка обеих положительных
   проб и клиентского regression. Наличие старых scripts не разрешает apply.

### Изменение разрешенной сетевой схемы

Manifest намеренно сравнивает snapshot namespace целиком. Поэтому после
согласованного изменения route, firewall, peer или адреса collector откажется
от цикла с `manifest_invalid`, пока baseline не будет обновлен. Это защита, а
не сетевой диагноз. Для обновления: снять новый snapshot; доказать точный
ожидаемый diff от текущего baseline; сохранить manifest и ownership state;
остановить только `vpn-uplink-pilot.service`; заменить manifest и его SHA в
state как одну проверенную операцию; выполнить `guardctl ... check`; запустить
collector и подтвердить новую запись в SQLite/exporter. Нельзя обходить это
удалением state или отключением проверки.

2026-09-16 в baseline добавлены только два carrier-маршрута: `103.75.126.143/32
via 172.19.0.1 dev eth0` для Fornex и `89.252.153.129/32 via 172.19.0.1 dev
eth0` для Cenuta. Они удерживают WSS fallback вне соответственно `wg1` и
`wg-up-cenuta`, исключая рекурсивную маршрутизацию. До обновления manifest
такие изменения корректно вызывают fail-closed отказ collector.

`build_manifest.py`, `finalize_manifest.py`, `apply_live.sh` и
исторические timers не являются универсальными recovery-командами.
Нельзя исправлять отказ проверки редактированием runtime-state вручную.

## Исторический backup и приемка

Configuration backup до guards:
`.local/backups/timeweb/20260911T091052Z/timeweb-pre-uplink-guards.tar.gz`
относительно Dropbox. Состав, checksum и проверка распаковки сохранены
в протоколе deployment. Это не VM/disk snapshot и не автоматически актуальный
backup последующих изменений.

Восстановление требует проверки checksum, root-only staging, отдельной
проверки распакованного inventory и выбора конкретных файлов по diff.
Не накатывать старые routes/firewall/config поверх действующей системы.

Исторические результаты: 22 rules, идемпотентность, точный rollback,
130 совпавших route lookups, DNS/health и лабораторные проверки route ABA/late RST.
Они не доказывают активность guards сегодня, полный WG/firewall ABA coverage
или исправность конкретного клиента. Разовые успех/отказ Cenuta/Fornex
привязаны ко времени исходной пробы, а не к имени провайдера навсегда.
