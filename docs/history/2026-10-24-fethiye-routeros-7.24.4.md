---
type: maintenance-report
status: completed-with-limitations
updated: 2026-10-24
tags: [fethiye, mikrotik, routeros, backup]
---

# Фетхие: RouterOS 7.24.4

Разрешение владельца: обновить Фетхие до той же версии, что на Нахимова.
RouterOS и wifi-qcom обновлены с7.19.6 до7.24.4 stable, arm64.
Не использовалась команда установки latest: ровно два NPK получены по HTTPS
с download.mikrotik.com/routeros/7.24.4/. После SFTP каждый файл прочитан
обратно и побайтово сравнен; SHA256 сохранены в private evidence.
Установка штатных NPK и одна перезагрузка завершились успешно.

RouterBOOT current7.19.6, upgrade7.24.4: отдельная прошивка загрузчика
не выполнялась; auto-upgrade=no сохранен. Нахимова не изменялась.

## Проверка

- Закрепленный SSH host key и serial HM20B6QXS8H совпали до/после.
- WAN DHCP bound192.168.68.117/24, интернет ICMP1.1.1.1:5/5.
- WG peer имеет handshake, RX/TX растут; IPIP running.
- TimeWeb10.60.60.1 через WG:5/5 ICMP.
- SSTP автоматически восстановлен, running/hardware crypto, AES256-GCM;
  Нахимова10.60.64.2 с source10.60.64.1:5/5 ICMP.
- Оба Wi-Fi monitor показывают running после штатного DFS CAC.
  Клиентов регистрации нет; пользовательский интернет с Wi-Fi устройства
  и производительность не проверены.
- Free storage82.7MiB, bad blocks0%, CPU0% в финальной проверке.

## Сверка Конфигурации

Нормализованы menu-only строки нового экспорта, переносы и порядок секций.
Совпали WG/SSTP/PPP, маршруты/routing rules, address lists, NAT/mangle,
Wi-Fi, DHCP reservations, сервисы и пользователи. Порядок filter rules совпал
после исключения прежнего явно экспортированного hw-offload=yes у FastTrack.
Не заявляется побайтовое совпадение всего export между версиями.

Новая версия экспортирует cpu-flow-control=yes для switch1,
name=client1 для DHCP client, advertise-dns=yes для default IPv6 ND;
не выводит hw-offload=yes FastTrack и timezone, совпадающую с auto-detect.
Live timezone осталась Europe/Istanbul, IPv6 ND сообщает, что automatic DNS
advertising не запущен до reapply; IPv6/DNS-настройки не переустанавливались.
Default scripts перемещены по порядку экспорта. Эти отличия сохранены
в private diff, никаких компенсирующих route/firewall изменений не внесено.

## Бекапы И Откат

Private directories `.local/backups/fethiye/`:

- `20261024T060701Z-pre-routeros-7.24.4`;
- `20261024T061007Z-post-routeros-7.24.4`.

Обе копии VERIFIED_TRANSFER: sensitive/redacted exports и AES-SHA256 binary
backup, двойное независимое чтение encrypted bytes и SHA256. Пароль в private
store; конфигурация во время каждого backup не менялась. Restore drill не
выполнялся. Это configuration backups, не disk images.
Post-export/identity материализованы как current с проверкой canonical store.

Для отката локально сохранены официальные routeros/wifi-qcom7.19.6 arm64.
При подтвержденной регрессии: передать оба старых пакета, сверить transfer,
применить штатный package downgrade с перезагрузкой, затем сверить состояние;
восстановление encrypted backup только при необходимости и после оценки
diff. Downgrade не выполнялся и не проверялся как отдельный тест.

Raw exports, package hashes, snapshots и diff:
`.local/backups/fethiye/20261024-upgrade/`; исключены из Git.
Код панели и VPN topology не менялись, release bump не требуется.
