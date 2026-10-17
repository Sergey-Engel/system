---
type: checkpoint
status: local-transport-verified
created: 2026-10-16
updated: 2026-10-16
---

# IPIP Transport В Local

Шаг 8 [плана](../tasks/PLAN-fethiye-site-to-site.md),
[changeset и откат](../architecture/Site_to_Site_Egress_Changeset.md).
Пользователь сообщил исходный public IP, затем подтвердил открытие
`https://example.com` на MacBook Air Sergey после изменения. Это приемка
Local HTTPS, не Remote Internet. Значение IP сохранено как user-reported,
а не agent-verified, в private evidence.

## Применено

- IPIP `ipip-s2s-egress` внутри существующего WG, Нахимова `10.60.61.1/30`,
  Фетхие `.2/30`, MTU 1400, clamp MSS, keepalive 10 s / 3 attempts.
- Только противоположный outer `/32` добавлен к AllowedIPs двух роутеров.
  На hub WG keys/config/AllowedIPs/routes не менялись. Только два файла
  собственной nft guard/manifest обновлены без restart и wg syncconf.
- 24 owned-объекта Фетхие и 29 Нахимова: custom tables, guards и blackholes.
  Все 10 Fethiye Remote controls выключены. Lease `.89.197` dynamic и bound,
  его MAC/IP сверены. Static binding отложен до Remote, без смены адреса.
- Основные defaults, прежние NAT/mangle, DHCP/DNS, Wi-Fi и Deco сохранены.
  Nakhimova return rule затрагивает только WAN -> `.89.197` в собственной
  таблице; LAN-initiated маршрут остается старым WG LAN route.
- Два profile masters меняют только AllowedIPs; 65 остальных файлов без
  изменений. Inventory сохраняет 22 устройства / 49 WG observations /
  67 профилей; роль двух S2S observations теперь `WG-S2S-TW (LAN/IPIP)`.

## Сетевые Проверки

Read-back static exports сохраняет всю исходную конфигурацию, кроме exact
owned delta и двух AllowedIPs. Inner IPIP, прежняя LAN-пара и ICMP к hub:
по 3/3, размер 1400, в обе стороны. Nft IPIP accept counters: `.2` 89 packets,
`.3` 88 packets на момент проверки 14:21:22 UTC. TCP 22 к inner gateways
отклонен с ростом каждого input-deny counter 0 -> 4. Foreign transit с
временного network namespace отклонен: drop 2 -> 4; временные объекты удалены.

Внешний Internet gate **не очищен**: при диагностике Нахимова WAN gateway
5/5, Cloudflare `1.1.1.1` 6/10, Quad9 `9.9.9.9` 4/5. Позднее короткие
пробы 3/3 к `1.1.1.1` прошли на обоих роутерах, но прежние потери сохранены
как предупреждение. Причина не установлена; на основании только ICMP нельзя
приписывать отказ приложению, провайдеру или новой конфигурации.

Оба device-mode запрещают fetch. Попытка read-only fetch Нахимова отклонена;
ограничение не снималось. На TimeWeb получен свежий аутентифицированный UDP
endpoint Нахимова: это наблюдение NAT, **не** HTTPS egress IP verification.
Remote/DNS-redirection на MacBook, приложение и client fail-closed не приняты.

### Квалификация DNS Preset

Все шесть router-originated resolve вернули адрес, но сам факт ответа
недостаточен. Через `1.1.1.1` два имени (`example.com`, `api.ipify.org`)
получили одинаковый `8.47.69.0`, не совпавший с текущим TLS-verified DoH
ответом Cloudflare с TimeWeb. Через `9.9.9.9` все три имени совпали с A sets
reference, включая `www.iana.org`. Причина расхождения не установлена;
не объявлять это доказанной подменой провайдером.

После pre-change backup `20261016T143042Z-post-egress` только два disabled
MAC-scoped DNS targets Фетхие изменены с `1.1.1.1` на `9.9.9.9`.
Exact export diff, read-back protocol/MAC/ports/disabled и новый RED/GREEN
test проверены. Router-wide DNS/DHCP и текущий DNS MacBook не менялись.
Проверка TCP/UDP redirect и TLS на самом MacBook через Remote еще требуется.
Метод reference: [официальный DoH API Cloudflare](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/).

## Мониторинг И Хранение

Private evidence: `.local/backups/site-to-site/20261016T134255Z-egress-local/`.
История preflight остается отдельным датированным evidence; новые live stages
не используют старые mutators. Новые snapshots и writer сохраняются в private
store вместе с exact read-back. Initial Фетхие не меняется.

Отдельные runtime/BTH/monitoring проверки и protected legacy snapshot
не требуют переподписания старых contracts. Новых server console controls,
lock paths или переключаемых server tables не добавлено; не ослаблять sandbox.
WG monitoring не измеряет IPIP/удаленный Internet. При закрытии подшага
сверяются два fresh valid upstream cycles, console namespace/HTTP и
Prometheus/Grafana coverage; post-backup и результаты закрытия указаны ниже.

Post-backups: TimeWeb `2026-10-16T142629Z_current-config` VERIFIED,
386 host files / 61 offline restore checks, SHA-256
`5bf5a16f290754966826ff152468dcd1b771f3bd98099599675aadf8b7cb6719`;
Фетхие `20261016T143653Z-post-egress`, Нахимова `20261016T143155Z`,
оба VERIFIED_TRANSFER. Fethiye current синхронизирован с последним снимком,
initial сохранен. VERIFIED_TRANSFER не является выполненным restore drill.

Закрытие Local-подшага 14:43:52 UTC: runtime/BTH/monitoring/pilot contracts
PASS, protected legacy snapshot без изменений; policy generation не
переподписывалась. В mount namespace консоли все три прежних fleet routes
ready; HTTP `/state` и доступность controls PASS, sandbox/locks не менялись.
Prometheus: оба S2S peers fresh/present/rate-valid, оба upstreams fresh и все
четыре probe-valid = 1. Два dashboard resources и новые подписи проверены
в persisted Grafana storage read-only; authenticated UI render не проверен.

После последней DNS preset правки дополнительно проверены сохраненные
Prometheus samples: boundary после post-backup 14:36:53 UTC, два различных
valid collector cycles обоих upstreams 14:38:09 и 14:40:09 UTC; последний
sample также valid. Более ранние 14:24/14:26 samples сохранены как история,
но не подменяют эту post-final-config проверку.

351 тест PASS, из них 30 egress tests; repository validation PASS:
410 public files / 67 profiles / 22 devices. Private store VERIFIED:
923 files / 302 records. Сводный WG count в каталоге исправлен на 38 по
фактическим строкам: 38 WG + 11 AWG31 + 9 SOCKS + 9 XRAY = 67.
65 нецелевых профилей сохранены побайтно; два S2S profiles меняют только
AllowedIPs. Git diff check и public staging dry-run PASS, private files
не попадают в публикацию. Commit/push не выполнялись.

## Границы Следующего Шага

Local HTTPS принят пользователем. Перед Remote сохранить предупреждение о
внешних пробах, квалифицировать DNS/HTTPS и объявить краткий тест переключения
только MacBook с точным возвратом Local. Успех DNS lookup не доказывает TLS,
egress IP или отсутствие потерь. Обратный egress, резервирование,
reboot и restore остаются последующими этапами.
