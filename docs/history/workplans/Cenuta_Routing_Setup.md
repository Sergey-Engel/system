---
type: workplan
status: draft
topic: mikrotik
updated: 2026-06-28
tags:
  - mikrotik
  - vpn
  - wireguard
  - cenuta
source:
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[TimeWeb_Parameters](<../../hosts/timeweb/TimeWeb_Parameters.md>)"
  - "[TimeWeb_Configuration](<../../hosts/timeweb/TimeWeb_Configuration.md>)"
  - "[Cenuta_Parameters](<../../hosts/cenuta/Cenuta_Parameters.md>)"
  - "[Cenuta_Configuration](<../../hosts/cenuta/Cenuta_Configuration.md>)"
  - "[Cenuta_hosts_2026-06-22](<../../reference/Cenuta_hosts_2026-06-22.md>)"
  - "[Current_Mikrotik_hAP_ax3_Config](<../../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>)"
---

## Назначение

Рабочий документ для настройки маршрутизации через **TimeWeb** как центральный WireGuard-router, который принимает клиентские профили, выбирает маршрут по экземпляру клиента и выводит трафик через один из upstream-серверов:

- `client-1` -> TimeWeb -> Fornex -> Internet.
- `client-2` -> TimeWeb -> Cenuta -> Internet.

Cenuta Cloud II на этом этапе остается только upstream outbound egress. Она не является BTH/relay hub и не хранит клиентские конфиги конечных пользователей. Клиентские конфиги, ключи клиентов и command file создаются на TimeWeb.

Live inventory 2026-06-28 показал, что TimeWeb уже является действующим production `wg-relay`, а не пустым сервером:

- Public IPv4: `94.241.171.65`.
- Current regular clients: `wg0`, `94.241.171.65:51820/udp`, `10.10.10.0/24`.
- Current Fornex uplink: `wg1`, `10.20.0.1/24` -> Fornex `103.75.126.143:51821`, route table `100`.
- Current BTH: `wg-home`, `94.241.171.65:51830/udp`, `10.30.30.0/24`, route table `300`.

Selector `client-1`/`client-2` реализован как отдельный контур `wg-clients` под управлением `/opt/wg-router/`, без добавления Cenuta rules в текущий production `wg0`.

Cenuta live audit 2026-06-28 показал, что Cenuta пока является чистым VPS, а не готовым WireGuard egress. Maintenance update/reboot и установка `wireguard-tools` выполнены позднее 2026-06-28:

- OS/kernel after update: `Ubuntu 24.04.4 LTS`, `6.8.0-124-generic`.
- Public IPv4: `89.252.153.129`.
- Public IPv6 не зафиксирован; external IPv6 check не проходит.
- WireGuard kernel module загружен, `wireguard-tools` установлен.
- `wg-cenuta` настроен и активен.
- Docker не установлен.
- IPv4 forwarding включен; IPv6 forwarding выключен.
- nftables firewall/NAT включен и активен; SSH `22/tcp` и WireGuard `51840/udp` разрешены.
- Reboot required: no after update/reboot.
- Pending updates: `0`.

Следствие: Cenuta-side подготовка завершена 2026-06-28. TimeWeb-side `wg-up-cenuta`, `wg-clients`, routing selector и e2e tests завершены 2026-06-29.

## Перенесенные вопросы и решения

| Вопрос                 | Решение                                                                 |
| ---------------------- | ----------------------------------------------------------------------- |
| Центральный router     | `TimeWeb` `94.241.171.65`; live inventory снят 2026-06-28.              |
| Где создавать clients  | На TimeWeb; предпочтительно в отдельном `/opt/wg-router/client-configs/`, чтобы не смешивать с текущим `/opt/wg/clients/`. |
| Командный файл         | `/opt/wg-router/commands.sh`.                                           |
| Downstream client net  | `10.50.50.0/24` на TimeWeb interface `wg-clients`.                      |
| `client-1`             | `10.50.50.11/32`, маршрутизируется в Fornex.                            |
| `client-2`             | `10.50.50.12/32`, маршрутизируется в Cenuta.                            |
| Fornex upstream        | Initial preference: reuse current TimeWeb `wg1` / table `100` with NAT for `client-1`, if selector runs in the same network namespace. |
| Cenuta upstream        | TimeWeb interface `wg-up-cenuta`, route table `TW-Cenuta-Route`.        |
| Cenuta UDP port        | `51840/udp` для WireGuard на Cenuta.                                    |
| Cenuta tunnel subnet   | `10.40.40.0/24`, отдельно от `10.10.10.0/24` и `10.30.30.0/24`.         |
| Cenuta server WG IP    | `10.40.40.1/24` на Cenuta `wg-cenuta`.                                  |
| TimeWeb-Cenuta WG IP   | `10.40.40.2/32` на TimeWeb `wg-up-cenuta`.                              |
| Cenuta public key      | `3fg6rK3jeTdtGxtr0yX896BhEtH33OvWyx3ncTm6uR0=`.                         |
| TimeWeb peer public key | `OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=`; private handoff config is root-only on Cenuta. |
| Cenuta role            | Только outbound egress; второй BTH/relay hub на Cenuta не делаем.       |
| Cenuta hostname        | `wg-tr-01`.                                                             |
| DNS name               | Не создаем; endpoint задается прямым IPv4 `89.252.153.129`.             |
| IPv6                   | Наружу не маршрутизируем; selector client profiles могут содержать `::/0` только для предотвращения direct IPv6 leaks. На Cenuta IPv6 forwarding не включать. |
| Cenuta implementation  | Host-level WireGuard через `wireguard-tools`; Docker не нужен, если не появится отдельное требование. |

## IP-план

