# Прямой SSTP Через Deco: Ограниченный Тест

**Дата:** 19 октября 2026. **Итог:** прямой SSTP с проверкой сертификатов,
HTTP и переподключением подтверждён на уровне роутеров. Постоянный канал
не установлен; строгая приёмка всех быстрых ICMP-проб не пройдена.
TimeWeb и пользовательские маршруты не менялись.

## Подтверждено

Владелец сохранил на Deco `SSTP-Direct`, TCP443 -> `192.168.68.117:5443`.
Список правил показывает `.117:443`, но входящие SYN фактически приходят
на5443. Исправлять правило по одной строке списка не потребовалось.
Старый UDP51972 и DHCP reservation не изменялись.

```text
Нахимова, SSTP client -> Internet TCP443 -> Deco -> Фетхие, SSTP server5443
Только тестовые адреса: 10.60.64.2 <-> 10.60.64.1
Пользовательский forward через тестовые interfaces запрещён
```

- Strict SSH: Нахимова `HKM0BDXYG74`, ROS7.24.4;
  Фетхие `HM20B6QXS8H`, ROS7.19.6. WAN/MAC/reservation и exports сверены.
- TLS1.2, AES256-GCM, PFS required; проверка server CA/IP SAN и client
  certificate включены. Fresh RSA2048/SHA256 certificates с отдельными
  server/client EKU. CA private key оставался только локально, P12 с закрытыми
  ключами зашифрованы; сильный отдельный PPP secret, MSCHAPv2 внутри TLS.
- Фактический authenticated caller Нахимова `5.18.143.112`, endpoint Фетхие
  `194.61.140.217`. Это прямой transport, не SSTP listener на TimeWeb.
- HTTP через SSTP к тестовому адресу Фетхие: код200, explicit positive
  observation F: 6 проверок, 0 failed. Разрешены только точный HTTP request
  и established response между двумя тестовыми IP; другие input/forward закрыты.
- При снятии trusted только с нового CA на Нахимова SSTP не подключался:
  журнал `ssl: no trusted CA certificate found (6)`. После возврата trust
  соединение восстановилось, ICMP recovery 5/5 в обе стороны.

## ICMP И Размер Пакета

| Scope / проба | Нахимова -> Фетхие | Фетхие -> Нахимова |
| --- | --- | --- |
| E: шесть серий, interval200ms, размер56 | 28/30 | 28/30 |
| E: дополнительный DF1400, interval200ms | 5/5 | 5/5 |
| F: шесть серий, interval200ms, размер56 | 27/30 | 26/30 |
| F: DF1400, interval200ms | 5/5 | 3/5 |
| F: отдельный interval1s, размер56 | 10/10 | 10/10 |
| F: после восстановления доверия, размер56 | 5/5 | 5/5 |

Во всех двенадцати основных положительных сериях SSTP оставался running.
Здесь не воспроизведён прежний WG-сценарий полного прекращения доставки.
При ordinary interval1s средний RTT около141/149ms, максимальный233/294ms;
CPU после каждой такой серии0% на обоих роутерах, не peak CPU measurement.

В RouterOS ответ позже `interval` считается timeout. Поэтому timeout при200ms
не равнозначен доказанной потере пакета во внешнем тракте; RTT >200ms реально
наблюдался в независимой серии. Все быстрые результаты сохранены, не отброшены.
Нельзя утверждать, что **каждый** прежний timeout объяснён задержкой: для этого
нет сопоставленной трассы каждого пакета. Строгий zero-timeout gate200ms не
пройден, итог F `SSTP_PARTIAL_ACCEPTANCE`, не production qualification.

Пакет IP-размера1400 с DF проходил без фрагментации. Повторный DF1400 с обычным
interval1s, длительный soak, throughput, клиентский egress и отказ WAN ещё
не приняты. Нельзя переносить router-level HTTP на приложения MacBook.

## Подготовительные Остановки

Все ошибки сохранены, не представлены как успешные испытания транспорта.

