# Длительная Проверка SSTP Direct

**Дата:** 19 октября 2026. **Статус:** Done. Transport test, exact undo и
финальные monitoring/store/repository gates PASS.
**Поручение:** длительная автономная проверка без изменений рабочего TimeWeb.

## Объём

Новый изолированный namespace `s2s-sstp-soak-20261019`, отдельные credentials
и fresh encrypted backups обоих роутеров. Нахимова SSTP client -> Internet
TCP443 -> уже сохранённый Deco forward -> Фетхие SSTP server5443.
Только PPP `.64.2/.64.1`, без default/LAN routes и клиентского forward.
TLS1.2/AES256-GCM/PFS required, server CA/IP SAN и client certificate checks.
Outer allowlist сужен до authenticated caller перед началом окна.

Плановое окно1800s,61 двусторонняя серия по5 ICMP interval1s, семь серий
DF1400, HTTP каждые5s. До начала зафиксированы критерии и отдельные фазы
reconnect/negative CA; см. [план](../tasks/PLAN-sstp-direct-soak.md).
Результаты [коротких проб](2026-10-19-sstp-direct-trial.md) не отменяются.

## Подготовка И Начало

- Fresh pinned SSH/serial: Нахимова `HKM0BDXYG74`, ROS7.24.4;
  Фетхие `HM20B6QXS8H`, ROS7.19.6. Masters/exports/contracts PASS.
- Focused tests33 PASS, полный suite509 PASS.
- Оба новых encrypted binary backups VERIFIED_TRANSFER; двойное скачивание
  совпало, exports до/после backup неизменны. Restore drill не выполнялся.
- Начало soak: `2026-10-19T09:06:12.807771Z` (12:06:12 Europe/Istanbul).
  Private evidence `.local/backups/site-to-site/20261019T090323Z-forward/`.
- Safe Mode без takeover на обоих, local watchdog2700s, fresh SAFE prompt
  проверяется постоянно, лимит<80 write commands. Scheduler/device-mode
  не изменяются; по окончании требуется exact undo, не commit.
- Первые ICMP/DF серии проходят, HTTP200 и растущий done-tests без failed.
  При2min наблюдался RTT383ms; это observation, не итог всего окна.
- Midpoint read-only check `2026-10-19T09:21:44.339286Z`: TimeWeb config,
  WG runtime и interface identity совпали с before snapshot; ничего не менялось.
- Промежуточные structured snapshots отдельно сохранены после9 и20min;
  данные не заменяют финальный полный result и restoration receipts.

## Результат Окна

`SSTP_30MIN_ROUTER_SOAK_PASS`. Начало09:06:12.807771Z, конец09:36:33.678176Z
(12:06:12-12:36:33 Europe/Istanbul), фактически1820.85s. Все61 наблюдения
running, идентификатор PPP session один и тот же, uptime непрерывно растёт.
Own logs до намеренных controls не содержат новых disconnect events.

| Измерение | Нахимова -> Фетхие | Фетхие -> Нахимова |
| --- | --- | --- |
| ICMP56, interval1s,61x5 | 305/305 | 305/305 |
| IP1400 с DF,7x5 | 35/35 | 35/35 |
| RTT min / среднее / max, ms | 95.9 / 121.0 / 383.0 | 93.0 / 130.5 / 363.2 |

HTTP counter1 ->365: **за окно364 проверки,0 failed**. Во всех61
typed observations код200/up. Netwatch настроен на accepted codes200-399;
другие успешные2xx/3xx между snapshots не исключаются этим evidence.
Рост счётчика проверялся на каждой серии, старый успешный ответ не принимался
за новое измерение. Во всех61 series `issues=[]`; заданные критерии не менялись.

RX/TX error counters0 на обоих; drop counters не увеличились между первым
и последним наблюдением. На Фетхие TX-drop уже был2 при первом наблюдении
нового интерфейса и остался2; это не выдаётся за нулевой счётчик от создания.
CPU0% во всех sampled points на обоих, не peak measurement и не load benchmark.

RTT >200ms реально наблюдался при полном получении обычных probes. Это
согласуется с семантикой прежних быстрых timeouts, но не доказывает причину
каждого timeout исторического короткого теста. Прежний результат сохранён.

## Восстановление И TLS

После окончания окна выполнены три disable/enable **только нового клиента**.
Каждый раз новый uptime1-2s, running/AES256-GCM, новый HTTP200 с увеличением
done-tests, ICMP5/5 в обе стороны. Существующие WG/TimeWeb не отключались.

Отдельно trusted снят только с нового CA на клиенте. SSTP running=false,
явный `ssl: no trusted CA certificate found`. После возврата trust соединение
восстановилось, новый HTTP200, ICMP5/5 и DF1400 5/5 в обе стороны.
Намеренные разрывы/отказы HTTP этой фазы отделены от результатов soak.

## Exact Cleanup

Все новые PPP profiles/secret/interfaces, filters/raw observer, certificate
fingerprints и import files удалены. Safe Mode закрыт Ctrl+D, не commit.
Exports, certificate/trust snapshots и прежние global SSTP server settings
обоих роутеров совпали с baseline. До hub и remote LAN gateway по5/5
с каждой площадки; завершающие read-only probes использовали interval1s.

TimeWeb config/runtime/interface identity проверены до, в середине и после;
не изменились. Все67 client profile hashes прежние. Runtime recovery, BTH
и monitoring contracts PASS; generation не переподписывалась, baseline update
не требовался. Canonical current/initial masters не заменялись trial snapshot.
Private evidence/backup и исходники операторов сохраняются в portable store.

## Финальные Независимые Проверки

- Два новых валидных collector cycles обоих upstream: PASS, timestamps выросли
  после начала final gate. Prometheus4/4 valid,2/2 fresh, оба timestamps свежие.
- Grafana database health OK; это проверка существующего monitoring, не новой
  SSTP-вкладки или dashboard. Runtime recovery/BTH/monitoring contracts PASS.
- Focused tests33 PASS, новый полный suite509 PASS. Repository PASSED:
  441 public files,67 profiles,22 devices, `problems=[]`.
- Private store VERIFIED:2161 files,336 records. Credentials/CA key/import
  bundles/full exports/binary backups остаются private, права600/700.
- `git diff --check` чистый, staging dry-run не включает private paths.
  Commit/push/deployment не выполнялись. Расписание проверок Нахимова
  осталось на паузе, постоянные inventories/fleet/console не менялись.

Итоговый `closed.json` содержит `CLOSED`, `SSTP_30MIN_ROUTER_SOAK_PASS`,
`permanent_sstp_installed=false`. Полные наблюдения, два intermediate snapshots,
source hashes, controls, restoration и final observability receipts находятся
в указанном private evidence каталоге и portable store.

## Граница Достоверности

Это успешный30min router-level test при небольшой активной нагрузке, не
многосуточный soak, клиентский egress/приложения, throughput или отказ
WAN/электропитания. Idle-only сценарий отдельно не проверялся. Постоянный SSTP
не развёрнут и тестовый listener удалён. TimeWeb использовался
только как существующий management path и для read-only checks; его службы,
peers, routing, firewall и recovery policies не изменяются. Устройства и
Local/Remote режимы не переключались, панель не публиковалась.

Для постоянного канала нужны отдельный changeset, lifecycle сертификатов,
обработка изменения публичных адресов, boot/recovery/monitoring и controlled
client routing. Успех этого теста не означает готовую вкладку управления или
автоматическое подключение пользовательских устройств к Direct.
