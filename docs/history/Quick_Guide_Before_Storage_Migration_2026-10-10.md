---
type: runbook
status: historical
updated: 2026-09-26
tags: [mikrotik, vpn, operations]
---

> Historical storage snapshot. Current paths and access: [Quick Guide](../quick-start.md).


# VPN: быстрая эксплуатационная проверка

## Доступ агентов к хостам

Перед первой SSH-командой агент обязан прочитать [Host_Access_Guide](<../operations/access.md>). Это
SSOT для доступа: там есть полные команды, проверка правильного узла, scoped
`known_hosts` и ограничения учётных записей. Не искать ключи в `System`, не
просить их содержимое и не копировать их в рабочую папку или сообщения.

| Узел | Адрес | Пользователь | Локальный private key |
| --- | --- | --- | --- |
| TimeWeb | `94.241.171.65` | `root` | `.local/ssh/codex_timeweb_audit_20260628` |
| Cenuta | `89.252.153.129` | `ubuntu` | `.local/ssh/codex_cenuta_audit_20260628` |
| Fornex | `103.75.126.143` | `root` | `.local/ssh/codex_fornex_audit_20260628` |
| MikroTik hAP ax3, Нахимова | `192.168.88.1` | `codex` | `.local/ssh/codex_mikrotik_20260704` |
| MikroTik hEX, Орехово | `192.168.88.1` | `codex_audit` | `.local/ssh/codex_mikrotik_orekhovo_audit_rsa` |

Оба MikroTik используют один IP, но это разные площадки. Перед подключением
к `192.168.88.1` определить текущую сеть Mac и использовать только команду
для соответствующей площадки из [Host_Access_Guide](<../operations/access.md>). Для Cenuta обязателен
`.local/ssh/known_hosts_cenuta`, для Орехово —
`.local/ssh/known_hosts_orekhovo`; не обходить проверку ключа хоста.

Если среда агента не может прочитать указанный файл в `~/.ssh`, это ограничение
среды, а не отсутствие данных доступа. Агент должен запросить разрешение на
использование конкретного существующего key path, не новый ключ и не пароль.

## Нахимова: административная SSH-консоль из внешней сети

Проверено 2026-09-26: Mac -> SSH TimeWeb -> контейнер `wg-relay` ->
`wg-home` -> MikroTik `10.30.30.2:22`. Домашний LAN IP `192.168.88.1`
для этого пути не требуется; публичные порты управления не открываются.
Используются существующие ключи и SSH-профиль `timeweb-console`:

```sh
ssh -i .local/ssh/codex_mikrotik_20260704 \
  -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.88.1 \
  -o ConnectTimeout=10 \
  -o 'ProxyCommand=ssh -o BatchMode=yes -o ClearAllForwardings=yes -o PermitLocalCommand=no timeweb-console docker exec -i wg-relay nc 10.30.30.2 22' \
  codex@10.30.30.2
```

`HostKeyAlias` проверяет ранее доверенный ключ Нахимова для `192.168.88.1`
в локальном `known_hosts`. При несовпадении остановиться, не отключать
проверку и не заменять ключ автоматически: Орехово имеет такой же LAN IP.
`ClearAllForwardings=yes` отключает ненужный console-forward только для
этого SSH-подключения к TimeWeb; работающую консоль не останавливает.

После входа проверить правильный узел:

```routeros
/system identity print
/system resource print
/user print detail where name=codex
```

Подтверждены hAP ax3, RouterOS и RouterBOOT `7.24.4` (проверено 27 сентября 2026) и пользователь `codex` с группой
`full` (административные права). Это проверенный доступ к RouterOS CLI,
не проверка WebFig/WinBox. Несмотря на права `full`, изменения выполнять
только по явному поручению и после свежего export/backup.

## Запуск консоли TimeWeb

На Mac Mini с настроенным SSH-профилем `timeweb-console`:

```sh
timeweb-vpn
```