| Scope | Причина / результат |
| --- | --- |
| A | Import успешен, но `print as-value` не содержит calculated fingerprint. Исправлено на explicit typed get; 5 новых regression cases |
| B | ROS7.24.4 отвергает `use-vj-compression`; первый PPP profile не создан. Однокомандная Safe Mode проба подтвердила ответ, устаревший параметр удалён |
| C | Mutual TLS подключён, HTTP tester остановлен на старом `http-code-min`; актуальный параметр `http-codes` |
| D | Закрыт до изменения конфигурации: static review добавил узкий established HTTP response accept перед новым input-deny |
| E | HTTP/MTU/ICMP проверены; строгие быстрые ICMP-пробы остановили тест до negative TLS |
| F | Отдельно завершены TLS negative/recovery и ordinary interval1s; прежние timeouts не отменены |

Один read-only runtime check в завершении B временно вернул ошибку; повторный
прямой check и затем полная проверка contracts прошли. Контракты и TimeWeb
не исправлялись/не переподписывались; точная причина этого разового ответа
не установлена.

## Откат И Хранение

Каждый live scope: Safe Mode на обоих роутерах, без takeover, timer300s,
менее100 операций. Ctrl+D undo и дополнительный exact cleanup импортированных
certificates/files по новым fingerprints и совпадающим bytes. Все scope закрыты.
После F exports, certificates/trust и прежние global SSTP server settings
точно совпали с baseline. Hub и remote LAN gateway по5/5 с обеих площадок.
TimeWeb config/runtime/interface identity и все67 client profile hashes прежние;
runtime recovery, BTH и monitoring contracts PASS.

Fresh encrypted binary backups для каждой подготовки скачаны дважды,
VERIFIED_TRANSFER; exports до/после backup совпали. Live restore drill не делался.
Canonical current/initial masters не заменялись временными trial snapshots.
Private evidence, ключи/пароли и фотографии сохранены в portable private store
с ограниченными правами файлов, не в публичной документации.

Папки под `.local/backups/site-to-site/`:

- A `20261019T073827Z-forward`; B `20261019T074810Z-forward`.
- Однокомандная проба `20261019T075505Z-sstp-profile-probe`.
- C `20261019T075630Z-forward`; не запущенный D `20261019T080123Z-forward`.
- E `20261019T080444Z-forward`; F `20261019T080957Z-forward`.

Объекты временные, поэтому активные fleet/tunnel/client inventories не
пополнялись. Панель не публиковалась, MacBook не переключался, автоматические
проверки Нахимова остаются на паузе. Deco в этой работе агент не изменял.

## Финальные Проверки

Pure SSTP tests18 PASS, полный suite494 PASS. Два новых валидных collector
cycles обоих upstream: PASS. Prometheus4/4 valid,2/2 fresh, оба timestamps
свежие. Grafana database health OK; это не приёмка нового SSTP dashboard.
Runtime recovery/BTH/monitoring contracts PASS. Repository validation PASSED:
437 public files,67 profiles,22 devices, `problems=[]`. Private store VERIFIED:
1908 files,334 records. `git diff --check` чистый; staging dry-run не включает
private paths. Commit/push/deployment не выполнялись.

## Следующая Граница

Для постоянного SSTP нужен отдельный changeset: lifecycle сертификатов,
управление direct endpoint/source changes, долговременный мониторинг,
восстановление после перезапуска, изолированные policy routes и реальная
клиентская приёмка. При этом рабочий путь TimeWeb остаётся неизменным.
Успешный короткий тест не заменяет эту эксплуатационную интеграцию.

План: [SSTP trial](../tasks/PLAN-sstp-direct-trial.md).
Первичные источники:
[SSTP](https://help.mikrotik.com/docs/spaces/ROS/pages/2031645/SSTP),
[актуальный Netwatch](https://manual.mikrotik.com/docs/diagnostics-monitoring-and-troubleshooting/netwatch/),
[семантика Ping interval](https://manual.mikrotik.com/changelog/changelog-2026-09-30/).
