---
type: checkpoint
status: accepted-network-scope
created: 2026-10-16
updated: 2026-10-16
---

# Связь LAN Нахимова И Фетхие

Подшаг 7B [общего плана](../tasks/PLAN-fethiye-site-to-site.md) применен после
принятого пользователем HTTPS на втором плече. [Точный scope/rollback](../architecture/Site_to_Site_LAN_Changeset.md).
Только IPv4 `192.168.88.0/24` ↔ `192.168.89.0/24`, L3 через host `wg-s2s`
TimeWeb. Deco `.68/24` не включен, L2/discovery не добавлены.

## Изменения

Каждый роутер: один main route удаленной LAN через `wg-s2s-tw`, два точных
bridge/WG forward accept без invalid и ICMP к LAN IP самого роутера.
Четыре новых объекта на каждом, marker `s2s-lan-20261016`; в существующий
peer добавлена только противоположная LAN. Объекты сначала disabled,
проверены до активации. NAT, mangle, DNS, FastTrack и default не менялись.

TimeWeb: три owned-файла (WG config, guard.nft, manifest), два exact
proto-static LAN route. Только своя nft table заменена atomic transaction;
syncconf без restart. Peer `.2` владеет только `.88/24`, peer `.3` `.89/24`.
Host input/output не расширены; чужой transit и управление закрыты.
Ключи/endpoints, boot ID/ifindex и все прежние VPN identities сохранены.

## Реальные Проверки

- Router LAN-source ping `.88.1` ↔ `.89.1`: по 3/3, 1400 байт. Оба служебных
  плеча до `.1` и обычный Internet ping обоих роутеров также по 3/3.
- Router SSH-negative через LAN pair: рост input-deny 0 -> 4 на Фетхие и
  1 -> 5 на Нахимова. Host TCP к обеим LAN закрыт, output drop растет.
- Чужой реальный transit из temporary netns закрыт: forward drop 0 -> 2;
  временные namespace/veth удалены. Обе разрешенные forward-направления
  подтверждены counters, не только конфигом/handshake.
- Пользователь подтвердил `ping -c 3 192.168.88.1` с MacBook на Wi-Fi MikroTik:
  «Есть ответы, потерь нет». Raw ping output не присылался; это именно
  пользовательское подтверждение, не сохраненный дамп измерения агента.
- Входящий ping к известному lease MacBook `.89.197` не ответил ни с
  Нахимова, ни локально с Фетхие (size 64). Причина не установлена;
  firewall/stealth/актуальность клиента не объявлены доказанной причиной.
  Входящие сервисы MacBook, приложения и discovery не приняты.
- VPN-приложения на MacBook отдельно не проверены. Для последующей проверки
  Internet egress их состояние нужно согласовать, чтобы не смешать пути.

## Мониторинг И Хранение

Legacy protected snapshot и runtime/BTH/monitoring contracts неизменны,
check PASS, bindings/generation не переподписывались. Изолированный startup
guard принят с новой точной LAN-политикой; periodic recovery еще отдельный этап.
Новых FLEX controllers/locks нет; console namespace fleet 3/3 ready,
HTTP `/state` и controls PASS, sandbox не расширен.

Два fresh valid upstream-цикла: `12:40:08.461545` и `12:42:08.944641 UTC`.
Prometheus: оба S2S peer fresh/present/rate-valid=1 с ролью `WG-S2S-TW (LAN)`;
оба upstream valid. Grafana persisted main/detail resources и новые mappings
обоих роутеров проверены read-only. Authenticated UI render не проверен.

67 profiles / 22 devices / 49 WG observations. Изменены только AllowedIPs
двух S2S профилей, не их keys/endpoints; остальные 65 профилей побайтово
сохранены. Current masters и `.local/secrets.json` синхронизированы;
initial Фетхие не изменен. Полные конфиги/ключи не публиковались.

## Копии После Изменения

| Узел | Snapshot | Результат |
| --- | --- | --- |
| TimeWeb | `2026-10-16T124355Z_current-config` | VERIFIED, 386 host files, 61 offline restore checks |
| Фетхие | `20261016T124357Z-post-s2s-lan` | VERIFIED_TRANSFER, encrypted bytes считаны дважды, export без drift |
| Нахимова | `20261016T124635Z` | VERIFIED_TRANSFER, encrypted binary считан дважды, export совпал с live |

TimeWeb archive SHA-256:
`045ff634ad4aa195e3b98f28ed99997de59f7a0f379fb262cd7a2cabd2e75cf1`.
Перед изменением получены fresh VERIFIED копии всех трех VPS и отдельные
копии обоих роутеров. Реальные restore/reboot не выполнялись.

## Остановка До Активации

RouterOS 7.19 Фетхие не возвращает `disabled` в `print as-value`. Первичная
проверка ошибочно приняла отсутствующее поле за False и остановилась после
создания отключенных объектов, до host update/enable. Не повторяли add.
Через explicit `get <id> disabled` подтвердили оба маршрута и все шесть
firewall rules disabled; сверили exact owned scope и продолжили read-back.
Добавлен RED/GREEN regression: missing flag означает unknown и требует get,
не считается включенным. Правило сохранено в README site-to-site.

Evidence: `.local/backups/site-to-site/20261016T122827Z-lan/`.
Локальные проверки: 321 tests PASS; repository/link/profile/secret scan и
`git diff --check` PASS. Private store VERIFIED: 763 files, 295 records.
Проверка `git add --dry-run` не включает private files; commit/push не делались.
Принят только текущий сетевой объем. Remote Internet, failover, direct B,
reboot/restore и общая эксплуатационная приемка всего этапа A еще впереди.
