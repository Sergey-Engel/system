---
type: configuration
status: audited-snapshot
updated: 2026-10-17
tags: [mikrotik, fethiye, backup, audit]
---

# MikroTik Фетхие: стартовый паспорт и аудит

> Текущий подшаг 17 октября: ограниченный IPIP outage принят на MacBook
> по terminal IPv4/HTTPS с DNS bypass и отдельной recovery-пробой.
> Первый recovery LAN ping 2/3 сохранен как предупреждение, причина не установлена.
> Финальный Local подтвержден `194.61.140.217`, все 10 Remote controls
> disabled, прежний lease `.89.197` закреплен static без смены IP/DNS/gateway.
> Общие DNS/default/Wi-Fi/Deco не менялись. Постоянный Remote, полный WAN/TimeWeb
> outage и IPv6-negative не приняты. Latest backup/current:
> `.local/backups/fethiye/20261017T084141Z-post-egress/`, VERIFIED_TRANSFER,
> initial неизменен. [Результаты и предупреждения](../../history/2026-10-17-egress-fail-closed.md).

> 16 октября: WireGuard Фетхие `.3` - TimeWeb `.1` в `10.60.60.0/29`
> расширен до управляемой LAN-пары `.89/24` ↔ `.88/24` Нахимова.
> MacBook -> gateway Нахимова подтвержден, default/NAT/DNS/Deco не менялись.
> Входящие сервисы MacBook и удаленный Internet-выход не приняты.
> Latest backup/current: `.local/backups/fethiye/20261016T124357Z-post-s2s-lan/`, VERIFIED_TRANSFER.
> Initial неизменен; reboot/restore drill не выполнялись.
> [Текущие результаты и ограничения](../../history/2026-10-16-site-to-site-lan.md).

> 16 октября, 11:56-11:57 Europe/Istanbul: strong-crypto=yes, новый strict
> SSH/SFTP проверен с прежним host key. NTP клиент принят пользователем.
> Минимальная подготовка завершена; VPN пока не создан. Последний backup/current:
> `.local/backups/fethiye/20261016T085739Z-post-ssh-crypto/`.

> 16 октября, 11:50-11:51 Europe/Istanbul: NTP client synchronized через
> `0.tr.pool.ntp.org` / `1.tr.pool.ntp.org`; timezone Europe/Istanbul сохранен,
> NTP server выключен. Router PASS, клиент после NTP ожидается.
> Последний verified backup/current: `.local/backups/fethiye/20261016T085126Z-post-ntp/`.
> Клиентский WebFig после отключения лишних сервисов подтвержден.

> 16 октября, 11:43 Europe/Istanbul: FTP/Telnet/API/API-SSL выключены;
> SSH/SFTP/www и router Internet/DNS проверены, клиентский WebFig ожидается.
> Последний verified backup: `.local/backups/fethiye/20261016T084353Z-post-services/`,
> current синхронизирован. Country Turkey принят: MacBook переподключился,
> внешний сайт работает, IP `.89.197`. История ниже остается датированными срезами.

> 16 октября, 11:29-11:32 Europe/Istanbul: country wifi1/wifi2 установлен в
> Turkey, оба radio running; SSID/пароль/width не менялись. Клиентская проверка
> после этого изменения ожидается. Последний verified backup и current:
> `.local/backups/fethiye/20261016T083227Z-post-wifi-country/`.

> 16 октября, 10:46 Europe/Istanbul: новая LAN `192.168.89.0/24`, локальный
> WebFig `192.168.89.1`, pool `.100-.199`, gateway/DNS `.1`. Router PASS,
> MacBook DHCP/Internet/WebFig проверены. WAN `.68.117` и Deco не изменялись. Актуальный
> snapshot: `.local/backups/fethiye/20261016T074642Z-post-lan-renumber/`,
> также materialized в `.local/config/hosts/fethiye/current/`.
> Initial ниже остается историческим. Пароль сохранен по решению владельца;
> вход SSH по пользовательскому ключу проверен. [Лог](../../tasks/PLAN-fethiye-site-to-site.md).

