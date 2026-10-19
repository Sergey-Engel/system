---
type: changeset
status: bounded-ipip-outage-verified-with-warning
created: 2026-10-16
updated: 2026-10-17
---

# Выход MacBook Фетхие Через Нахимова

**Текущее состояние:** ограниченная проба Local -> Нахимова -> Local принята
на MacBook Air Sergey: terminal HTTPS показал `5.18.141.112` в Remote и
`194.61.140.217` после возврата, `example.com` в Remote открылся.
Сейчас Local, все 10 Remote controls выключены; прежний IP закреплен
статически. 17 октября принята ограниченная IPv4/HTTPS проверка обрыва IPIP:
проверенный запрос с DNS bypass завершился timeout без местного выхода,
отдельная recovery-проба вернула `5.18.141.112`, финальный Local подтвердил
`194.61.140.217`. Первый recovery gate дал 2/3 LAN ping и containment в Local;
это предупреждение не снято. Постоянный Remote, полный WAN/TimeWeb outage,
IPv6-negative, обратный выход и приложения еще не приняты.
Исторические ICMP-потери Нахимова не отменены.
[Текущий протокол и ограничения](../history/2026-10-17-egress-fail-closed.md),
[пробы 16 октября](../history/2026-10-16-egress-trials.md),
[предыдущий Local-подшаг](../history/2026-10-16-egress-local.md),
[история подготовки](../history/2026-10-16-egress-preparation.md).

## Граница Первого Пилота

Шаг 8 [плана](../tasks/PLAN-fethiye-site-to-site.md): только MacBook Air Sergey,
текущий bound lease `192.168.89.197`, MAC текущего SSID закреплен в changeset.
Пользователь подтвердил, что VPN-приложения выключены. Другие клиенты,
операторский Deco, main defaults и работающая LAN-пара не меняются.
Обратный Internet-выход Нахимова через Фетхие требует отдельного выбранного
клиента; сейчас он не включается.

## Конструкция

Отдельный IPIP внутри существующих WG-плеч: Нахимова outer `.60.2`,
Фетхие outer `.60.3`; inner `10.60.61.1/30` и `.2/30`, interface
`ipip-s2s-egress`, MTU 1400, MSS clamping, keepalive 10 s / 3 attempts.
IPIP сам не шифрует и не аутентифицирует; он доступен только внутри двух
аутентифицированных WG-плеч, по точным outer IP. В WAN его не открывать.
Новые WG-ключи/порты не нужны. Device-mode/fetch/scheduler/sniffer не менять.

Причина: общий host WG с двумя peers не может одновременно направлять один
и тот же default-префикс в разные peers. Добавлять `0.0.0.0/0` обоим нельзя.
Альтернатива: разнести host WG по отдельным интерфейсам, но это затронет уже
принятый LAN-контур. IPIP сохраняет его keys/endpoints/host routes и допускает
позднее независимые policy routes двух площадок без петли.

AllowedIPs каждого роутера расширить только адресом другого outer peer `/32`.
На TimeWeb AllowedIPs/config/routes не менять; в своей nft table добавить
только protocol 4 `.2 -> .3` и `.3 -> .2`, `wg-s2s -> wg-s2s`. Host services
и прочий transit закрыты. Только guard.nft и manifest.json меняются на сервере.

На роутерах input IPIP ограничен ICMP между inner gateway IP, остальное drop.
Forward IPIP допускает только Internet выбранного `.89.197`, valid conntrack;
ответы только established/related. Нахимова не выпускает через этот канал
private/bogon destinations, используется прежний WAN masquerade. Не добавлять
новый широкий NAT, не менять Smart Split/старые mangle или BTH.

## Local И Remote

Начальное состояние Local: IPIP и guards можно проверить, но client lookup,
DNS redirect и kill guards выключены. Проверить без изменения выхода MacBook.

