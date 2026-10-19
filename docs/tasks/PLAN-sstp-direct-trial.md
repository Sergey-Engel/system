# PLAN: Изолированный SSTP/TCP Direct

**Дата:** 2026-10-19. **Разрешение:** выбран SSTP, самостоятельные проверки;
рабочий TimeWeb не менять. Постоянная интеграция/переключение клиентов не входят
в этот ограниченный транспортный тест.

## Deco И Схема

Владелец прислал форму TCP443 -> `192.168.68.117:5443` и сохранённый список
`SSTP-Direct`, где показано `.117:443`. Список может показывать внешний порт;
фактическое назначение проверяется по входящим SYN, не считается доказанным
только по строке списка. Старый UDP51972/резервирование остаются как есть.

```text
Нахимова, клиент -> Internet TCP443 -> Deco -> Фетхие, SSTP server
Тестовая PPP пара: Нахимова 10.60.64.2 <-> Фетхие 10.60.64.1
Существующие WG/TimeWeb/LAN/egress и режимы устройств неизменны
```

## Границы И Откат

- Fresh identities/masters/namespace/contracts, новые verified encrypted backups.
- Новый owner `s2s-sstp-trial-20261019`, отдельные PPP profiles/secret/interfaces,
  адреса только после проверки свободного диапазона, никаких default/LAN routes.
- TLS1.2, RSA/SHA256 certificates, проверка server CA/address и client certificate.
  Временный CA и leaf certificates генерируются локально, CA private key не
  загружается в роутеры. PPP password и encrypted import passwords только private.
- Сервер Фетхие до начала должен быть выключен, PPP AAA без внешнего RADIUS,
  не должно быть других разрешённых SSTP/any secrets. Старый global server
  snapshot полностью восстанавливается. Другие PPP profiles не меняются.
- Сначала listener5443; если фактический forward ведёт на443, допускается
  использовать443 только после live-проверки отсутствия другого enabled listener.
  WebFig/www-ssl/SSH не включать и не переносить.
- Наружу открыт только SSTP TLS listener, не management. Первоначально TLS
  требует client certificate + сильный PPP secret; после аутентификации
  source allowlist сужается до фактического caller-id Нахимова.
- Forward через тестовые interfaces запрещён, input только точная ICMP пара
  и HTTP80 с Нахимова к тестовому адресу Фетхие для прикладной пробы.
- Safe Mode на обоих, без takeover, 300 s, менее100 операций. Ctrl+D undo.
  Certificate/file import может потребовать явного cleanup: удалять только
  точные новые fingerprints и точные загруженные filenames. Сверить прежние
  certificates/trust, server settings и exports, не полагаться только на Safe Mode.
- Никакого изменения device-mode, scheduler, fetch, sniffer, NAT/default/DNS,
  TimeWeb config/peers/services/contracts. Не publish/re-sign/restart.
- При любом исходе эксперимент удаляется; постоянный SSTP требует отдельного
  эксплуатационного changeset с мониторингом и восстановлением.

## Приёмка И Шаги

| # | Шаг | Статус |
| --- | --- | --- |
| 1 | Fresh read-only preflight и pure builder tests | Done: identities/masters/contracts PASS; 18 tests PASS; другие listeners не занимают443/5443 |
| 2 | Verified backups, private TLS/PPP bundle | Done: fresh encrypted backups всех подготовок verified; CA key только локально |
| 3 | Подтверждённый TCP forward и SSTP с проверками сертификатов | Done: C/E/F mutual TLS connected; входящие SYN на5443, адаптация не понадобилась |
| 4 | Устойчивый ICMP, DF1400, HTTP, reconnect и fail-closed TLS control | Завершено с ограничениями: HTTP200, ordinary1s 10/10 оба, negative CA/recovery PASS; zero-timeout200ms НЕ пройден |
| 5 | Undo, certificates/files/server/exports exact, TimeWeb/LAN/contracts | Done: все scopes CLOSED; exact baseline, hub/LAN5/5 оба, contracts PASS |
| 6 | Два fresh collector cycles, repository/store verification и отчёт | Done: 2 cycles/Prometheus/Grafana PASS, 494 tests, repository PASSED, private store VERIFIED |