| Контур                   | Узел                  | Адрес             | Интерфейс        | Назначение                                  |
| ------------------------ | --------------------- | ----------------- | ---------------- | ------------------------------------------- |
| TimeWeb public            | TimeWeb               | `94.241.171.65`   | `eth0`           | Публичный endpoint; WG ports `51820/udp`, `51830/udp`, selector `51850/udp`. |
| TimeWeb current clients   | TimeWeb               | `10.10.10.1/24`   | `wg0`            | Действующие клиенты `/opt/wg/clients/`; не менять без отдельного плана. |
| TimeWeb current Fornex    | TimeWeb               | `10.20.0.1/24`    | `wg1`            | Действующий uplink на Fornex через table `100`. |
| TimeWeb current BTH       | TimeWeb               | `10.30.30.1/24`   | `wg-home`        | Действующий Back-to-Home на `94.241.171.65:51830`. |
| Selector downstream clients | TimeWeb             | `10.50.50.1/24`   | `wg-clients`     | Активная серверная сторона client selector. |
| Downstream client-1       | client-1              | `10.50.50.11/32`  | client profile   | Клиент, жестко направляемый в Fornex.       |
| Downstream client-2       | client-2              | `10.50.50.12/32`  | client profile   | Клиент, жестко направляемый в Cenuta.       |
| Fornex SSH management     | Fornex                | `103.75.126.143`  | public NIC       | Корректный SSH-доступ: `ssh root@103.75.126.143`. |
| Fornex exit current       | Fornex                | `103.75.126.143:51821` | `wg0` in `wg-exit` | Текущий внешний egress; `94.241.171.65` является TimeWeb relay endpoint. |
| TimeWeb -> Fornex current/reused | TimeWeb       | `10.20.0.1/24`    | current `wg1`    | `client-1` uses current Fornex uplink with NAT inside existing `wg-relay` namespace. |
| Cenuta public             | Cenuta                | `89.252.153.129`  | `ens3`           | Публичный IPv4 endpoint.                    |
| Cenuta WireGuard          | Cenuta                | `10.40.40.1/24`   | `wg-cenuta`      | Серверная сторона Cenuta upstream.          |
| TimeWeb -> Cenuta         | TimeWeb               | `10.40.40.2/32`   | `wg-up-cenuta`   | Upstream peer TimeWeb в Cenuta.             |
| MikroTik existing Fornex  | MikroTik hAP ax3      | `10.10.10.24/24`  | `wg1`            | Существующий домашний Fornex-туннель.       |
| BTH current               | TimeWeb / MikroTik / remote BTH | `10.30.30.0/24` | TimeWeb `wg-home` | Отдельный Back-to-Home контур; активен на TimeWeb, не часть Cenuta selector. |

Private keys, preshared keys, QR-коды и полные клиентские конфиги в Obsidian не сохранять.

## Фактический результат внедрения 2026-06-29

- TimeWeb management tree: `/opt/wg-router/`.
- Command procedure: `/opt/wg-router/commands.sh`.
- Active Docker published ports: `51820/udp`, `51830/udp`, `51850/udp`.
- Active interfaces in `wg-relay`: `wg0`, `wg1`, `wg-home`, `wg-up-cenuta`, `wg-clients`.
- `wg-up-cenuta`: `10.40.40.2/32`, peer Cenuta `89.252.153.129:51840`, table `200`.
- `wg-clients`: `10.50.50.1/24`, public endpoint `94.241.171.65:51850`.
- `client-1`: `10.50.50.11/32`, route `fornex`, e2e IPv4 `103.75.126.143`, ping 5/5, IPv6 no connect.
- `client-2`: `10.50.50.12/32`, route `cenuta`, e2e IPv4 `89.252.153.129`, ping 5/5, IPv6 no connect.
- `sergey-iphone-12`: `10.50.50.20/32`, `fd00:50:50::20/128`, route `cenuta`; key rotated after chat exposure; server-side route check passed: table `200` -> `wg-up-cenuta`; client-side e2e pending after device import.
- `sveta-iphone`: `10.50.50.21/32`, `fd00:50:50::21/128`, route `cenuta`; server-side route check passed: table `200` -> `wg-up-cenuta`; client-side e2e pending after device import.
- Root-only client exports: `/root/wg-client-exports/client-1-fornex.conf`, `/root/wg-client-exports/client-2-cenuta.conf`.
- Root-only real client exports: `/root/wg-client-exports/sergey-iphone-12-cenuta.conf`, `/root/wg-client-exports/sveta-iphone-cenuta.conf`.
- Config/QR viewer command: `sudo wg-client-config`; list includes `selector`, `legacy`, `bth`.
- Selector client configs use public-IPv4 split `AllowedIPs` with local/private IPv4 exclusions, ULA IPv6 `fd00:50:50::/64`, and `::/0` to prevent direct IPv6 leaks. IPv6 is not routed to the Internet by the selector.
- Root-only rollback backup: `/root/timeweb-pre-selector-backup-20260629T0649Z`.
- Root-only post-change backup: `/opt/wg-router/backups/20260629T070316Z`.
- Root-only backup after first real Cenuta client and wrapper fix: `/opt/wg-router/backups/20260629T145317Z`.
- Root-only backup after config/QR viewer command: `/opt/wg-router/backups/20260629T150512Z`.
- Root-only backup after selector AllowedIPs/viewer fix and `sergey-iphone-12` key rotation: `/opt/wg-router/backups/20260629T152006Z`.
- Sanitized Obsidian checkpoint: [2026-06-29T0701Z TimeWeb selector implementation](<../timeweb/2026-06-29T0701Z-timeweb-selector-implementation/README.md>).

## Целевая структура на TimeWeb

```text
/opt/wg-router/
├── commands.sh
├── env/
│   └── routes.env
├── keys/
│   ├── server/
│   ├── upstream/
│   └── clients/
├── configs/
│   ├── server/
│   │   ├── wg-clients.conf
│   │   └── wg-up-cenuta.conf
│   └── snippets/
├── client-configs/
│   ├── client-1-fornex.conf
│   └── client-2-cenuta.conf
├── logs/
├── state/
├── backups/
└── docs/
    ├── CLIENT_CREATION.md
    ├── IMPLEMENTATION_LOG.md
    └── RUNBOOK.md
```

Права:

- `/opt/wg-router/keys/`: `0700`, owner `root`.
- `/opt/wg-router/client-configs/`: `0750`, owner `root`.
- `commands.sh`: `0750`, owner `root`.

## Командный файл TimeWeb

Файл: `/opt/wg-router/commands.sh`.

Минимальные subcommands:

```bash
# normal client creation
sudo /opt/wg-router/commands.sh add-client <client-name> fornex
sudo /opt/wg-router/commands.sh add-client <client-name> cenuta
sudo /opt/wg-router/commands.sh add-client <client-name> bth

# inventory and base operations
sudo /opt/wg-router/commands.sh inventory
sudo /opt/wg-router/commands.sh init-dirs
sudo /opt/wg-router/commands.sh check-upstream fornex
sudo /opt/wg-router/commands.sh gen-upstream cenuta

# low-level selector operations
sudo /opt/wg-router/commands.sh gen-client client-1 fornex
sudo /opt/wg-router/commands.sh gen-client client-2 cenuta
sudo /opt/wg-router/commands.sh gen-client <client-name> cenuta
sudo /opt/wg-router/commands.sh render
sudo /opt/wg-router/commands.sh apply-sysctl
sudo /opt/wg-router/commands.sh apply-firewall
sudo /opt/wg-router/commands.sh up
sudo /opt/wg-router/commands.sh status
sudo /opt/wg-router/commands.sh test fornex
sudo /opt/wg-router/commands.sh test cenuta
sudo /opt/wg-router/commands.sh test-client <client-name>
sudo /opt/wg-router/commands.sh export-client client-1
sudo /opt/wg-router/commands.sh export-client client-2
sudo /opt/wg-router/commands.sh export-client <client-name>
sudo /opt/wg-router/commands.sh backup
```

Командный файл должен быть idempotent: повторный запуск `init-dirs`, `render`, `status` и `test` не должен ломать уже созданную конфигурацию.

### Процедура создания новых client configs

Цель: после первичного внедрения иметь повторяемую командную процедуру для добавления новых WireGuard client configs одной командой, без ручного редактирования runtime-конфигов.

Основная команда:

```bash
sudo /opt/wg-router/commands.sh add-client <client-name> cenuta
sudo /opt/wg-router/commands.sh add-client <client-name> fornex
sudo /opt/wg-router/commands.sh add-client <client-name> bth
```

Результат сохраняется в root-only export directory:

```text
/root/wg-client-exports/<client-name>-cenuta.conf
/root/wg-client-exports/<client-name>-fornex.conf
/root/wg-client-exports/<client-name>-bth.conf
```

Отдельная короткая инструкция для операционного использования:

- TimeWeb: `/opt/wg-router/docs/CLIENT_CREATION.md`.
- Obsidian: [TimeWeb Client Creation](<../../operations/TimeWeb_Client_Creation.md>).

Что делает `add-client`:

- для `cenuta` и `fornex`: выполняет `gen-client`, `render`, `up`, `test-client`, `export-client`, `backup`;
- для `bth`: вызывает существующий BTH generator `/opt/wg/add-bth.sh`, синхронизирует `wg-home`, экспортирует конфиг в `/root/wg-client-exports/<client-name>-bth.conf`, затем делает backup.

Низкоуровневые команды `gen-client`, `render`, `up`, `test-client`, `export-client`, `backup` остаются для диагностики и восстановления.

Требования к `add-client <client-name> cenuta`:

- проверить, что `<client-name>` уникален;
- выделить следующий свободный IPv4 из Cenuta-routed pool внутри `10.50.50.0/24`;
- создать client private/public key на TimeWeb root-only;
- добавить peer в render-state для `wg-clients`;
- назначить route profile `cenuta`;
- сгенерировать client config в `/opt/wg-router/client-configs/<client-name>-cenuta.conf`;
- генерировать ULA IPv6-адрес клиента из `fd00:50:50::/64` и добавлять `::/0` в client config только для предотвращения direct IPv6 leaks;
- не сохранять private keys, preshared keys, QR-коды и полные client configs в Obsidian.

Требования к routing/NAT для новых Cenuta-routed clients:

- source IP каждого Cenuta-routed client должен попадать в `TW-Cenuta-Route` / table `200`;
- NAT только out `wg-up-cenuta`;
- forwarding только `wg-clients -> wg-up-cenuta`;
- новые Cenuta clients не должны матчиться на Fornex table `100`;
- существующие `10.10.10.0/24`, `10.20.0.0/24`, `10.30.30.0/24`, `10.40.40.0/24` не должны затрагиваться.

Проверки после создания каждого нового Cenuta-routed client:

- `commands.sh status` показывает peer в `wg-clients`;
- `commands.sh test-client <client-name>` проверяет route decision, NAT counters и отсутствие IPv6 route;
- при подключении клиента external IPv4 соответствует Cenuta `89.252.153.129` или документированному Cenuta egress IP;
- `curl -6` с клиента не возвращает внешний IPv6;
- результат добавлен в `IMPLEMENTATION_LOG.md` без секретов.

Документация после каждого нового Cenuta-routed client:

- обновить client inventory: profile name, assigned IPv4, route profile `cenuta`, дата создания;
- обновить `/opt/wg-router/docs/CLIENT_CREATION.md` и `RUNBOOK.md`, если процедура изменилась;
- создать sanitized backup/checkpoint после применения.

## План настройки и тестирования TimeWeb

Target outcome: TimeWeb принимает отдельные client profiles и жестко маршрутизирует `client-1` через Fornex, а `client-2` через Cenuta, не ломая текущие production-контуры `wg0`, `wg1` и `wg-home`.

Режим выполнения: при фактической настройке идти по одному действию или одной команде за раз, с проверкой результата перед следующим шагом.

### Исходные решения для плана