Remote: отдельная Fethiye table `s2s_remote`, default через inner `.61.1`,
blackhole fallback и `lookup-only-in-table` только для `.89.197`. Known LAN
`.68/24`, `.88/24`, `.89/24` остаются через main. Независимый MAC-based WAN
guard запрещает public Internet через ether1 даже при ошибке policy lookup.
IPv6 forwarding и IPv6 DNS к роутеру для этого MAC блокируются только в Remote.
TCP/UDP DNS 53 этого MAC перенаправляются на `9.9.9.9` через remote route;
router DNS и другие клиенты не меняются. DoH/DoT идут как обычный remote IP traffic.
Нет DNS fallback через SkyFiberNet. Выбор DNS фиксируется для пилота, не всей LAN.
Первоначальный disabled preset `1.1.1.1` заменен только в двух выключенных
правилах: на Нахимова ответы для `example.com` и `api.ipify.org` расходились
с TLS reference Cloudflare. Три ответа Quad9 совпали. Это квалификация
preset, не приемка DNS на MacBook и не установленная причина расхождения.

Return на Нахимова: отдельная `s2s_return` содержит только `.89.197/32` через
IPIP и blackhole того же /32. Rule только `interface=ether1` к этому IP,
перед прежним private-main bypass. LAN-initiated трафик `.88/24 -> .89/24`
по-прежнему идет по существующему WG LAN route, не меняется на IPIP.
Перед Remote тестовый lease закрепить статически без смены IP/DNS/gateway.
В первом Local-подшаге lease оставался dynamic; перед Remote он переведен
в static без смены IP/MAC/DNS/gateway. После возврата Local привязка сохранена:
теперь 25 owned-объектов Фетхие и 29 Нахимова. Удаление static lease не
входит в обычное переключение и потребует отдельной процедуры DHCP renew.

Вход в Remote: enable kill guards -> удалить только conntrack выбранного
клиента -> включить DNS и source lookup -> повторно удалить только его
старые соединения. Это может кратко прервать только сессии тестового MacBook.
Новые egress flows принимаются до FastTrack; глобально FastTrack не выключать.
Local: disable lookup/DNS -> очистить только client conntrack -> снять guards
последними. Частичное переключение не должно открывать незаявленный local fallback.
Для проб используется новый guarded writer с ровно 10 закрепленными object IDs,
проверкой exact export delta и typed flags, а не повторный запуск Local deployment.
Проба ограничена 420 секундами: процесс на компьютере агента возвращает Local
при истечении окна. RouterOS scheduler/device-mode для этого не менялись.
Это ограничитель испытания, не автономное резервирование сети.

### Испытание Обрыва 17 Октября

Одобрено пользователем «начинай» для того же MacBook. До записи: свежие
verified backups, strict serial/SSH, exact current/master/store и bound static
lease. Local baseline сегодня: пользовательский terminal HTTPS `194.61.140.217`.

Последовательность физической приемки: Local -> Remote (положительный HTTPS
контроль) -> отключить только Fethiye `ipip-s2s-egress` -> ожидать HTTPS timeout
без local fallback -> включить IPIP -> подтвердить Remote HTTPS -> Local и
контрольный HTTPS. Для outage-запроса используется тот же заранее проверенный
public IP сервиса api.ipify.org через `curl --resolve`: отсутствие DNS не
должно быть единственной причиной отрицательного результата.

Все 10 Remote controls остаются включенными во время обрыва. Проверяются
inactive remote gateway, active blackhole и продолжающая работать LAN-пара;
другие WG/ethernet/Wi-Fi/Deco не отключаются. Трафик/conntrack очищается только
для `.89.197`. Один процесс на компьютере агента владеет всеми изменениями:
outage максимум 180 s, общий drill максимум 900 s; при timeout восстанавливает
IPIP и Local. Это не router-side failover. Повторный тест требует нового
baseline, старые sealed пробы не перезапускаются.