ICMP: не менее шести двусторонних серий без потерь в ограниченном окне.
HTTP: отдельный Netwatch http-get, без scripts, только тестовый адрес/порт80;
это router-level application test, не приёмка клиентских приложений.
Реконнект: отключить/включить только новый client. Отрицательный TLS контроль:
временно снять trusted только с собственного CA на клиенте, переподключить,
потребовать отказ, затем восстановить trust и проверить восстановление.

### Формат Certificate Evidence

Попытка A остановлена до запуска SSTP: `certificate print as-value` не содержит
вычисляемый `fingerprint` даже для корректно импортированного сертификата.
Отпечаток и boolean trust читать отдельными typed `get`, не считать отсутствие
поля признаком unsigned certificate. Добавлены regression tests для пропущенного
поля, невалидных/дублированных отпечатков и нетипизированного trust. A закрыт:
imports/files удалены по точным fingerprints/bytes, exports/certificates/server
совпадают с baseline; hub и remote LAN 5/5 на обоих, contracts PASS.

Попытка B остановлена на первом PPP profile: ROS7.24.4 возвращает
`bad parameter use-vj-compression`. Этот устаревший параметр удалён, TLS
проверки не ослаблялись. Отдельная однокомандная Safe Mode проба установила
точный ответ и полностью откатилась. B также восстановлен; временный сбой
read-only runtime check при повторе исчез, contracts PASS без изменений.

C установил mutual TLS, SYN подтвердил внутренний5443. Проба HTTP остановлена
на `bad parameter http-code-min`; в актуальном CLI используется `http-codes`.
Frozen Confluence не применять как единственный источник синтаксиса:
[актуальный Netwatch](https://manual.mikrotik.com/docs/diagnostics-monitoring-and-troubleshooting/netwatch/).
C полностью удалён, exports/certificates/server exact, старые ping5/5 и contracts
PASS. Handshake C не считается приёмкой устойчивого канала.

D закрыт до начала изменения конфигурации: дополнительный static review нашёл,
что input-deny на клиенте блокировал бы ответ HTTP раньше старого established
rule. Для E добавлен только exact peer->peer TCP source80 established accept,
вставляемый перед новым deny; forward остаётся запрещён. Regression test
проверяет адреса, порт, established и порядок. Ни D, ни review не меняли трафик.

E: SSTP connected во всех шести сериях; ICMP 28/30 в каждую сторону (4 timeouts
из60), HTTP200 с пятью проверками без отказов, supplemental DF1400 5/5 в обе
стороны. Порог zero-loss не пройден, negative TLS/reconnect не выполнялись:
оператор остановил E до них. F - отдельный ограниченный functional diagnostic:
не прерывает сбор остальных независимых controls при ICMP timeouts, но сохраняет
их в evidence и НЕ считает zero-loss gate пройденным. Успех F не отменяет E и
не означает production qualification. Исходные пороги не ослабляются.

F завершён: six quick rounds27/30 и26/30, DF1400 5/5 и3/5. Independent
ordinary interval1s: 10/10 в обе стороны, RTT max233/294ms; HTTP200 с6 tests,
0 failed. Negative CA дал явный `no trusted CA certificate found`, recovery
5/5 оба. RouterOS считает reply после interval timeout: quick200ms результаты
не доказывают внешнюю потерю; каждый timeout отдельно не объяснён. Постоянный
канал не установлен, long soak/client egress не приняты. Полный
[отчёт](../history/2026-10-19-sstp-direct-trial.md).

Источники: [SSTP](https://help.mikrotik.com/docs/spaces/ROS/pages/2031645/SSTP),
[Certificates](https://help.mikrotik.com/docs/spaces/ROS/pages/2555969/Certificates),
[Netwatch](https://help.mikrotik.com/docs/spaces/ROS/pages/8323208/Netwatch).