- Активная WireGuard-среда TimeWeb сейчас находится внутри Docker container `wg-relay`, а не на host-level `wg-quick`.
- Для первого внедрения selector лучше использовать существующий network namespace `wg-relay`, потому что только там уже есть рабочий Fornex uplink `wg1` и route table `100`.
- `/opt/wg-router/` используется как управляемое дерево для command file, generated client configs, backups, logs и render-state.
- Активные WireGuard configs для container runtime должны рендериться в `/opt/wg/config/wg_confs/`, потому что именно этот каталог смонтирован в `wg-relay` как `/config`.
- Cenuta не меняется при настройке TimeWeb. Нужен только уже подготовленный root-only handoff config с Cenuta или ручная безопасная передача private key для TimeWeb peer.
- IPv6 через новый selector наружу не маршрутизируем: client config содержит `::/0` только для предотвращения direct IPv6 leaks; успешный сценарий - `curl -6` с client profile не уходит наружу.
- Кратковременные перерывы текущего VPN/BTH допустимы. Restart/recreation `wg-relay` можно планировать спокойно, если до него создан backup и понятен rollback.

### 0. Gate: плановое окно изменений

Цель: зафиксировать, что кратковременный restart/recreation `wg-relay` допустим и может быть использован для применения Docker Compose changes, включая публикацию public UDP port `51850`.

Проверки до допуска:

- есть доступ по SSH key к TimeWeb;
- текущие `51820/udp` и `51830/udp` могут прерваться на время container restart, и это не блокирует работы;
- выбран момент выполнения и понятно, что активные VPN/BTH sessions могут переподключиться;
- Cenuta уже готова и слушает `89.252.153.129:51840/udp`;
- Fornex и MikroTik не меняются.

Acceptance: краткое прерывание принято как штатный риск изменения, поэтому Docker Compose recreation можно выполнять после backup и baseline checks.

Stop-line: не переходить к live-изменениям, если нет SSH-доступа, свежего backup, rollback path или baseline показывает деградацию текущих `wg0`/`wg1`/`wg-home`.

Документация после шага: записать в `IMPLEMENTATION_LOG.md`, что кратковременный restart `wg-relay` разрешен планом, и указать фактическое время окна.

### 1. Fresh read-only baseline TimeWeb

Цель: перед изменениями убедиться, что TimeWeb находится в ожидаемом состоянии.

Проверки:

- host OS/kernel, `reboot-required`, pending updates;
- `docker ps`, `docker compose -f /opt/wg/docker-compose.yml ps`;
- published ports `51820/udp`, `51830/udp`;
- inside `wg-relay`: `wg show`, `ip addr`, `ip rule`, `ip route`, `ip route show table 100`, `ip route show table 300`;
- свежий handshake `wg1` -> Fornex;
- свежий handshake `wg-home` -> MikroTik, если BTH должен остаться активным;
- отсутствие host-level активного `wg-quick` контура, который может конфликтовать.

Acceptance:

- `wg-relay` running;
- `wg0`, `wg1`, `wg-home` active;
- table `100` указывает Fornex path;
- table `300` обслуживает BTH;
- main default route host не направлен в WireGuard.

Stop-line: любое расхождение с [TimeWeb_Configuration](<../../hosts/timeweb/TimeWeb_Configuration.md>) сначала расследовать как отдельную задачу.

Документация после шага: добавить fresh baseline snapshot в `docs/agents/host-state/TimeWeb/archive/`.

### 2. Backup and rollback point

Цель: иметь точку восстановления до любых изменений Docker/WireGuard/routing.

Что сохранить:

- root-only backup на TimeWeb: `/opt/wg/`, `/etc/wireguard/`, `/etc/sysctl.d/`, Docker Compose, текущие firewall/routing dumps;
- sanitized backup в Obsidian без private keys, preshared keys, QR и полных secret client configs;
- checksum manifest;
- короткий rollback file с конкретным restore order.

Acceptance:

- root-only backup создан на TimeWeb и доступен только root;
- sanitized backup создан в `docs/agents/host-state/TimeWeb/archive/`;
- checksum verification проходит;
- есть явный rollback path: restore compose/configs -> restart `wg-relay` -> verify `51820`, `51830`, `wg0`, `wg1`, `wg-home`.

Stop-line: без backup не менять `/opt/wg/docker-compose.yml` и `/opt/wg/config/wg_confs/`.

Документация после шага: ссылка на backup README и SHA256SUMS.

### 3. Подготовка `/opt/wg-router/`

Цель: создать management tree без включения новых interfaces.

Ожидаемая структура:

```text
/opt/wg-router/
├── commands.sh
├── env/routes.env
├── keys/
├── configs/
├── client-configs/
├── logs/
├── state/
├── backups/
└── docs/IMPLEMENTATION_LOG.md
```

Проверки:

- директории существуют;
- `keys/` имеет `0700`;
- `client-configs/` имеет `0750`;
- `commands.sh` имеет `0750`;
- `commands.sh inventory/status` работает read-only и не меняет runtime.

Acceptance: management tree готов, активные `/opt/wg/config/wg_confs/*` еще не изменены.

Stop-line: если command file не получается сделать idempotent, продолжать ручной настройкой нельзя.

Документация после шага: зафиксировать дерево, права, owner.

### 4. Подготовка TimeWeb -> Cenuta upstream config

Цель: подготовить `wg-up-cenuta` внутри `wg-relay`, но включить его только после проверки ключей.

Входные параметры:

- Cenuta endpoint: `89.252.153.129:51840`.
- Cenuta public key: `3fg6rK3jeTdtGxtr0yX896BhEtH33OvWyx3ncTm6uR0=`.
- TimeWeb tunnel IP: `10.40.40.2/32`.
- Cenuta tunnel IP: `10.40.40.1/24`.
- TimeWeb peer public key, уже разрешенный на Cenuta: `OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=`.
- Route table: `200`, logical name `TW-Cenuta-Route`.

Проверки до включения:

- private key, который попадет на TimeWeb, дает public key `OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=`;
- TimeWeb-Cenuta upstream config не содержит `::/0`;
- config не меняет main default route;
- `PersistentKeepalive = 25`;
- `Table = off` или эквивалентная явная route setup, чтобы default route не попал в main table.

