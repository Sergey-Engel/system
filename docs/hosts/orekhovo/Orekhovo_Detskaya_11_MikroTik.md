---
type: host-state
topic: mikrotik
status: access-ready
created: 2026-08-11
updated: 2026-08-11
location: Orekhovo, Detskaya 11
tags:
  - mikrotik
  - routeros
  - orekhovo
  - site-card
---

## Назначение

Карточка второй площадки MikroTik: **Орехово, Детская 11**.

Документ фиксирует известную стартовую информацию и служит рабочей точкой для
дальнейшего подключения, сбора live-конфигурации и оформления постоянной
операционной карточки.

Текущая схема и правила: [конфигурация роутера Орехово](<Orekhovo_Detskaya_11_Router_Configuration.md>).

## Известная информация

| Параметр | Значение |
| -------- | -------- |
| Площадка | Орехово, Детская 11 |
| Устройство | MikroTik hEX, подтверждено по SSH `2026-08-11` |
| System identity | `MikroTik Root`, подтверждено по SSH `2026-08-11` |
| Модель | hEX |
| RouterBOARD model | `RB750Gr3`, revision `r3` |
| Serial number | `8AFF0A501C19` |
| RouterBOOT | factory/current `3.41`; upgrade firmware offered: `6.47` |
| RouterOS version | `6.47 stable`, build `Jun/02/2020 07:38:00` |
| Architecture | `mmips`; CPU MIPS 1004Kc V2.15, 4 cores, 880 MHz |
| Memory | 256 MiB total; 218.6 MiB free at check |
| Storage | 16.3 MiB total; 4.9 MiB free at check |
| Uptime | 1h50m31s at check; требует сопоставления с логами неожиданных перезагрузок |
| LAN IP | `192.168.88.1` |
| Username | `admin` |
| Password | Не фиксировать в Obsidian |
| SSH status | TCP/22 доступен; вход под `admin` подтвержден `2026-08-11` |
| WinBox status | TCP/8291 доступен |
| WebFig status | HTTP TCP/80 доступен; HTTPS TCP/443 отклоняет соединение |
| WAN/provider | Asarta — [asarta.ru](https://asarta.ru/) |
| DHCP/LAN subnet | Подтверждено: `192.168.88.0/24`; DHCP pool `192.168.88.10-192.168.88.254`, lease time `10m` |
| VPN/WireGuard | Отсутствуют: VPN interfaces и peers не обнаружены |
| Backup/export | Snapshot `20260811T074020Z` saved and SHA-256 verified `2026-08-11`: sanitized export and binary backup in `Dropbox/System/Mikrotik/current/orekhovo-router/`; binary backup is not stored in Obsidian |
| SSH key for `codex_audit` | Ed25519 key создан на Mac `2026-08-11`; public fingerprint: `SHA256:4/liCkUEysQa4si0gaGufh19mLnGTu60l9BIzL/aV+U` |
| SSH public key import | Ed25519 public key был uploaded для проверки, но import отклонен RouterOS 6.47: `unable to load key file (wrong format?)`; временный файл удален `2026-08-11` |
| SSH key compatibility | RouterOS 6.47 не поддерживает user Ed25519 keys. План: отдельный RSA 4096 key для этого устройства; Ed25519 key оставить локально для будущего обновления RouterOS |
| RSA fallback key | RSA 4096 создан на Mac `2026-08-11`; public fingerprint: `SHA256:JcfoqEcOcZju0oqm8gJYsBYx+8Uc5Nsg0cuMpmDzjKk`; public key imported into `codex_audit` and verified: RSA, 4096 bits; temporary upload file deleted |
| SSH server host key | RSA `SHA256:sN9lcdCa6o8b7MCx64L0YAss4/DP8k8i86W9CVSgSkk`; подтвержден при успешных SSH-входах к RB750Gr3 serial `8AFF0A501C19` |
| `codex_audit` user | Создан `2026-08-11`; group=`codex_audit`, enabled; RSA 4096 public key импортирован и проверен; изменения сохранены выходом из Safe Mode |
| Agent read-only access | Подтвержден `2026-08-11` до и после выхода из Safe Mode: команда `/system identity print` успешно выполнена из среды Codex по `codex_audit` SSH key |
| SSH alias on Mac | `mikrotik-orekhovo`; отдельный `known_hosts_orekhovo`, RSA key и scoped `ssh-rsa` compatibility для RouterOS 6.47 |
| Temporary public-key files | Ed25519 и RSA upload-файлы удалены после import; working access перепроверен после очистки |
| `codex_audit` group | Создан и проверен `2026-08-11` в Safe Mode; policy=`ssh,read` только |

## Результат проверки коннективности

Проверка выполнена `2026-08-11` с компьютера, подключенного к сети с такими
параметрами:

| Параметр | Результат |
| -------- | --------- |
| Адрес компьютера | `192.168.88.20` |
| Маска | `255.255.255.0` (`/24`) |
| Интерфейс | `en1` |
| Шлюз | `192.168.88.1` |
| ICMP ping | 4 из 4 ответов, 0% потерь, средняя задержка около 3.6 мс |
| SSH TCP/22 | Доступен |
| WebFig HTTP TCP/80 | Доступен |
| WinBox TCP/8291 | Доступен |
| HTTPS TCP/443 | Соединение отклонено |

Сетевой доступ, вход под `admin` и RouterOS identity `MikroTik Root`
подтверждены. Для неизменной идентификации устройства еще нужны serial number
и factory firmware из RouterBOARD.

## Рекомендуемая схема доступа для анализа

Для работы агента использовать отдельную учетную запись `codex_audit` с
минимальными правами. Учетную запись `admin` для регулярного анализа не
использовать.

### SSH-ключ и TLS-сертификат — разные вещи

Для SSH-доступа нужен публичный ключ, назначенный пользователю `codex_audit`.
На RouterOS 6.47 используется RSA 4096 из-за несовместимости с user Ed25519
keys; для новых RouterOS предпочтителен Ed25519. TLS-сертификат для этого
сценария не требуется: он относится к HTTPS/WebFig или API-SSL. Создавать
сертификаты на роутере будем только при отдельной необходимости безопасного
WebFig/API-доступа.

Параметры доступа:

- RouterOS user group: `read,ssh`;
- право `test` добавлять только если понадобятся активные проверки
  (`/ping`, traceroute и аналогичные команды);
- не выдавать права `write`, `policy`, `sensitive`, `password`, `reboot`,
  `sniff`, `api`, `rest-api` и другие права, не требуемые для read-only-аудита;
- авторизация по отдельному SSH-ключу RSA 4096, хранящемуся на Mac в
  `~/.ssh/` и не попадающему в Obsidian, Dropbox `clients` или документы;
- публичный ключ импортируется только для `codex_audit`;
- SSH не публиковать напрямую в интернет и не делать port-forward с WAN;
- доступ к SSH ограничить management-сетью или management WireGuard-туннелем;
- для SSH отключить forwarding (`forwarding-enabled=no`), если он не нужен.

Для основной домашней площадки можно использовать локальный адрес, если Mac
находится в ее сети. Для Орехово нужен отдельный сетевой контекст:

- предпочтительно management WireGuard с уникальным адресом туннеля, например
  из отдельной сети `10.255.0.0/24`;
- альтернативно — отдельный jump-host внутри сети Орехово с доступом к нему по
  SSH;
- подключение к `192.168.88.1` с той же машины без отдельного маршрута не
  считать способом доступа к Орехово: этот адрес может вести к роутеру другой
  площадки.

Поскольку у площадок одинаковый IP, для каждого SSH-алиаса нужен отдельный
`UserKnownHostsFile`. Нельзя удалять или заменять запись `192.168.88.1` в общем
`.local/ssh/known_hosts`: она относится к другой площадке и защищает ее от подмены
SSH host key.

Операционная схема после настройки:

1. В `~/.ssh/config` завести отдельные алиасы, например
   `mikrotik-home` и `mikrotik-orekhovo`, с разными маршрутами и ключами.
2. Перед анализом проверить, что SSH-ключ принят и отвечает именно нужная
   площадка: identity, модель, RouterOS version и MAC/serial из read-only-команд.
3. Для текущего аудита использовать `/export hide-sensitive` и команды просмотра
   состояния; полные backup-файлы хранить только в Dropbox System.
4. Любое изменение конфигурации выполнять только после отдельного подтверждения,
   свежего backup/export и проверки Safe Mode.

Официальные ограничения и возможности RouterOS:

- [User and SSH keys](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User)
- [SSH server](https://help.mikrotik.com/docs/spaces/ROS/pages/132350014/SSH)
- [IP services](https://help.mikrotik.com/docs/spaces/ROS/pages/103841820/Services)
- [RouterOS firewall](https://help.mikrotik.com/docs/spaces/ROS/pages/250708066/Firewall)

## Важное ограничение

Основная домашняя площадка и площадка **Орехово, Детская 11** являются
географически разными независимыми сетями. На обеих площадках локальный адрес
MikroTik одинаковый: `192.168.88.1`.

Это нормально, пока сети не объединены напрямую в одну маршрутизируемую схему.
Адрес `192.168.88.1` означает локальный роутер текущего сетевого контекста:

- при подключении к сети Орехово он должен вести к роутеру Орехово;
- при подключении к основной домашней сети он ведет к текущему MikroTik hAP ax3;
- при подключении через VPN результат зависит от того, в какую площадку заведены
  маршрут и туннель;
- если площадки будут связаны Site-to-Site VPN, одинаковые подсети
  `192.168.88.0/24` потребуют отдельного решения: NAT, смены подсети одной
  площадки или иной схемы маршрутизации.

Текущая проверка подтверждает доступ к одному из роутеров по адресу
`192.168.88.1`, но без входа в RouterOS не позволяет окончательно определить,
что это именно площадка Орехово. До идентификации устройства не менять
адресацию и не выполнять команды записи.

## Первичный аудит: завершен

`2026-08-11` выполнены без изменения сетевой конфигурации:

1. Подтверждены доступность, identity, модель и версия RouterOS.
2. Создан read-only SSH-доступ `codex_audit` с отдельным RSA 4096 key.
3. Проверены сервисы управления, WAN, LAN, DHCP, firewall, NAT и VPN.
4. Сняты `/export hide-sensitive` и binary backup в Dropbox System.
5. Составлена [отдельная схема и описание конфигурации](<Orekhovo_Detskaya_11_Router_Configuration.md>).

## Команды для будущей проверки

Если SSH включен и доступ выполняется из LAN площадки:

```bash
ssh admin@192.168.88.1
```

После входа в RouterOS:

```routeros
/system identity print
```

```routeros
/system resource print
```

```routeros
/system package print
```

```routeros
/interface print
```

```routeros
/ip address print
```

```routeros
/ip route print
```

```routeros
/ip service print
```

```routeros
/export hide-sensitive
```

## Что не делаем до отдельного подтверждения

- Не меняем пароль `admin`.
- Не включаем/выключаем сервисы управления.
- Не меняем LAN IP и DHCP.
- Не добавляем WireGuard/BTH.
- Не импортируем конфигурацию с основной площадки.
- Не делаем reset configuration.

## Открытые вопросы

- Какое физическое устройство подключено к каждому из `ether2`-`ether5`.
- Какие LAN-клиенты критичны и какое допустимо окно недоступности.
- Нужен ли отдельный management VPN и должно ли Орехово интегрироваться с
  TimeWeb/Fornex/Cenuta архитектурой.
- Требуется ли входящий доступ извне и предоставляет ли Asarta публичный адрес
  либо услугу port-forward.

## Правила хранения данных

В Obsidian можно хранить:

- модель;
- версии;
- IP-адреса;
- описание sanitized export и контрольной суммы;
- описание схемы;
- команды и порядок действий.

В Obsidian не хранить:

- пароль `admin`;
- private keys;
- preshared keys;
- полные импортируемые VPN-конфиги;
- sanitized и полные RouterOS exports;
- бинарные RouterOS backups.

Полные backups и exports хранить во внешнем Dropbox System, в отдельном каталоге
для площадки Орехово.

Current storage path: `System/Mikrotik/current/orekhovo-router/`.