Команда при необходимости запускает SSH-туннель, проверяет ответ консоли и
открывает [страницу управления VPN](http://127.0.0.1:19118/) в браузере.
Оставлять Terminal открытым не требуется. Проверить доступность можно командой
`timeweb-vpn status`, остановить запущенный ею туннель — `timeweb-vpn stop`.
Запуск выводит этапы проверки, `started/reused`, PID и время жизни SSH.
Это фоновый процесс: возврат shell prompt нормален, в `jobs` он не отображается;
повторный запуск не создает новый SSH, а переиспользует соединение.
После открытия браузера вывод остается в Terminal. Последние сообщения запуска:
`timeweb-vpn logs` (постоянный журнал `.local/runtime/timeweb-vpn/launcher.log`).
`stop` закрывает только принадлежащий launcher SSH, не серверные VPN-сервисы.
Консоль доступна только локально через SSH; порт `19118` не открывать во
внешнюю сеть. Короткая команда установлена на Mac Mini; на других Mac её нужно
установить локально и настроить SSH-профиль.

### Минимум по Prometheus и Grafana

- **Prometheus** забирает метрики TimeWeb и хранит временные ряды.
- **Grafana** показывает историю и текущие метрики в dashboard
  [TimeWeb Uplinks - Pilot](http://127.0.0.1:3000/d/timeweb-uplink-pilot/timeweb-uplinks-pilot?orgId=1&from=now-1h&to=now&timezone=browser&refresh=10s).
- **Консоль** показывает оперативный режим транспорта и выполняет только
  ручное переключение `native UDP` / `WSS backup`; она не заменяет Grafana.

`NO DATA` в Grafana означает, что нет доступных метрик для отображения. Это
не доказательство отказа VPN. Перед диагностикой проверить, что SSH-forward
и локальные monitoring services запущены, затем сверить состояние в консоли.

## Сначала определить контур

| Соединение | Где смотреть |
| --- | --- |
| WG в TimeWeb UDP 51820/51850/51830 | TimeWeb `wg-relay` и upstream |
| REALITY в TimeWeb TCP 443 | Host `xray-timeweb-reality`, user/outbound, guards |
| Прямой AWG 3.1 UDP 46056 | Fornex `fornex-awg31` |
| LAN-устройство Нахимова 11 | MikroTik address-list/mangle + TimeWeb; отдельно VPN-приложение устройства |
| Графики | Мониторинг, не процесс передачи трафика |

Схема [VPN_HLD](<../architecture/overview.md>), профили [TimeWeb_VPN_Registry](<../registry/tunnels.md>), master [VPN_Configuration_Registry](<../registry/configuration.md>). SSH и проверка правильного узла: [Host_Access_Guide](<../operations/access.md>).

## TimeWeb: только чтение

В SSH-сессии TimeWeb:

```sh
systemctl status xray-timeweb-reality --no-pager
systemctl status bth-recovery.timer --no-pager
systemctl show bth-recovery -p Result -p ExecMainStatus
cat /run/bth-recovery-state.json
docker inspect --format '{{.Name}} {{.State.Status}} {{.State.StartedAt}} {{.State.Pid}}' wg-relay
docker exec wg-relay wg show
docker exec wg-relay ip -4 rule
docker exec wg-relay ip -4 route show table 100
docker exec wg-relay ip -4 route show table 200
docker exec wg-relay ip -4 route show table 300
docker exec wg-relay nft -s list table inet ru_bth
nft -s list table inet reality_fornex
```

WG nft-команда может вернуть большой RU IP-list. Не публиковать его целиком без необходимости. `wg show` безопаснее `wg show all dump`, который может включать секреты. Recovery oneshot обычно inactive между запусками; важны Result, timer и свежесть state.

Серверный helper `wg-status`, `wg-status --active`, `wg-status --interface wg-clients` относится к обычному WG. Он не отображает полностью встроенные Xray WG outbound и прямой AWG31.

## Fornex / Cenuta: только чтение

Fornex:

```sh
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker exec wg-exit wg show
docker exec fornex-awg31 awg show awg0 latest-handshakes
docker exec fornex-awg31 awg show awg0 transfer
```

Cenuta:

```sh
sudo systemctl status wg-quick@wg-cenuta nftables --no-pager
sudo wg show
sudo ip -4 route
sudo nft -s list table inet reality_c3
```

Fornex UDP/53 относится к **amnezia-wireguard**, не открытому DNS-сервису.

## MikroTik: только чтение

В сессии правильного роутера:

```routeros
/system identity print
/system resource print
/interface wireguard print
/interface wireguard peers print
/ip firewall address-list print where list=CENUTA_Devices
/ip firewall address-list print where list=VPN_Devices
/ip firewall mangle print stats
/ip firewall filter print stats
/ip route print detail where dst-address=0.0.0.0/0
```

Последний saved export: [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>). Не импортировать полный старый export вместо диагностики.

## Если сайты недоступны

1. Уточнить устройство, выбранный файл/endpoint, время и сайт. Connected не доказывает передачу данных.
2. Проверить DNS, TCP, TLS и HTTP отдельно. HTTP 503 после TLS не равен отказу туннеля.
3. Сравнить нужный outbound с проверкой непосредственно на exit-хосте. Обычный curl с TimeWeb без привязки не проверяет выход клиента через Fornex/Cenuta.
4. При capture явно попросить пользователя включить точный профиль и создать трафик; ограничить capture временем/фильтром.
5. При регрессии после изменения сначала проверить собственный diff, не приписывать отказ оператору/блокировке без доказательств.

## Изменения

Переключение всех LAN-хостов, очистка conntrack, recreate wg-relay, изменение keys и удаление профиля не являются read-only диагностикой.

Перед сменой одного устройства: свежий backup, точный адрес/список/исходное состояние, согласованный выход, адресный diff, проверка нового сеанса и обратный diff. Не менять динамические address-list записи общим циклом и не очищать все соединения.

WG: [TimeWeb_Client_Creation](<../operations/TimeWeb_Client_Creation.md>). AWG31: [Fornex_AWG31_Operations](<../operations/Fornex_AWG31_Operations.md>). REALITY/откат: [TimeWeb_REALITY_Backup_and_Rollback](<../operations/TimeWeb_REALITY_Backup_and_Rollback.md>). Мониторинг: [TimeWeb_Uplink_Pilot_Quick_Guide](<../operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>), отдельно от BTH recovery.