> Последующее изменение 16 октября, 09:57 Europe/Istanbul: раскрытый SSH
> host key заменен, новый strict SSH проверен. Fresh backup:
> `.local/backups/fethiye/20261016T065747Z-post-host-key-rotation/`.
> Пароль admin пока прежний. Ниже сохранен исторический initial-срез;
> старые backups содержат прежний ключ и не являются актуальным baseline.
> [Текущий план и лог](../../tasks/PLAN-fethiye-site-to-site.md).

## Достоверность и границы

Live-срез 16 октября 2026, начало **05:48:41 UTC / 08:48:41 Europe/Istanbul**.
Авторизация admin предоставлена пользователем. Модель, serial и настройки
прочитаны с нового устройства, не из паспорта Нахимова. SSH host public key
получен через авторизованный WebFig и закреплен в отдельном known_hosts;
последующий SSH проверял точное совпадение ключа (RejectPolicy).

Это начальное рабочее состояние после подключения ether1 к Deco и добавления
пользователем разрешения SSH/WebFig с одного Mac. Это **не нетронутый заводской
backup**: пароль admin уже изменен пользователем, WAN подключен, management rule
добавлено до аудита. Заводской template сохранен отдельно, но не исполнялся.
Сеть, firewall, Wi-Fi, пользователи, версии и время аудитом не менялись.

## Идентификация

| Параметр | Значение |
| --- | --- |
| Identity | `MikroTik` |
| Модель | hAP ax3, `C53UiG+5HPaxD2HPaxD` |
| Serial | `HM20B6QXS8H` |
| RouterOS / channel | `7.19.6 (stable)`, build `2025-09-12 09:02:42` |
| Пакеты | routeros и wifi-qcom, оба 7.19.6 |
| RouterBOOT | factory/current/upgrade 7.19.6 |
| Architecture / CPU | arm64, 4 ядра, текущая частота 1320 MHz |
| RAM / NAND | 1024 MiB / 128 MiB |
| Ресурсы в срезе | CPU 2%, RAM свободно 660 MiB, NAND 94.9 MiB, bad blocks 0% |
| Температура | 51 C, моментное значение, не нагрузочное испытание |
| Лицензия | Level 6 |
| Часовой пояс | Europe/Istanbul, autodetect включен |
| Синхронизация | NTP client выключен; IP Cloud update-time=yes |

Устройство отличается от Нахимова (serial `HKM0BDXYG74`). По совпадающему
адресу `192.168.88.1` нельзя выбирать площадку или переносить host trust.

## Топология и адреса

```text
SkyFiberNet radio -> антенна крыши -> PoE -> Deco main (PPPoE)
                                                |
                                   LAN 192.168.68.0/24
                                                |
                                  ether1 нового MikroTik
                                   DHCP 192.168.68.117
                                                |
                                  NAT / bridge 192.168.88.1
                                     /                  \
                            ether2-ether5          wifi1 / wifi2
```

Deco управляется оператором/владельцем, пользователь имеет роль менеджера.
Решение пользователя: не менять Deco, подключить MikroTik за ним по Ethernet.
Модель PoE/антенны дальше не исследуется по решению пользователя.

| Объект | Конфигурация |
| --- | --- |
| ether1 | WAN list, MAC `D0:EA:11:12:F5:E8`, DHCP client bound |
| Ethernet uplink | 1 Gbps full-duplex, link-ok; это скорость до Deco, не WAN-тариф |
| WAN address | `192.168.68.117/24`, динамический, не зарезервирован на Deco |
| Default route | DHCP через `192.168.68.1`, distance 1 |
| DNS upstream | DHCP `10.10.10.2`, `192.168.68.1`; DoH не задан |
| bridge | LAN list, RSTP, MAC `D0:EA:11:12:F5:E9`, VLAN filtering выключен |
| LAN ports | ether2-ether5, wifi1, wifi2 входят в bridge; ether1 не входит |
| LAN | `192.168.88.1/24` |
| DHCP server | defconf на bridge; `.10-.254`; lease 30 минут |
| DHCP network | gateway/DNS `192.168.88.1` |
| NAT | masquerade через WAN list; без NAT для IPsec-policy traffic |
| IPv6 | Включен стек, только link-local/loopback, нет DHCPv6 client и default route |

