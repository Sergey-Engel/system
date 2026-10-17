---
type: changeset-design
status: accepted-icmp-only
created: 2026-10-16
updated: 2026-10-16
tags: [mikrotik, wireguard, fethiye, timeweb]
---

# Изолированный пилот Фетхие - TimeWeb

## Решение и границы

Согласовано пользователем для шагов 5-6 [плана](../tasks/PLAN-fethiye-site-to-site.md).
Подготовка и проверка writer выполняются до серверных записей.

Не добавлять новый peer в существующие `wg-home`, `wg-clients` или
`wg0` контейнера wg-relay. На TimeWeb использовать отдельный host WireGuard
interface, отдельные identities и собственные firewall-объекты. Это не
гарантирует полную независимость от общего хоста, но уменьшает область
изменений действующих BTH/FLEX/selector routing contracts.

```text
Сейчас: MacBook -> MikroTik Фетхие -> Deco -> местный интернет

Первый пилот, только служебные IP:
MikroTik Фетхие -- исходящий WireGuard --> TimeWeb host wg-s2s
   10.60.60.3                                  10.60.60.1

Следующий этап, после приемки первого плеча:
Нахимова -- новое исходящее WG-плечо --> тот же изолированный hub
10.60.60.2

Существующий wg-relay / wg-home / FLEX: остаются отдельным контуром.
```

## Настройки Пилота

Параметры ниже были предложены и затем применены в этом changeset.
Перед следующим изменением повторить live-проверки, не принимать drift.

| Параметр | Примененное решение |
| --- | --- |
| Hub | TimeWeb `94.241.171.65`, root network namespace, не wg-relay |
| UDP port | `51860`, был свободен перед deploy; теперь отдельный owned listener |
| Интерфейсы | `wg-s2s` на TimeWeb; `wg-s2s-tw` на MikroTik Фетхие |
| Tunnel network | `10.60.60.0/29`, проверен до назначения; теперь выделен пилоту |
| Hub / Фетхие / будущее Нахимова | `.1/29` / `.3/29` / `.2/29` |
| MTU | Начать с 1420, проверить реальные крупные пакеты перед LAN/egress |
| Фетхие endpoint / keepalive | TimeWeb UDP 51860; persistent keepalive 25 секунд |
| AllowedIPs на первом пилоте | На hub peer Фетхие только `.3/32`; на Фетхие peer hub только `.1/32` |
| LAN routes/default routes | Не добавлять на первом плече; LAN `.89.0/24` не объявлять hub до шага 7 |
| Клиентский интернет | Остается местным через Deco; MacBook без изменения gateway и VPN-профилей |
| Нахимова | На первом пилоте не менять вообще; второе новое плечо отдельным подшагом |
| NAT | На первом пилоте не добавлять; между площадками позднее без NAT |
| Управление | Существующий локальный SSH через Deco сохранить; через пилот пока только ICMP |
| IPv6 | В пилот не включать; не открывать параллельный обход политики |

Перед назначением `10.60.60.0/29` расширить проверку до всех namespaces,
сохраненных профилей и реестра адресов, включая Fornex/Cenuta. Отсутствие
host route само по себе не доказывает, что диапазон нигде не назначен.
Идентичность MacBook в Wi-Fi не приравнивать к существующим WG/FLEX profiles
по одному имени; клиентские VPN учитывать отдельно при тестах egress.

## Firewall и восстановление

На TimeWeb IP forwarding уже включен. Поэтому подключение WG без собственных
ограничений не является безопасным служебным пилотом. Новый guard обязан
запретить forwarding с/на `wg-s2s`, доступ к host services и allowlist только
служебный ICMP между `.1` и `.3`; UDP handshake 51860 обрабатывается отдельно.
WG peer AllowedIPs не заменяют firewall. Не менять существующие policy или
таблицу `inet reality_fornex`; использовать отдельную owned table/unit.

Guard загружается до доступности нового interface; при невалидном guard
поднимать туннель нельзя. Не использовать глобальный `nft flush ruleset`,
Docker restart/recreate, общий route flush, retired WG writers или разрешение
SSH/WWW на публичном WAN MikroTik. Не менять default интернет-выход TimeWeb.