Acceptance: `wg-up-cenuta.conf` подготовлен и проходит syntax/key sanity checks, но production routing еще не изменен.

Stop-line: если public key не совпал с Cenuta peer, не стартовать interface и не менять Cenuta автоматически.

Документация после шага: записать только public key, endpoint, table ID; private key не переносить в Obsidian.

### 5. Включение и проверка `wg-up-cenuta`

Цель: поднять upstream TimeWeb -> Cenuta и доказать handshake без подключения downstream clients.

Проверки:

- `wg-up-cenuta` появился в `wg show`;
- latest handshake с Cenuta свежий;
- route table `200` содержит default via/dev `wg-up-cenuta`;
- `ip rule` еще не отправляет существующих клиентов в table `200`;
- `curl -4`/route test из container namespace через Cenuta показывает egress `89.252.153.129` или ожидаемый Cenuta egress;
- `curl -6` через этот path не проходит.

Acceptance:

- Cenuta handshake есть;
- существующий Fornex `wg1` не изменился;
- `wg0` regular clients продолжают использовать table `100`;
- `wg-home` BTH продолжает использовать table `300`.

Stop-line: если `wg-up-cenuta` поднялся, но egress не Cenuta, не переходить к clients/routing.

Документация после шага: зафиксировать handshake time, transfer counters, route table `200`, IPv6 result.

### 6. Подготовка downstream `wg-clients`

Цель: создать отдельный client selector, не расширяя текущий production `wg0`.

Параметры:

- interface: `wg-clients`;
- public endpoint: `94.241.171.65:51850/udp`;
- TimeWeb IP: `10.50.50.1/24`;
- `client-1-fornex`: `10.50.50.11/32`;
- `client-2-cenuta`: `10.50.50.12/32`;
- client `AllowedIPs`: public-IPv4 split list with local/private IPv4 exclusions, plus `::/0` to prevent direct IPv6 leaks;
- client IPv6 ULA: `fd00:50:50::x/128`; IPv6 is not routed to the Internet by selector;
- DNS in client profiles: зафиксировать явно, например `1.1.1.1, 8.8.8.8`, если не будет отдельного DNS-плана.

Проверки до включения:

- generated client configs лежат в `/opt/wg-router/client-configs/`;
- private keys/QR не попали в Obsidian;
- `/opt/wg/docker-compose.yml` подготовлен к публикации `51850:51850/udp`; применение выполняется на этапе 8 после backup/baseline, отдельный блокер из-за краткого downtime отсутствует;
- `wg-clients.conf` не содержит route/NAT, который может перехватить `10.10.10.0/24` или `10.30.30.0/24`.

Acceptance: configs готовы, но external clients еще не подключаются.

Stop-line: если новый port пересекается с существующим listener/firewall rule, остановиться.

Документация после шага: зафиксировать profile names и IP-план без секретов.

### 7. Policy routing and NAT selector

Цель: привязать каждый client source IP к своему upstream.

Правила:

- `10.50.50.11/32` -> table `100` -> existing Fornex `wg1`;
- `10.50.50.12/32` -> table `200` -> `wg-up-cenuta`;
- NAT `10.50.50.11/32` только out `wg1`;
- NAT `10.50.50.12/32` только out `wg-up-cenuta`;
- forwarding разрешить только `wg-clients -> wg1` для `client-1` и `wg-clients -> wg-up-cenuta` для `client-2`;
- не добавлять default route в main table.

Проверки:

- `ip rule show` содержит правила selector с понятными priorities;
- `ip route show table 100` не сломан;
- `ip route show table 200` ведет в `wg-up-cenuta`;
- `iptables`/`nft` counters растут только на ожидаемых правилах;
- `ip route get 1.1.1.1 from 10.50.50.11` выбирает Fornex path;
- `ip route get 1.1.1.1 from 10.50.50.12` выбирает Cenuta path.

Acceptance: static routing proof проходит до подключения реальных клиентов.

Stop-line: если `10.10.10.0/24` или `10.30.30.0/24` начали матчиться новыми правилами, немедленно rollback selector rules.

Документация после шага: зафиксировать priorities, tables, NAT mapping.

### 8. Применение Docker port `51850` и restart check

Цель: открыть внешний UDP port для `wg-clients` и убедиться, что старые контуры восстановились после container recreation.

Проверки сразу после restart:

- `docker ps`: `wg-relay` running;
- `ss -u -l -n -p`: `51820`, `51830`, `51850` слушают;
- inside container: `wg0`, `wg1`, `wg-home`, `wg-up-cenuta`, `wg-clients` active;
- `wg1` latest handshake с Fornex свежий;
- `wg-up-cenuta` latest handshake с Cenuta свежий;
- `wg-home` handshake с MikroTik свежий или объяснимо stale, если peer offline;
- route tables `100`, `200`, `300` на месте.

Acceptance: новые и старые WireGuard interfaces активны после restart.

Stop-line: если после restart не поднялись `wg0`, `wg1` или `wg-home`, сначала восстановить старый production path, не продолжать selector tests.

Документация после шага: обновить TimeWeb configuration и backup checkpoint.

### 9. End-to-end тест `client-1 -> Fornex`

Цель: доказать, что отдельный profile `client-1-fornex` идет только через Fornex.

Проверки с тестового клиента:

- WireGuard handshake на `wg-clients`;
- `curl -4 https://api.ipify.org` возвращает `103.75.126.143`;
- `ping -c 20 1.1.1.1` без заметных потерь;
- latency зафиксирована;
- `curl -6 https://api64.ipify.org` не должен возвращать внешний IPv6. Если возвращает IPv6 через локальную сеть клиента, это IPv6 leak и тест не пройден;
- DNS leak check: резолверы соответствуют ожидаемой политике profile.

Проверки на TimeWeb:

- `wg show wg-clients` показывает свежий handshake peer `client-1`;
- counters NAT/forward растут на path `wg-clients -> wg1`;
- counters path `wg-clients -> wg-up-cenuta` не растут от `client-1`.