Deco PPPoE WAN в срезе 15 октября имел публичный IPv4, IP Cloud MikroTik
16 октября наблюдает тот же адрес. Это не публичный WAN самого MikroTik:
он остается за NAT Deco. Статичность внешнего IP и входящий UDP не проверены.

## Wi-Fi и клиенты

| Интерфейс | Диапазон | Ширина | MAC |
| --- | --- | --- | --- |
| wifi1 | 5 GHz AX | 20/40/80 MHz | `D0:EA:11:12:F5:ED` |
| wifi2 | 2.4 GHz AX | 20/40 MHz | `D0:EA:11:12:F5:EE` |

Оба AP running, SSID `MikroTik-12F5ED`, WPA2-PSK/WPA3-PSK, FT и FT-over-DS
включены. Радио сообщает **current-country=Latvia**; country не задан явно
в экспортированной конфигурации. Для эксплуатации в Турции требуется
отдельно согласовать корректный country и каналы, не выбирать их по догадке.
Пароль Wi-Fi есть только в sensitive export/private store.

В registration table 4 клиента: три на wifi1 и один на wifi2. DHCP видит
MacBookAir `.252`, iPhone `.251`, Watch `.253` и клиент без имени `.254`.
Это новый SSID, private MAC отличается от сети Deco. Не переносить
сопоставления по одинаковому имени без подтверждения владельца/IP.
Сквозная производительность клиентов за MikroTik не измерялась.

## Firewall и управление

- Input: первым стоит `Allow admin Mac from Deco LAN`: ether1, source
  `192.168.68.115/32`, TCP 22/80. Далее default established/related/untracked,
  invalid drop, ICMP, loopback accept, drop входа не из LAN.
- Forward: default IPsec accept, FastTrack established/related, established
  accept, invalid drop, drop новых WAN подключений без DSTNAT.
- Пользовательские mangle/policy-routing rules отсутствуют; только main routes.
- IPv6 имеет default firewall. MAC server, MAC WinBox и discovery ограничены LAN.
- SSH/HTTP доступны с admin Mac за Deco. WinBox и остальные сервисы этим
  разрешением не открываются на WAN. DNS remote requests=yes обслуживает LAN;
  отдельного разрешения DNS с ether1 нет.
- Включены FTP, Telnet, SSH, WWW, WinBox, API, API-SSL; service address пустой.
  WWW-SSL выключен, API-SSL без назначенного сертификата. Firewall ограничивает
  WAN, но в LAN эти сервисы требуют последующего hardening.
- SSH strong-crypto=no, RSA 2048; forwarding выключен.
- Один enabled admin с full, без ограничения address; user SSH keys отсутствуют.
- UPnP выключен. BTH revoked-and-disabled. IP Cloud DDNS auto.
- Нет WireGuard interfaces, IPsec peers, активных PPP sessions, сертификатов,
  scheduler jobs. Два default button scripts: dark-mode и wps-accept.
- Disk settings допускают auto media/SMB sharing; storage devices в срезе нет.

HTTP WebFig не шифрует канал. Пароль admin уже передавался в чат;
рекомендуется заменить после завершения подготовки, без повторной отправки
в чат. Не считать firewall source IP полноценной идентификацией компьютера.

## Выводы и необходимые последующие действия

| Приоритет | Наблюдение | Действие перед постоянной эксплуатацией |
| --- | --- | --- |
| Высокий | LAN `192.168.88.0/24` совпадает с Нахимова | Выделить непересекающуюся LAN до site-to-site; пока не изменено |
| Высокий | Экспорт SSH host private key попал в диагностический tool output при чтении file detail | Согласовать ротацию host key и повторное закрепление trust; не выполнено автоматически |
| Высокий | Пароль admin сообщен в чат, WebFig по HTTP | Согласовать смену пароля/управление по SSH key либо HTTPS; текущий доступ сохранен |
| Средний | current-country Latvia | Согласовать country Turkey и проверить каналы; не изменено |
| Средний | Admin source `.115` и WAN `.117` динамические | Спроектировать устойчивое управление без расширения доступа на всю LAN |
| Средний | Лишние сервисы LAN, SSH strong-crypto=no, NTP выключен | Отдельный hardening changeset, включая MAC/discovery и storage settings |
| Плановый | RouterOS/RouterBOOT 7.19.6 | Отдельно проверить актуальный stable и совместимость; обновление не выполнялось |
| Плановый | VPN и резервирования еще нет | Применить проект моста после устранения пересечения LAN |

