# PLAN: Длительная Проверка SSTP Direct

**Создан:** 2026-10-19. **Статус:** Done.
**Разрешение:** пользователь поручил самостоятельную длительную проверку,
не меняя рабочий канал TimeWeb. Повторного участия владельца не требуется.

## Контекст И Цель

[Короткий тест](../history/2026-10-19-sstp-direct-trial.md) подтвердил mutual
TLS, HTTP200 и recovery, но не длительную стабильность. Пробы interval200ms
имели тайм-ауты; ordinary1s прошли10/10 с RTT до294ms. Новая независимая
проверка сохраняет старые результаты и заранее задаёт interval1s.

Цель: 1800 секунд непрерывного наблюдения одного прямого SSTP соединения,
не менее61 двусторонней серии ICMP, HTTP каждые5s, DF1400 каждые5min.
Далее три намеренных переподключения и отдельный negative CA/recovery.
Router-level transport test не является клиентской/эксплуатационной приёмкой.

## Изоляция И Откат

- Fresh strict SSH identities/serials, master/export и TimeWeb/contracts check.
- Новые verified encrypted backups обоих роутеров, отдельные TLS/PPP credentials.
- Только namespace `s2s-sstp-soak-20261019`, interfaces `sstp-soak-out/in`,
  свободная тестовая PPP пара `.64.2/.64.1`. Старые scope не запускаются.
- На Фетхие используется уже owner-created TCP443 -> `.68.117:5443`.
  Deco не менять. При другом назначении остановиться, не переносить сервисы.
- TLS1.2/AES256-GCM/PFS required, server CA/IP SAN и client certificate checks.
  CA private key только локально. PPP strong secret, клиент без default route.
- Тестовый forward полностью запрещён; input только точная ICMP пара и
  HTTP80 request/established response. После handshake outer listener сужается
  до authenticated caller IPv4; при смене адреса не расширять автоматически.
- Safe Mode на обоих без takeover. Только локальный hard watchdog45min вместо
  прежнего5min; RouterOS settings/device-mode/scheduler не меняются.
  Проверять свежий `<SAFE>` prompt, живую SSH-сессию и лимит<80 write commands
  на площадку. На выходе Ctrl+D undo, затем exact fingerprints/files cleanup.
- Никаких изменений TimeWeb config/peers/routes/firewall/services/contracts,
  publish/re-sign/restart, пользовательских режимов, NAT/DNS/default/LAN/Wi-Fi.
- Все imports/files/global SSTP settings сравнить с исходными; unknown drift
  не перезаписывать. Любой исход заканчивается удалением теста.

## Измерения И Критерии

Окно начинается после HTTP200 и сужения source allowlist. Серии каждые30s,
по5 ICMP с interval1s в каждую сторону. Размер56; DF1400 в начале, каждые5min
и в конце. Сохранять каждый результат и RTT; size означает полный IP packet.

Каждая серия: typed running/uptime/encoding/MTU, HTTP status/code и
done-tests/failed-tests, CPU и tunnel counters. HTTP counter должен расти,
не быть stale, HTTP200/up; минимум300 запросов за окно, 0 failed в soak phase.
Намеренный negative/reconnect идёт отдельной фазой, не портит soak counters.

Отдельно учитывать неожиданные down/reconnect: uptime не должен сбрасываться,
финальные own logs просматриваются на disconnect. Отказ дольше90s или потеря
guard прекращает окно; краткие сбои не скрывать повторным чистым прогоном.
Все обычные ICMP/DF должны ответить для строгой приёмки; пограничные случаи
сохранять как ограничения, не менять пороги по результату.

После окна: три disable/enable только нового клиента, каждый раз требовать
SSTP running/AES256-GCM, HTTP200 и ICMP обе стороны. Затем временно снять
trusted только с нового CA клиента, требовать явный certificate rejection,
вернуть trust и проверить восстановление. Никаких reboot/WAN outage tests.

## Список Задач

| # | Задача | Приоритет | Статус | Завершение |
| --- | --- | --- | --- | --- |
| 1 | Проверка кода наблюдений/guard и fresh read-only preflight | P0 | Done: identities/masters/contracts PASS; 33 focused и509 full tests | 2026-10-19 |
| 2 | Verified backups, отдельные credentials, guarded stage | P0 | Done: оба encrypted backups verified, mutual TLS/HTTP connected, source allowlist narrowed | 2026-10-19 |
| 3 | Полное30min окно с HTTP/ICMP/DF/uptime evidence | P0 | Done: 61 samples,305/305 small и35/35 DF на площадку, zero issues | 2026-10-19 |
| 4 | Три reconnect и negative TLS/recovery | P0 | Done: три positive, explicit CA rejection и full recovery PASS | 2026-10-19 |
| 5 | Exact undo и проверка старого TimeWeb/LAN/profiles/contracts | P0 | Done: exact exports/certificates/server; old paths5/5; TimeWeb/profiles/contracts unchanged | 2026-10-19 |
| 6 | Два fresh collector cycles, Prom/Grafana, tests/store/repo и отчёт | P1 | Done: 2 cycles/Prom/Grafana/contracts PASS;509 tests; repo PASSED; store2161/336 VERIFIED | 2026-10-19 |

Постоянные inventories/fleet/console не меняются: кандидат временный и будет
удалён. Для неизменённых BTH/monitoring/runtime contracts сохраняется no-change
evidence, их generations не пересоздаются. Расписание проверок Нахимова остаётся
на паузе. Открытых вопросов к пользователю нет.

Источники: [Ping](https://manual.mikrotik.com/docs/diagnostics-monitoring-and-troubleshooting/ping/),
[Netwatch](https://manual.mikrotik.com/docs/diagnostics-monitoring-and-troubleshooting/netwatch/),
[Safe Mode](https://help.mikrotik.com/docs/spaces/ROS/pages/328155/Configuration+Management).

## Лог Подготовки

При первом collection tests выявлен import-mode mismatch: соседние модули
не добавляются pytest в sys.path автоматически. Используется принятый в этом
каталоге explicit importlib/file pattern, без изменения глобального PYTHONPATH.
Live конфигурация на этом этапе не менялась.

## Итог

Окно1820.85s,61 samples,305/305 ICMP и35/35 DF1400 на площадку;
364 HTTP checks без failed, код200 во всех snapshots. Session/uptime непрерывны.
Три reconnect и explicit negative CA/recovery PASS. Все trial objects удалены,
exports/certificates/server exact, TimeWeb и67 profiles неизменны. Постоянный
SSTP не установлен. [Подробный отчёт](../history/2026-10-19-sstp-direct-soak.md).