Acceptance: `client-1` стабильно выходит через Fornex и не использует Cenuta.

Stop-line: если egress не `103.75.126.143`, не тестировать `client-2` до исправления routing/NAT.

Документация после шага: таблица test result: profile, public IPv4, IPv6 result, latency, packet loss.

### 10. End-to-end тест `client-2 -> Cenuta`

Цель: доказать, что отдельный profile `client-2-cenuta` идет только через Cenuta.

Проверки с тестового клиента:

- WireGuard handshake на `wg-clients`;
- `curl -4 https://api.ipify.org` возвращает `89.252.153.129` или документированный Cenuta egress IP;
- `ping -c 20 1.1.1.1` без заметных потерь;
- latency зафиксирована;
- `curl -6 https://api64.ipify.org` не должен возвращать внешний IPv6. Если возвращает IPv6 через локальную сеть клиента, это IPv6 leak и тест не пройден;
- DNS leak check: резолверы соответствуют ожидаемой политике profile.

Проверки на TimeWeb и Cenuta path:

- `wg show wg-clients` показывает свежий handshake peer `client-2`;
- `wg show wg-up-cenuta` transfer counters растут;
- counters NAT/forward растут на path `wg-clients -> wg-up-cenuta`;
- counters path `wg-clients -> wg1` не растут от `client-2`.

Acceptance: `client-2` стабильно выходит через Cenuta и не использует Fornex.

Stop-line: если egress не Cenuta, остановиться и проверить table `200`, NAT и peer AllowedIPs.

Документация после шага: таблица test result: profile, public IPv4, IPv6 result, latency, packet loss.

### 11. Regression tests existing production paths

Цель: доказать, что новая схема не сломала существующую.

Проверки:

- existing TimeWeb `wg0` clients still handshake;
- current MikroTik Smart VPN path still exits through Fornex;
- `wg1` Fornex handshake fresh;
- `wg-home` BTH still works for home access/egress if peer online;
- published ports `51820`, `51830`, `51850` persist after `docker compose` restart;
- host main route still goes via `94.241.171.1`, not WireGuard;
- IPv6 forwarding remains disabled.

Acceptance: old paths and new selector work simultaneously.

Stop-line: если existing production path degraded, rollback selector before further tuning.

Документация после шага: update [VPN_HLD](<../../architecture/overview.md>), [TimeWeb_Configuration](<../../hosts/timeweb/TimeWeb_Configuration.md>), test table, rollback status.

### 12. Final hardening and documentation

Цель: закрыть работу как воспроизводимую операционную схему.

Что зафиксировать:

- final configs sanitized;
- active interfaces and ports;
- route table IDs and priorities;
- exact profile names and assigned IPs;
- final egress IPs;
- IPv6 leak test result;
- rollback instructions;
- remaining risks: TimeWeb SSH/password policy, key file permissions, Ubuntu Pro/ESM, `qemu-guest-agent` held back.

Обновить Obsidian-документацию после завершения всех работ:

- [VPN_HLD](<../../architecture/overview.md>) - финальная схема, route matrix, IP-план, статус selector.
- [TimeWeb Parameters](<../../hosts/timeweb/TimeWeb_Parameters.md>) - endpoints, ports, route tables, command procedure.
- [TimeWeb Configuration](<../../hosts/timeweb/TimeWeb_Configuration.md>) - фактический runtime после внедрения.
- Этот документ - статусы этапов, результаты тестов и final checklist.
- `docs/agents/host-state/TimeWeb/archive/` - sanitized post-implementation checkpoint.
- `/opt/wg-router/docs/CLIENT_CREATION.md` на TimeWeb - короткая инструкция добавления новых `cenuta`, `fornex` и `bth` clients через `commands.sh add-client <client-name> <route>`.
- `/opt/wg-router/docs/RUNBOOK.md` на TimeWeb - расширенная процедура и low-level команды.
- `/opt/wg-router/docs/IMPLEMENTATION_LOG.md` на TimeWeb - пошаговый журнал выполнения без секретов.

Acceptance:

- `commands.sh status` показывает зеленый статус всех контуров;
- backup после внедрения создан;
- secrets остаются только на серверах/root-only;
- Obsidian содержит только sanitized operational docs.

Stop-line: не делать SSH hardening или key permission cleanup в этом же изменении без отдельного плана и secret backup.

## Этапы настройки и проверки

### -1. Inventory Cenuta

Статус: complete на 2026-06-28.

Источник: [Cenuta_Configuration](<../../hosts/cenuta/Cenuta_Configuration.md>) и [Cenuta live audit 2026-06-28T1958Z](<../cenuta/2026-06-28T1958Z-live-audit/README.md>).

Выводы initial audit до maintenance:

- SSH key access работает для `ubuntu@89.252.153.129`.
- `sudo_nopasswd=yes`.
- Initial reboot state: required.
- Initial pending updates: `48`.
- Initial `wireguard-tools` state: absent.
- Docker: absent.
- Forwarding: IPv4 off, IPv6 off.
- Firewall: UFW inactive, default iptables policies open.

Документация после шага: создана папка `docs/agents/host-state/Cenuta`, параметры и конфигурация зафиксированы. Maintenance step `-0` ниже обновил текущее состояние до `Ubuntu 24.04.4`, kernel `6.8.0-124`, pending updates `0`, `wireguard-tools` installed.

### -0. Maintenance Cenuta

Статус: complete на 2026-06-28.

Цель: привести Cenuta в актуальное состояние до production-настройки WireGuard.

Ожидаемые действия:

```bash
sudo apt upgrade
sudo reboot
```

После reboot:

```bash
if [ -f /var/run/reboot-required ]; then cat /var/run/reboot-required; else echo no; fi
apt list --upgradable
uname -r
```

Затем установить WireGuard userspace:

```bash
sudo apt install wireguard-tools
```

Тест прохождения:

```bash
command -v wg
command -v wg-quick
sudo modprobe wireguard
lsmod | grep wireguard
```