Новые `/etc/wireguard/wg-s2s.conf`, guard и startup/recovery unit должны быть
включены в backup coverage до deployment. Автозапуск через wg-quick/systemd
проверить вместе с очередностью guard; не полагаться на текущий running state.
Новые ключи создаются только для этого changeset; private keys остаются в
`.local`/portable store. На MikroTik передается нужный private key только по
проверенному SSH, вывод ключей и полный export запрещены в публичном журнале.

## Gate до записи

1. Повторить live serial/namespace/baseline и проверить оба protection contracts.
2. Создать fresh schema-3 verified server backup с обязательным составом нового
   контура и отдельный fresh backup Фетхие; preflight pack ниже не заменяет их.
3. Подготовить dry-run diff и scoped rollback с ownership guards.
4. Проверить writer на fixtures: baseline mismatch, занятый IP/port/name,
   чужой peer, неподтвержденный host key, неверный guard, повторный запуск.
   Отказы должны происходить до первой записи. Проверять также полный
   RouterOS export с continuations и dotted property shorthand.
5. Согласовать источник host-WG telemetry, inventory, dashboard/console scope
   и guarded lifecycle; не добавлять фиктивный peer в существующий collector.

## Реальная приемка после записи

1. Handshake и рост counters, затем ping между `.1` и `.3` в обе стороны.
2. Негативные тесты: host SSH/API и transit через пилот закрыты;
   default route MacBook и внешний IP местного выхода не изменились.
3. SSH управления Фетхие через Deco, MacBook HTTPS и локальный WebFig работают.
4. BTH, monitoring guard и runtime check проходят; прежние identities,
   маршруты и защищенный wg-relay snapshot не изменились. Не переподписывать
   прежние contracts ради принятия нового состояния.
5. Новая telemetry отражает именно этот peer/namespace; два свежих валидных
   collector cycles, существующие console controls и Grafana без регрессии.
6. Fresh post-backup, masters/registry/observations согласованы. Новая
   recovery policy публикуется только для точного reviewed scope, если требуется.

Откат удаляет только owned новые peer/interface/unit/firewall objects после
проверки исходных fingerprint/hash. Не восстанавливать весь VPN-сервер из
архива поверх действующих конфигураций как штатный rollback одного пилота.

## Проверенный read-only baseline 16 октября

- Нахимова serial `HKM0BDXYG74`, RouterBOOT 7.24.4, LAN `192.168.88.0/24`.
- TimeWeb runtime recovery, BTH check и monitoring guard check: PASSED.
- Реальные units: `timeweb-runtime-recovery.*`, `vpn-uplink-console.service`,
  `vpn-uplink-pilot.service`, `vpn-uplink-exporter.service`.
- `/state` возвращает HTML fragment, не JSON. Первое чтение с timeout 10 s
  не завершилось; с лимитом 90 s полный fragment получен. Две upstream cards
  `ok`, controls enabled; FLEX `3/3 routes ready`, 0 active / 3 inactive / 0 unknown.
- Exporter: observation_fresh=1 для обоих upstream, HTTPS probe_valid=1
  для gstatic/cloudflare. Это один свежий срез, не post-deploy two-cycle gate.
- `wg-quick` установлен, host IPv4 forwarding=1, UFW inactive.
- Предложенных UDP 51860 и network `10.60.60.0/29` в проверенных listener/routes нет.
- Read-only evidence и hashes:
  `.local/backups/site-to-site/20261016T090427Z-preflight/`.
  Серверная конфигурация и Нахимова не менялись; новый VPN не создан.

## Согласованный Changeset, Подготовка

- Пользователь разрешил первое изолированное плечо ответом «да».
- Fresh schema-3 backups: TimeWeb `2026-10-16T091749Z_current-config`,
  Fornex `2026-10-16T091900Z_current-config`, Cenuta
  `2026-10-16T091926Z_current-config`: VERIFIED.