RouterOS 7.19.6 возвращает JSON `null` для `get active` невыбранного route,
хотя `/routing route` показывает `contribution=best-candidate`. Это не boolean
`false` и не самостоятельное доказательство выбора. Проверять положительный
набор `/routing route print ... where active=yes` и точный ожидаемый ID:
ровно gateway при поднятом IPIP, ровно blackhole при отключенном. Сверять
`contribution` выбранного route и весь scoped набор; `null` не приводить к False.
Источники: [routing route properties](https://help.mikrotik.com/docs/spaces/ROS/pages/59965493/routing%2Broute).

## Gates И Откат

До записи: fresh backups, exact current/master/store, serial и strict trust,
свободный inner /30, interface/table/chain names, current bound MAC/IP,
static anchors, исходные AllowedIPs и protected snapshots. RouterOS 7.19
не выводит часть flags в as-value: missing требует explicit get, не default False.
`find` возвращает массив ID: не сравнивать его текст с одним `.id`.
Признак dynamic получать явно через `get`, сериализовать как JSON boolean,
проверять вместе с точными MAC/IP и bound. Одинаковый defconf comment встречается
в IPv6 input и forward: anchor выбирать одновременно по chain и comment,
DNS input guard размещать до input established, не до forward established.
Числовые JSON ports могут сериализоваться как `53.000000`: сравнивать
числовое значение с 53, а не строку `str(value)` с `"53"`. Read-back mismatch
не исправлять повторным выполнением add/set команд. В quoted RouterOS regex
символ конца строки передается как `\$`, иначе CLI трактует его как начало
переменной. Исправление проверено read-only отбором и затем реальным
переключением; обход широким conntrack flush запрещен.

Порядок: pure RED/GREEN checks и isolated nft dry-run -> staged disabled IPIP
с guards и выключенным Remote -> scoped host nft -> enable только IPIP ->
inner gateway ping в обе стороны, counters и прежние LAN/Internet checks.
Baseline public IP MacBook запрошен отдельно. Без него Remote не активировать.
Baseline уже получен. Пройденные IPIP/LAN gates не отменяют отдельный
Internet gate: внешние потери не скрывать успешным повтором короткого ping.
Обе площадки запрещают `/tool fetch` в device-mode. Ограничение не менять;
WG endpoint observation на TimeWeb не выдавать за проверенный HTTPS egress IP.

После разрешенного переключения: public IP должен совпасть с прямым выходом
Нахимова, DNS/HTTPS и приложение проверить на MacBook. Fail-closed испытать
отключением только IPIP пилота в объявленное окно, затем восстановить и проверить.
Наличие WG handshake не является приемкой IPIP/Internet. Обратный egress,
автоматическое резервирование, reboot и restore остаются отдельными этапами.

Откат: вернуть Local с guards последними, после exact ownership проверки
удалить только marker `s2s-egress-20261016`, вернуть два прежних AllowedIPs,
guard.nft/manifest в исходный вид. Возврат static lease в dynamic является
отдельным teardown-подшагом, не обычным Local. Старые WG identities,
LAN routes и широкие firewall/conntrack tables не трогать. Unknown drift
останавливает автоматический rollback, его не переподписывать.

Профили остаются 67 / устройства 22; два S2S профиля меняют только AllowedIPs.
UI/метрики показывают WG transport, не подтверждают здоровье egress. Требуются
separate runtime/BTH/monitoring checks, console namespace/HTTP, два fresh valid
collector cycles, Prometheus/Grafana coverage и post-backups. Current snapshot
должен явно указывать Local или Remote, не приписывать клиентскую приемку.

Источники: [IPIP](https://help.mikrotik.com/docs/spaces/ROS/pages/47579173/IPIP),
[policy routing](https://help.mikrotik.com/docs/spaces/ROS/pages/59965508/Policy+Routing),
[routing rule](https://help.mikrotik.com/docs/spaces/ROS/pages/331612232/routing+rule),
[RouterOS string escapes](https://help.mikrotik.com/docs/spaces/ROS/pages/47579229/Scripting),
[Quad9 addresses](https://quad9.net/service/service-addresses-and-features/),
[Cloudflare TLS DNS reference](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/).
