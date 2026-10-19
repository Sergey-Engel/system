# Единое Управление Маршрутами Устройств

Дата: 2026-10-19. Release: controller/UI 3.0.0.
Статус: локальная facade установлена; controller/UI 3.0.0. Транспорт и
исходные клиентские назначения не менялись.

## Контракт И Границы

Пользователь согласовал один экран вместо независимых списков Direct/Split.
Нахимова: enabled permanent DHCP reservations `defconf`, включая offline.
Standard / Split Cenuta / Split Fornex / Direct SSTP via Fethiye — один режим
на устройство. Фетхие: только фактические авторизованные Wi-Fi registration
MikroTik; Standard / Direct SSTP via Nakhimova. Ethernet, Deco и просто
существующие DHCP leases не являются основанием включать клиента Фетхие в UI.
Ассоциированный Wi-Fi-клиент без однозначной DHCP-привязки видим read-only.

Имя берётся только по точному MAC из справочника. В основную строку входят
имя и IP, MAC доступен как подсказка. Нет OUI/hostname inference. Одна Apply
меняет только выбранное устройство. Выбор в меню сам по себе не пишет роутер.
Ручное обновление, сообщения до закрытия, без auto-poll.

## Исходные Имена Нахимова

Источник — live read-only комментарии семи enabled static DHCP reservations,
не определение модели по производителю и не утверждение владельца.
Зафиксированы exact MAC/IP/label; labels перенесены в presentation dictionary.

| MAC | IP | Existing Reservation Label | Initial Mode |
| --- | --- | --- | --- |
| 80:EA:96:E7:DF:FF | 192.168.88.210 | SEAP Server | Standard |
| C4:F7:C1:13:E4:BC | 192.168.88.11 | Apple TV Gostinaa | Split Cenuta |
| 00:D8:61:3A:23:BC | 192.168.88.252 | DigitalRazor PC | Split Cenuta |
| 54:BD:79:53:0C:AE | 192.168.88.207 | Samsung TV | Standard |
| 50:DE:06:8F:B7:A7 | 192.168.88.28 | AppleTV Spalna | Split Cenuta |
| 00:11:32:5D:AA:19 | 192.168.88.206 | Synology DS416 | Standard |
| D0:11:E5:CD:1F:51 | 192.168.88.35 | Mac Mini M4 (Sergey) en0 | Split Cenuta |

Фетхие при preflight: только A2:C1:5E:29:F5:8E /192.168.89.197,
MacBook Air (Sergey), Standard. DHCP .196 не зарегистрирован в Wi-Fi и
исключён. Dynamic reservations Нахимова также исключены. Состав Wi-Fi может
изменяться; это не постоянный список всех когда-либо подключавшихся клиентов.

## Безопасность Записи

Контроллер проверяет strict SSH identity/serial, baseline, MAC/IP/lease ID,
актуальную eligibility и revision. Общий flock с Direct. Legacy HTTP writers
возвращают 410 после включения unified flag; CLI Direct writer также закрыт.
Меняются только exact host memberships `CENUTA_Devices` / `VPN_Devices` и
существующие per-device Direct controls. Смена Cenuta/Fornex использует одну
запись set для одного существующего host. Direct снимается до Split; Split
снимается до Direct. Очищаются только tracked flows выбранного IP.

Durable intent сохраняется до первой записи. Unknown acknowledgement не
повторяет запись: pending и явное восстановление того же MAC/IP/lease в
Standard. Reviewed baseline adoption допускает только исходные/запланированные
host memberships; чужой diff, соседнее устройство, shared CIDR/dynamic entries
не принимаются автоматически. Транспорт, ключи, сертификаты, глобальные
mangle/RU/local/BitTorrent исключения, TimeWeb selector и службы не меняются.
Назначения вне eligibility остаются нетронутыми и показываются счётчиком.

## Доказательства

Fresh preflight и encrypted backups обоих MikroTik:
`.local/backups/site-to-site/20261019T152132Z-unified-routing/`.
Чувствительные exports и binary backup secrets только в private store;
исходные local config/state и code snapshots сохранены там же.
Физические клиенты не переключаются для проверки интерфейса. Тесты writer
выполняются на детерминированных router fixtures; readiness не означает
принятую проверку HTTPS/DNS конкретного клиента или reboot recovery.

Связанные документы: [план](../tasks/PLAN-unified-device-routing.md),
[эксплуатация](../operations/Direct_SSTP.md),
[справочник](../../config/inventory/lan-devices.json).

## Результаты

- 610 tests passed; durable JUnit и вывод в preflight-каталоге `tests.xml`,
  `tests-output.txt`. Все 16 переходов между четырьмя режимами Нахимова,
  Wi-Fi-only Фетхие, offline static, stale binding/revision, конфликт и
  прерванные записи/recovery проверены на fixtures с настоящим strict inspector.
- Browser desktop1280x1000 / mobile390x844: семь строк Нахимова, четыре режима;
  Фетхие — только actual Wi-Fi, два режима. Нет горизонтального overflow и JS
  ошибок. Имя не интерпретируется как HTML, Apply явная, ошибок по таймеру
  не скрывает. VPN main сохранён; реальных POST assignment в live proof нет.
- В live Фетхие снова появился 52:EB:3F:26:E9:5A /.196, поэтому видны два
  Wi-Fi-клиента. Без dictionary binding он отображается `Unknown device`,
  не угадывается по private MAC. Это ожидаемое изменение ассоциации, не
  новая статическая запись/новый профиль VPN.
- Fresh encrypted post backups обоих MikroTik в
  `.local/backups/site-to-site/20261019T154007Z-unified-routing-post/`:
  VERIFIED_TRANSFER, двойное чтение binary, SHA и unchanged export.
  Полные sensitive exports совпадают с preflight и current private masters;
  Split memberships и оба Direct state файла побайтно/структурно сохранены.
  Restore/reboot drill не проводился.
- Прежние Direct HTTP writers возвращают410; unified intent generation0,
  pending null. Release source hashes сохранены в `release-sources.json`.
  Перезапускалась только локальная facade `com.sergey.sstp-panel`, не SSH
  forward и не TimeWeb. Пользовательская вкладка не перезагружалась агентом.
- Два новых валидных collector cycles после deployment для Cenuta/Fornex;
  Prometheus freshness/probe validity/cardinality и Grafana health проверены.
  Первый заключительный runtime-contract check завершился ошибкой; точная
  причина не установлена, сохранён `host-error.txt`. Отдельный повторный
  read-only check runtime/BTH/monitoring — все PASS, подробности private
  `contract-diagnostics.json`. Никакие policy/manifest не переподписывались,
  службы TimeWeb не перезапускались. Ошибка первого замера не скрывается.
- Финальный `observability.json` подтверждает unchanged TimeWeb persistent,
  runtime и interface identity, все67 VPN profile bytes, два сохранённых
  возрастающих цикла и актуальный Prometheus. Baseline update not required.
  Repository validation PASS:67 profiles/22 devices, без проблем;
  private-store verification и `git diff --check` пройдены.

Readiness UI — проверка конфигурации/маршрута, не новая клиентская приёмка
HTTPS/DNS. Новые реальные маршруты клиентов в этой задаче не испытывались:
сохранено разрешённое исходное состояние. Часовые проверки остаются на паузе.