- Fresh Фетхие: `20261016T093516Z-pre-s2s-pilot`, VERIFIED_TRANSFER,
  без испытания восстановления.
- Расширенный live-аудит: host и container namespaces TimeWeb 2,
  Fornex 8, Cenuta 1; 47 приватных WG/AWG profiles. Адреса/имена/порт свободны.
- Runtime/BTH/monitoring checks PASS. Один monitoring check отказал без
  вывода из-за nonblocking lock; последующий check `VALID generation=26`.
  Не менялись manifest или правила для обхода отказа.
- `tool fetch` на MikroTik запрещен device-mode. Ограничение не ослаблялось;
  клиентский внешний IP не подменяется измерением с роутера.
- Точный пакет, identities, protected baseline и rollback helper находятся
  приватно под `.local/backups/site-to-site/20261016T093901Z-prepared/` и
  `.local/runtime/deploy_s2s_pilot.py`.
- Backup coverage нового контура проверяется целиком: появление хотя бы
  одного файла требует наличия всех шести файлов, включая guard/manifest/unit.

## Примененный Результат

Первое плечо создано; адреса, порт и MTU из таблицы выше применены. Сначала
загружен TimeWeb guard, затем включен host WG; после этого настроен Фетхие.
Файлы startup и rules прошли проверку, source/runtime/master сверены.

На MikroTik пять собственных firewall rules: два forward drop, входной jump
в `s2s-pilot-input`, ICMP allow и завершающий drop внутри этой цепочки.
Разрешение находится раньше запрета **в собственной цепочке**. Новые
input/forward rules действуют раньше прежних accepts/FastTrack; прежние
правила не изменены. Вместе с interface/address/peer это восемь owned objects.

Первоначальная числовая вставка дала неверный порядок ICMP/deny; перемещение
отказало `cannot move builtin` при расположении новых правил перед dynamic
FastTrack dummy. Пакеты тогда блокировались, а не проходили лишним путем.
Исправление использует собственную цепочку без отключения FastTrack,
перезагрузки или ослабления исходного firewall. В последующем writer числовой
anchor 0 запрещен, выбран уникальный static management rule.

Проверено: handshake/counters, ICMP обе стороны, пакеты 1400 bytes,
реальные TCP 22 negatives с ростом input/output drops, реальный host transit
из временного namespace с ростом forward drops. Временные test objects удалены.
Ни LAN routes, ни default routes/NAT не добавлялись. MacBook HTTPS принят
пользователем; затем он подтвердил открытие страницы WebFig по
`http://192.168.89.1`. Повторная авторизация этим не подтверждается.
Служебный ICMP-only пилот принят; полный клиентский egress, его публичный IP
и доступ между LAN не входят в эту закрытую приемку и не объявлены проверенными.

Старые runtime/BTH/monitoring contracts и весь protected snapshot unchanged.
Для несменяемого инфраструктурного пилота нет новых FLEX controls или locks
в console namespace: существующие exact sandbox/tmpfiles paths не менялись,
fleet status из mount namespace консоли 3/3 ready, HTTP state/cards PASS.
Новый host-WG source читает отдельный namespace; Prometheus показывает свежие
данные и валидные скорости. Grafana provisioned resources реально содержат
новый device; авторизованный UI render отдельно не проверен (API 401, login
не сбрасывался). Два свежих valid collector cycles для обоих upstream получены.

Post-backups: TimeWeb `2026-10-16T101524Z_current-config` VERIFIED;
Фетхие `20261016T102035Z-post-s2s-pilot` VERIFIED_TRANSFER. Initial неизменен.
Root WG config, guard/manifest и startup/drop-in материализованы под
`.local/config/hosts/timeweb/current/host/`; новый профиль только Infrastructure.
Откат подготовлен с ownership checks, но реальный rollback/reboot/restore drill
не выполнялись. Новый guard контролирует startup; резервирование и полное
автоматическое восстановление относятся к дальнейшему шагу 9.

[Checkpoint и точные границы приемки](../history/2026-10-16-fethiye-timeweb-pilot.md).
