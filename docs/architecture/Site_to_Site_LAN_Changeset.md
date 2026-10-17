---
type: changeset
status: accepted-network-scope
created: 2026-10-16
updated: 2026-10-16
---

# Связь Управляемых LAN Через TimeWeb

## Объем Подшага 7B

Основание: согласованный [план](../tasks/PLAN-fethiye-site-to-site.md),
пользовательское разрешение выполнять по шагам и подтвержденный HTTPS MacBook
после второго плеча. Только IPv4 `192.168.88.0/24` (Нахимова) ↔
`192.168.89.0/24` (MikroTik Фетхие). Deco `192.168.68.0/24` не включать.
Общий DHCP/L2/discovery, удаленный Internet-выход и резервирование не входят.

Ключи/порты/интерфейсы существующих двух плеч не менять. На каждом роутере
добавить только удаленную LAN в AllowedIPs существующего peer, один main
маршрут через `wg-s2s-tw`, два ограниченных forward accept (bridge ↔ WG,
только точная пара LAN, не invalid) перед собственными drop и ICMP к LAN IP
самого роутера. Новые правила и route сначала disabled. SSH/HTTP/WinBox через
туннель остаются закрыты; другие источники и назначения закрывает прежний guard.
NAT/mangle/FastTrack/default/DNS/Wi-Fi не менять. Существующий private-LAN
main bypass Нахимова проверить до применения.

TimeWeb host peer `.2` получает только `192.168.88.0/24`, peer `.3` только
`192.168.89.0/24`; ключевые identities сохранить. Два main route через
`wg-s2s`, proto static; persistent AllowedIPs обеспечивают их восстановление
через wg-quick. Своя nft table разрешает только `wg-s2s -> wg-s2s` между
этой парой LAN; invalid и остальной transit закрыты. Host input/output guard
не расширять. Не давать доступ LAN к сервисам VPS. NAT не добавлять.

Изменить только три owned-файла (WG config, guard.nft, manifest.json),
atomic nft transaction только своей table, `wg syncconf` без restart.
Сверить фактические routes после syncconf: сама команда маршруты не создает.
Recovery/BTH/monitoring contracts старого relay не переподписывать:
потребуются отдельные read-only checks и доказательство неизменности.

## Проверки И Откат

До изменения: fresh VERIFIED VPS backups, encrypted backups обоих роутеров,
current/master/store parity, serial/trust, свободные remote LAN routes,
static firewall anchors, исходные peer keys/AllowedIPs и protected snapshot.
Точный baseline обязателен; неизвестный drift останавливает запись.

Порядок: staged disabled объекты обоих роутеров -> guarded host update и
маршруты -> read-back -> enable новых разрешений -> enable новых routes.
Без перезапуска существующих туннелей и без удаления старых правил.
Marker новых объектов `s2s-lan-20261016`; per router четыре новых объекта
и одно изменение AllowedIPs существующего peer.

Откат: сначала disable только новых routes; после сверки ownership убрать
четыре новых объекта каждого роутера и вернуть AllowedIPs `.1/32`.
Восстановить три pinned host-файла/own nft table, syncconf, удалить только
два точных собственных proto-static LAN route. Не делать общий flush,
не восстанавливать старый backup целиком и не менять старые WG identities.

Проверки: LAN-source ping между router LAN IP с размером 1400 в обе стороны,
сохранность служебных плеч и местного интернета, TCP management denial с
router counters, host-service/transit denial с nft counters. Затем MacBook
на Wi-Fi MikroTik должен проверить `192.168.88.1`; это подтверждает клиентский
путь, но не приемку приложений/AirPlay. До клиентского подтверждения 7B не принят.

Профили двух S2S роутеров обновить без ротации ключей; 65 прочих профилей
сохранить побайтово. Inventory сохраняет 22 устройства/49 WG observations,
подпись нового назначения обновляется совместно с dashboards. Требуются
console namespace и HTTP `/state`, два свежих валидных upstream-цикла,
Prometheus/Grafana persisted resources и новые post-backups всех измененных узлов.
Authenticated Grafana UI, reboot/restore и приложения не считать проверенными.

Основание параметров: [RouterOS WireGuard site-to-site](https://help.mikrotik.com/docs/spaces/ROS/pages/69664792/WireGuard),
[wg syncconf](https://man7.org/linux/man-pages/man8/wg.8.html).

## Результат

Применены и прочитаны обратно четыре новых объекта и изменение AllowedIPs
одного peer на каждом роутере; три owned-файла и два host route на TimeWeb.
Boot ID/ifindex и ключи существующих плеч сохранены. Router LAN-source ping
по 3/3 в обе стороны, размер 1400; служебные плечи и локальный Internet ping
обоих роутеров также 3/3. TCP 22 управления закрыт с реальным ростом router
input-deny counters; чужой transit и host-доступ закрыты с nft counters.

Пользователь подтвердил MacBook -> `192.168.88.1` без потерь. Входящий ping
к MacBook `.89.197` не ответил также при прямой локальной проверке с Фетхие;
причина не установлена. Не считать приложения, входящие сервисы и discovery
принятыми. Статус VPN-приложений на MacBook отдельно не проверен.
Обычный Internet egress не переключался.

Старые contracts/snapshot и 65 прочих профилей неизменны. Два S2S профиля
изменили только AllowedIPs, не ключи/endpoints. Console namespace/HTTP,
два fresh valid upstream-цикла, Prometheus и Grafana persisted mappings PASS.
Post-backups TimeWeb `2026-10-16T124355Z_current-config` VERIFIED;
Фетхие `20261016T124357Z-post-s2s-lan` и Нахимова `20261016T124635Z`
VERIFIED_TRANSFER. Current masters/canonical store синхронизированы.
[Полный checkpoint](../history/2026-10-16-site-to-site-lan.md).