Фактический результат:

- OS: `Ubuntu 24.04.4 LTS`.
- Kernel: `6.8.0-124-generic`.
- Reboot required: no.
- Pending updates: `0`.
- `wireguard-tools`: installed.
- `wg`: `/usr/bin/wg`.
- `wg-quick`: `/usr/bin/wg-quick`.
- Active WireGuard interfaces after Cenuta-side setup: `wg-cenuta`.

Документация после шага: обновлены [Cenuta_Parameters](<../../hosts/cenuta/Cenuta_Parameters.md>), [Cenuta_Configuration](<../../hosts/cenuta/Cenuta_Configuration.md>) и добавлен [post-update checkpoint](<../cenuta/2026-06-28T2017Z-post-update-check/README.md>).

### 0. Inventory TimeWeb

Цель: снять фактические параметры TimeWeb до изменений.

Команды:

```bash
date -u
hostnamectl
ip -br addr
ip route
resolvectl status
free -h
df -hT
sudo ss -tulpen
sudo systemctl --failed
sudo modprobe wireguard
lsmod | grep wireguard || true
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

Тест прохождения:

- понятен публичный IPv4 TimeWeb;
- WireGuard module доступен;
- известны текущие listening ports;
- понятен текущий firewall state;
- зафиксировано, включен ли reboot-required.

Документация после шага: заполнить `TimeWeb public` в [VPN HLD](<../../architecture/overview.md>) и добавить секцию inventory в этот документ или в `docs/IMPLEMENTATION_LOG.md` на TimeWeb.

### 1. Создание каталогов и command file

Цель: подготовить рабочее дерево `/opt/wg-router`.

Команды-каркас:

```bash
sudo mkdir -p /opt/wg-router/{env,keys/{server,upstream,clients},configs/{server,snippets},client-configs,logs,state,backups,docs}
sudo install -m 0750 -o root -g root /dev/null /opt/wg-router/commands.sh
sudo chmod 0700 /opt/wg-router/keys
```

Тест прохождения:

```bash
sudo test -d /opt/wg-router/client-configs
sudo test -x /opt/wg-router/commands.sh
sudo find /opt/wg-router -maxdepth 2 -type d | sort
```

Документация после шага: в `IMPLEMENTATION_LOG.md` зафиксировать дату, структуру каталогов и владельца/права.

### 2. Базовая настройка TimeWeb как router

Цель: включить только IPv4 forwarding и подготовить firewall без потери SSH.

Требования:

- `net.ipv4.ip_forward=1`.
- `net.ipv6.conf.all.forwarding=0`.
- SSH не закрывать.
- Открыть downstream WireGuard port TimeWeb для клиентов: `51850/udp`.
- Открыть только нужные outbound/upstream flows.

Тест прохождения:

```bash
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
sudo ss -tulpen
```

Документация после шага: зафиксировать выбранный downstream port `51850/udp` и firewall state.

### 3. Fornex path for `client-1`

Цель: обеспечить вывод `client-1` через Fornex без нарушения текущего MikroTik/TimeWeb/Fornex трафика.

Базовое решение после HLD review:

- Fornex SSH command: `ssh root@103.75.126.143`.
- Current TimeWeb interface: `wg1`.
- Current TimeWeb tunnel IP: `10.20.0.1/24`.
- Current Fornex endpoint: `103.75.126.143:51821`.
- Current Fornex tunnel IP: `10.20.0.2/24`.
- Current TimeWeb route table: `100`.
- Initial `client-1` implementation: source `10.50.50.11/32` -> table `100`, NAT source `10.50.50.11/32` out via current `wg1`.

Ограничение: reuse current `wg1` удобно только потому, что selector runs in the same network namespace as current `wg-relay`. Если `/opt/wg-router/` будет вынесен в отдельный контейнер или host-level service, нужен отдельный Fornex uplink или явный inter-namespace routing design.

Тест прохождения:

```bash
docker exec wg-relay wg show wg1
docker exec wg-relay ip route show table 100
docker exec wg-relay ip rule show
```

Functional test с клиента выполняется после создания `client-1`.

Документация после шага: обновить IP-план, указать выбранную модель namespace/service и зафиксировать NAT/rule для `10.50.50.11/32`.

### 4. Upstream TimeWeb -> Cenuta

Цель: поднять `wg-up-cenuta`, чтобы TimeWeb мог выводить `client-2` через Cenuta.

Cenuta-side status: complete. TimeWeb-side status: complete на 2026-06-29.

Параметры Cenuta:

- Cenuta endpoint: `89.252.153.129:51840`.
- Cenuta interface: `wg-cenuta`.
- Cenuta tunnel IP: `10.40.40.1/24`.
- Cenuta public key: `3fg6rK3jeTdtGxtr0yX896BhEtH33OvWyx3ncTm6uR0=`.
- TimeWeb interface: `wg-up-cenuta`.
- TimeWeb tunnel IP: `10.40.40.2/32`.
- TimeWeb peer public key already allowed on Cenuta: `OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=`.
- TimeWeb secret handoff config on Cenuta: `/root/wireguard-handoff/timeweb-wg-up-cenuta.conf`; do not copy to Obsidian.
- TimeWeb route table: `TW-Cenuta-Route`.
- IPv6: не маршрутизировать.

Тест прохождения:

```bash
sudo wg show wg-up-cenuta
ip route show table TW-Cenuta-Route
ip rule show
```

Документация после шага: зафиксировать handshake, endpoint, route table и отсутствие IPv6 forwarding/routes.

### 5. Downstream clients на TimeWeb

Цель: создать клиентские конфиги на TimeWeb.

Параметры:

- TimeWeb downstream interface: `wg-clients`.
- TimeWeb downstream IP: `10.50.50.1/24`.
- TimeWeb downstream port: `51850/udp`.
- `client-1-fornex`: `10.50.50.11/32`.
- `client-2-cenuta`: `10.50.50.12/32`.

Генерация:

```bash
sudo /opt/wg-router/commands.sh add-client client-1 fornex
sudo /opt/wg-router/commands.sh add-client client-2 cenuta
```

Тест прохождения:

```bash
sudo test -f /opt/wg-router/client-configs/client-1-fornex.conf
sudo test -f /opt/wg-router/client-configs/client-2-cenuta.conf
sudo wg show wg-clients
```

Документация после шага: в `IMPLEMENTATION_LOG.md` зафиксировать, какие profile names созданы, без private keys и QR.

### 6. Policy routing на TimeWeb

Цель: жестко привязать client IP к upstream route table.

Правила:

- Source `10.50.50.11/32` -> current Fornex table `100` / logical `TW-Fornex-Route`.
- Source `10.50.50.12/32` -> `TW-Cenuta-Route`.
- NAT для `10.50.50.11/32` только через current `wg1` или отдельный Fornex uplink, если он будет создан.
- NAT для `10.50.50.12/32` только через `wg-up-cenuta`.

Тест прохождения:

```bash
ip rule show
ip route get 1.1.1.1 from 10.50.50.11
ip route get 1.1.1.1 from 10.50.50.12
```

Ожидание:

- `10.50.50.11` выбирает current `wg1`/table `100` или отдельный Fornex uplink, если он будет создан;
- `10.50.50.12` выбирает `wg-up-cenuta`;
- нет default-route замены в main table из-за WireGuard.

Документация после шага: зафиксировать rules, route tables и NAT mapping.

### 7. End-to-end тесты клиентов

С `client-1`:

```bash
curl -4 ifconfig.me
curl -6 ifconfig.me
ping -c 5 1.1.1.1
```

Ожидание:

- IPv4 egress соответствует Fornex `103.75.126.143` или ожидаемому адресу после финального дизайна Fornex peer;
- IPv6 не должен уходить через туннель, если IPv6 не настроен явно.

С `client-2`:

```bash
curl -4 ifconfig.me
curl -6 ifconfig.me
ping -c 5 1.1.1.1
```

Ожидание:

- IPv4 egress соответствует Cenuta `89.252.153.129` или адресу из той же Cenuta-сети, если провайдер использует иной egress;
- IPv6 не должен уходить через туннель;
- latency фиксируется для сравнения с Fornex.

Документация после шага: добавить таблицу результатов `client-1`/`client-2`, egress IP, latency, IPv6 leak status.

### 8. MikroTik integration boundary

MikroTik на этом этапе не является главным маршрутизатором выбора Fornex/Cenuta. Его текущий Fornex `wg1` не менять. BTH/`wg-home`, если он активен в live-конфигурации, не менять без отдельного плана rollback.

Если позже нужно подключить домашние устройства к TimeWeb-router, добавить отдельный этап:

- MikroTik -> TimeWeb downstream как отдельный client profile.
- Отдельная подсеть/адрес, не конфликтующая с `10.50.50.11` и `10.50.50.12`.
- Явный выбор, какие домашние устройства идут через TimeWeb, а какие остаются в текущем Smart VPN.

## Стоп-линии

- Не хранить private keys, preshared keys, QR-коды и полные клиентские конфиги в Obsidian.
- Не включать UFW/firewall без явного разрешения SSH.
- Не включать IPv6 forwarding.
- Не маршрутизировать IPv6 наружу через selector/Cenuta без отдельного IPv6-дизайна; `::/0` в selector client profiles используется только для предотвращения direct IPv6 leaks.
- Не менять текущий Fornex `wg1`. Не менять BTH/`wg-home` на MikroTik без live-проверки и отдельного rollback-плана.
- Не заменять main default route на TimeWeb через upstream WireGuard; использовать policy routing per client source IP.

## Журнал выполнения

| Этап | Статус | Дата | Что обновить в документации |
| ---- | ------ | ---- | --------------------------- |
| 0. Inventory TimeWeb | done | 2026-06-28 | Зафиксировано в [TimeWeb Parameters](<../../hosts/timeweb/TimeWeb_Parameters.md>), [TimeWeb Configuration](<../../hosts/timeweb/TimeWeb_Configuration.md>) и [backup snapshot](<../timeweb/2026-06-28T1726Z-live-audit/README.md>). |
| 1. Каталоги и command file | done | 2026-06-29 | `/opt/wg-router/`, `/opt/wg-router/commands.sh`, `/opt/wg-router/docs/RUNBOOK.md`, `/opt/wg-router/docs/IMPLEMENTATION_LOG.md`. |
| 2. Router baseline | done | 2026-06-29 | Fresh baseline and root-only rollback backup `/root/timeweb-pre-selector-backup-20260629T0649Z`; selector port `51850/udp` published. |
| 3. Upstream Fornex | done | 2026-06-29 | Reused current `wg1`/table `100`; `client-1` NAT via `wg1`; e2e IPv4 `103.75.126.143`. |
| 4a. Cenuta-side upstream | done | 2026-06-28 | `wg-cenuta`, nftables NAT/firewall, sysctl and public keys documented in [Cenuta Configuration](<../../hosts/cenuta/Cenuta_Configuration.md>). |
| 4b. TimeWeb-side upstream | done | 2026-06-29 | `wg-up-cenuta`, table `200`, fresh handshake, IPv6 forwarding off, egress `89.252.153.129`. |
| 5. Client configs | done | 2026-06-29 | `client-1-fornex` `10.50.50.11/32`, `client-2-cenuta` `10.50.50.12/32`; secrets root-only. |
| 6. Policy routing | done | 2026-06-29 | `10.50.50.11 -> table 100`, `10.50.50.12 -> table 200`, NAT mapping documented in TimeWeb config. |
| 7. E2E tests | done | 2026-06-29 | Temporary namespace tests: Fornex `103.75.126.143`, Cenuta `89.252.153.129`, ping 5/5, IPv6 no connect. |
| 8. MikroTik boundary | done | 2026-06-29 | MikroTik not changed; existing Smart VPN/BTH left separate. |
