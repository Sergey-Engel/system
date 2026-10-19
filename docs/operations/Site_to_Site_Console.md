---
type: runbook
status: local-candidate-not-deployed
created: 2026-10-17
updated: 2026-10-17
---

# Управление Межплощадочным Выходом

**19 октября:** постоянный Direct SSTP и управление установлены через
[локальную facade прежней панели](Direct_SSTP.md). Server-side TimeWeb
candidate, описанный ниже, не разворачивался и не требуется для Direct SSTP.
Не применять его management/bootstrap шаги как инструкцию текущего контура.

**17 октября: локальная реализация, не опубликована в действующей панели.**
При подготовке панели Нахимова была недоступна по прежнему SSH/BTH и S2S ICMP. Проверки Фетхие -> Deco
и Фетхие -> TimeWeb прошли 3/3. Причина недоступности Нахимова не установлена;
питание не проверено. Сетевые настройки и действующая панель не менялись.
[План и границы](../tasks/PLAN-site-to-site-console.md).

**Уточнение после восстановления доступа 17 октября:** SSH и S2S вновь
доступны; последующие прямые transport trials полностью удалены, оба текущих
роутера совпадают с исходным baseline. Панель по-прежнему **не развёрнута**:
восстановление связи не заменяет management bootstrap и deployment gates.
[Результат проверки сети](../history/2026-10-17-direct-tunnel-feasibility.md).

## Поведение

Вкладка Site-to-site существующей VPN console обслуживает направление
Fethiye -> Nakhimova. Тоннель независим от списка устройств. Dropdown содержит
только online DHCP-клиентов bridge MikroTik Фетхие. Deco не включается.
Add выбирает удаленный выход, крестик возвращает Local. Кнопки блокируются
на время команды, результат определяется read-back, не оптимистичным UI.

Статусы: local, remote, blocked, pending, unknown. Remote означает проверенную
конфигурацию и готовый маршрут, не свежую клиентскую HTTPS-приемку. При сбое
Add до применения guards статус Pending прямо предупреждает о возможности
местного выхода: это еще не подтвержденный Remote. Прерванное Remove не
скрывает устройство из выбранных до подтвержденного Local. При отказе
controller последнее известное выделение остается видимым как Unknown,
действия недоступны. При недоступной Нахимова Remove возможен, если конфигурация
Фетхие успешно проверена. Переподключение не снимает сохраненный выбор.

MAC относится к текущей Wi-Fi-сети. Ротация частного MAC создает новую identity;
автоматического сопоставления по одному имени/IP нет. Static DHCP reservation
сохраняется после Remove, адрес/gateway/DNS не меняются. Offline выбранные
устройства остаются в списке. Список VPN-профилей и DHCP-список не смешиваются.

## Controller

Код: [controller.py](../../services/transport/site-to-site/controller.py),
[managed.py](../../services/transport/site-to-site/managed.py),
[router.py](../../services/transport/site-to-site/router.py).
Фиксированный launcher `/usr/local/sbin/timeweb-s2s` запускает
`/usr/bin/python3 -B /opt/vpn-s2s/controller.py`. Нет shell-команд из HTTP.
CLI: `status` либо `add|remove <MAC> <revision>`. Параметры allowlisted,
revision привязан к актуальным lease ID/MAC/IP и сохраненному выбору.
HTTP `/s2s-action` использует прежние Host/Origin/CSRF проверки console.
Отдельный ленивый cache 15 s не задерживает действующий VPN-раздел.

Приватные root-owned файлы, mode 600, dirs 700:

- `/etc/vpn-s2s/config.json`: version 1, `dhcp_server`, `baseline` и
  `legacy_hashes` для обеих площадок; только свежий reviewed baseline.
- `/etc/vpn-s2s/ssh_config`, `known_hosts`, `id_fethiye`, `id_nakhimova`:
  два strict aliases, User `s2s-console`, BindAddress `10.60.60.1`,
  HostKeyAlias каждой площадки, pinned ранее доверенные host keys,
  IdentitiesOnly/BatchMode/StrictHostKeyChecking=yes, ForwardAgent=no.
- `/var/lib/vpn-s2s/state.json`: version 1, monotonic generation, clients
  с MAC/IP, binding intent, selected/pending/operation и pinned object hashes.
- `/var/lib/vpn-s2s/actions.jsonl`: результаты команд без ключей/паролей.
- `/run/timeweb-s2s/`: короткоживущие OpenSSH control sockets;
  `/run/lock/timeweb-s2s.lock`: один writer для status и изменений.

Новые клиенты получают 10 source/MAC/DNS/IPv6 controls Фетхие, два flow rules
на каждой стороне и три узких return objects Нахимова. Прежние транспорт,
default/NAT, keys/endpoints и LAN маршруты не расширяются на все устройства.
Legacy MacBook использует прежний preset; до запуска controller необходимо
добавить проверенную MAC-привязку только к его исходящему flow rule.

## Предстоящий Deployment

1. Дождаться доступности Нахимова; повторно проверить обе serial/host keys,
   current/master, contracts и свежие VERIFIED backups. Не считать незавершенный
   preflight готовым baseline и не перезапускать старые one-shot deployment CLIs.
2. Создать отдельные management keys и custom RouterOS group с только
   `ssh,read,write,test`. Учетные записи допускают только hub `.60.1`.
   Существующие пользователи, пароли и ключи не ротируются. RouterOS не умеет
   ограничивать write только owner-комментариями: эту границу обеспечивает
   проверяемый controller; host credentials остаются root-only.
3. Разрешить только hub -> router S2S TCP 22 в соответствующем input chain
   обоих роутеров. На TimeWeb добавить только исходящий TCP 22 к `.2/.3` и
   established replies в собственной таблице S2S. Не открывать публичный
   management и не менять forward/LAN policies. Обновить только reviewed
   S2S guard/manifest, проверить exact diff и независимые старые contracts.
4. Усилить legacy flow MAC-проверкой, сохранить новый baseline после всех
   одобренных bootstrap изменений. До пользовательского Add все клиенты Local.
5. Разместить controller, зависимости egress/lan и launcher, приватные config,
   keys/state. Не перезаписывать уже существующее state. Применить только
   точные дополнительные console ReadWritePaths и tmpfiles paths из candidate
   unit. Создать их до restart console; не ослаблять ProtectSystem/ProtectHome.
6. Проверить status внутри mount namespace работающей console и HTTP, прежние
   VPN/FLEX controls, Prometheus/Grafana mappings, два валидных collector cycles
   и отдельно BTH/monitoring/runtime checks. Не переподписывать unknown drift.
7. Синхронизировать canonical private store и masters. Backup coverage включает
   `/opt/vpn-s2s`, `/etc/vpn-s2s`, `/var/lib/vpn-s2s`, launcher, unit/tmpfiles;
   неполный состав не принимается. Новые SSH identities не являются новыми
   клиентскими VPN profiles; состав inventory остается прежним, пока не изменен
   отдельным согласованным scope.
8. Ограниченным окном проверить Add/HTTPS/Remote IP/Remove/Local IP только
   на MacBook с физическим подтверждением владельца. Reboot и произвольные
   другие устройства не считать принятыми по fake-router тестам.

Rollback: вернуть только reviewed изменения console/controller/management
scope, с предварительным явным Local read-back для выбранных клиентов.
Удаление UI или процесса само по себе не возвращает клиентов в Local.
Не удалять state/ключи/guards прежде, чем подтверждено фактическое состояние.

Документация производителя: [политики RouterOS и SSH keys](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User),
[DHCP make-static](https://help.mikrotik.com/docs/spaces/ROS/pages/24805500/DHCP).
