# Прямой WG После Проброса Deco: 18 Октября 2026

## Итог

**`DIRECT_FORWARD_NOT_QUALIFIED`**. Начальный аутентифицированный обмен прошёл
через созданный владельцем проброс, но устойчивой двусторонней передачи нет.
Постоянный Direct не установлен, устройства не переключались. Временные
объекты удалены; exports двух роутеров и конфигурация TimeWeb совпали с baseline.

## Изменение Условий

Владелец в приложении Deco сохранил:

- `WireGuard-Direct`: **UDP 51972 -> 192.168.68.117:51972**.
- DHCP reservation: **D0-EA-11-12-F5-E8 -> 192.168.68.117**, имя MikroTik.

Обе записи подтверждены снимками сохранённых списков; протокол дополнительно
виден на снимке заполненной формы. В приложении доступны ручной IP и ручной
MAC: отсутствие MikroTik в списке клиентов не блокирует настройку. Вход
владельца через браузер не использовался. Агент не менял Deco и не удалял
сохранённые пользователем записи после эксперимента.

## Предварительные Проверки

- Strict SSH, serial Нахимова `HKM0BDXYG74`, Фетхие `HM20B6QXS8H` совпали.
- Live exports совпали с private masters; namespace/порты/сеть свободны.
- Свежие внешние endpoints существующего WG на TimeWeb: Нахимова
  `5.18.143.112`, Фетхие `194.61.140.217`. Старый `5.18.141.112` не использовался.
- На Фетхие live ether1 MAC `D0:EA:11:12:F5:E8`, DHCP bound `.68.117/24`.
- Новые AES-SHA256 backups обоих роутеров: `VERIFIED_TRANSFER`, два скачивания
  совпали; exports до/после сохранения неизменны. Restore drill не выполнялся.
- TimeWeb runtime recovery, BTH и monitoring guard: PASS до и после теста.

Первый read-only preflight остановился на различии сериализации `dynamic` в
RouterOS 7.19: поле у static filter отсутствует. Записей в роутеры тогда не было.
Read-back заменён явным запросом `where dynamic=no`; полный preflight выполнен
заново. Не выполнялось повторное создание объектов или утверждение drift.

## Ограниченный Эксперимент

Новый one-shot writer Oct18, owner `s2s-forward-trial-20261018`, интерфейс
`wg-forward-trial`. Mutating actions Oct17 не запускались: использованы лишь
выбранные низкоуровневые helpers. Два Safe Mode guard без takeover, таймер
300 s, undo Ctrl+D. На каждом роутере новый интерфейс/peer/address и пять
точных filter правил, менее 100 операций.

```text
Нахимова 10.60.62.1:51971
  -> NAT провайдера (аутентифицированный source 5.18.143.112:6303)
  -> 194.61.140.217:51972 -> Deco forward -> 192.168.68.117:51972
  -> Фетхие 10.60.62.2
```

Фетхие изучает endpoint из аутентифицированных пакетов, не из угаданного NAT
mapping. На новом интерфейсе разрешён только ICMP двух тестовых адресов;
прочий input и весь forward запрещены. Внешний UDP разрешён только от свежего
публичного IP другой площадки. Старые WG, маршруты, NAT, default, DNS и профили
не менялись; TimeWeb не переносит payload тестового диапазона.

| Серия | Нахимова -> Фетхие | Фетхие -> Нахимова |
| --- | --- | --- |
| 1 | 5/5 | 0/5 |
| 2-8, каждая | 0/5 | 0/5 |

Первый peer RX: Нахимова 572 bytes, Фетхие 660 bytes; последний: 668/660 bytes.
Непрерывного роста RX нет, возраст handshake вырос до ~129/130 s. Endpoints
оставались адресами площадок, не TimeWeb. Фильтры внешнего UDP насчитали по
7 пакетов на каждом роутере. Это подтверждает начальную достижимость, не
непрерывную доступность. DF/MTU-тест пропущен: устойчивый ICMP не прошёл.

Причина остановки не установлена. Результат не доказывает конкретный тип NAT,
блокировку/DPI оператора, неисправность Deco или определённого роутера.
Краткий handshake не считается готовым туннелем.

## Восстановление И Проверки

- После Ctrl+D: точное нормализованное совпадение exports с baseline.
  Cleanup ограничен именами/comments только данного кандидата.
- До TimeWeb по 5/5 с обеих площадок; до LAN IP удалённого роутера тоже по 5/5.
- Hub config/runtime/interface identity и все 67 client profiles неизменны.
- Проверки по расписанию на паузе; панель-кандидат не развёртывалась.
- Focused tests builder/guards: **22 PASS** (13 новых + 9 существующих).
- Полный suite дважды: **466 PASS, 1 FAIL** в существующем
  `test_scheduler.py::test_success_error_and_output_limit`: macOS
  `PermissionError` при `os.killpg`. Отдельно этот файл: 4 PASS. Его runtime
  и тесты не менялись; общий suite не объявлен зелёным.
- Два новых валидных collector cycles обоих upstream PASS. Prometheus:
  4/4 valid, 2/2 fresh, оба timestamps свежие. Grafana database health OK;
  это не приёмка нового Direct dashboard.
- Private store VERIFIED: 1324 files / 317 records. Repository validation
  PASSED: 427 public files, 67 profiles, 22 devices, `problems=[]`.
  `git diff --check` без замечаний.

## Evidence И Следующая Граница

Private evidence: `.local/backups/site-to-site/20261018T161335Z-forward/`:
снимки Deco, preflight, exports/snapshots, два encrypted backup с hashes,
восемь серий, counters, rollback и contracts. Пароли backup и private bundle
хранятся в `.local/secrets.json`; в public файлах их нет.

Эксплуатационный путь остаётся **TimeWeb**. Новая диагностика требует отдельного
ограниченного changeset, а не повторного запуска закрытого one-shot writer.
Миграция PPPoE, firmware update, ослабление device-mode и массовое открытие UDP
не выполнялись. [План](../tasks/PLAN-site-to-site-direct.md).
Семантика endpoint/keepalive/counters:
[официальная документация MikroTik](https://help.mikrotik.com/docs/spaces/ROS/pages/69664792/WireGuard).