Наличие Интернета не означает, что мост готов. Для клиентов Deco путь не
менялся. Новые VPN identities/наблюдения не создавались; серверные BTH/FLEX
contracts, controllers и dashboards этим аудитом не меняются.

## Проверки доступности

С MikroTik: DNS `example.com` разрешился; ping Deco 3/3, avg 0.334 ms;
ping `1.1.1.1` 3/3, avg 42.683 ms; IPv6 ping - no route.
С admin Mac: SSH port доступен, strict SSH с admin успешно выполнен;
HTTP вернул 200, вход WebFig успешен. Это короткие тесты, не SLA и не speed test.

Замер владельца 15 октября **без VPN**: download 29.8 Mbps, upload 5.48 Mbps,
ping 42 ms, jitter 27 ms, loss 0%, сервер Turkcell Antalya. Это измерение
асимметричного канала, не подтвержденная тарифная скорость.

## Backup и стартовые конфигурации

Все пути ниже локальные и исключены из Git:

- [Датированный backup](../../../.local/backups/fethiye/20261016T054841Z-initial/).
- [Стартовый sensitive export](../../../.local/config/hosts/fethiye/initial/router-export.rsc).
- [Current snapshot](../../../.local/config/hosts/fethiye/current/router-export.rsc).
- [Переносимое хранилище](../../../.local/secrets.json): точные байты snapshots,
  пароль admin, отдельный случайный пароль encrypted backup, известный host key.

| Артефакт | Размер | SHA-256 |
| --- | ---: | --- |
| router.backup | 33742 | `9e79931baecdd02a2aa05025bc8812e00bc4b352922265546dc09b10438f7ae0` |
| router-export.rsc | 8620 | `15c1d6720d1a6b76cb136ffa88ee2e13b11c65280ef7f65e7d121d5c9fa7fdcf` |
| router-export-redacted.rsc | 8574 | `306a30400137ebbe668c22a35f2088d6885c0c49352776369ed719bf0e6e033f` |
| factory-default-template.txt | 71006 | `45f865fc33ab163a58086eaceeb9b19cbe0c947820b5bcf805b2fb95d11296fc` |

В backup также 8 диагностических файлов и verification.json с inventory,
размерами и checksum каждого артефакта. Binary backup зашифрован AES-SHA256
отдельным случайным паролем, не admin password. Статус **VERIFIED_TRANSFER**:
два независимых чтения SFTP совпали, export body до/после сбора совпал.
Реальный restore/decryption drill не выполнялся. RSC и secret store не
зашифрованы, защищены правами 600, каталоги 700. Redacted export тоже private.

На роутере оставлен только созданный encrypted backup
`fethiye-initial-20261016T054841Z.backup`. Два временных файла host-key export
удалены, что подтверждено последующим file list. Сам host key не менялся.
Private диагностический system.txt содержит прежний file-detail с ключом;
он не должен публиковаться. Этот инцидент записан в verification.json.

Для восстановления: сначала проверить serial/модель, version и hashes,
извлечь пароль backup из private store; выполнять restore только в отдельном
окне с физическим доступом и ожидаемым reboot. Binary предпочтителен для того
же устройства; RSC не является побайтовым клоном (не содержит пароли users и
все ключевые объекты). Factory template не равно фактическому initial export.
Ни restore, ни import, ни reset не запускались.

Связи: [паспорт площадки](network-passport.md),
[проект моста](../../architecture/Nakhimova_Fethiye_Site_to_Site_Design.md),
[правила хранения](../../operations/storage-and-transfer.md),
[доступ](../../operations/access.md).
