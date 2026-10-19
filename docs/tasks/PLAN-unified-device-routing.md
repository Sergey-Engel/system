# PLAN: единое управление маршрутами устройств

Статус: Done
Дата: 2026-10-19
Разрешение: пользователь согласовал UI и поручил «Делай», без изменения
рабочего транспорта TimeWeb и без автоматического переключения клиентов.

## Контракт

- Единая вкладка Device routing вместо двух независимых списков назначения.
- Площадки: Nakhimova (первая, по умолчанию), Fethiye.
- Нахимова: только enabled permanent DHCP MAC/IP reservations `defconf`,
  включая offline. Режимы Standard / Split Cenuta / Split Fornex / Direct Fethiye.
- Фетхие: только авторизованные клиенты Wi-Fi MikroTik с однозначной DHCP
  привязкой `.89/24`. Режимы Standard / Direct Nakhimova.
- Имя только по exact MAC из справочника; без имени — Unknown device.
  Данные MAC доступны в деталях, в основной строке имя и IP.
- Выбор режима не пишет настройки. Явная Apply меняет только выбранное
  устройство; Direct и оба Split-включения взаимоисключающие.
- Старый HTTP writer Direct отключается после включения unified controller,
  чтобы старый открытый браузер не мог обойти единое управление.
- Обновление только вручную/по команде; ошибки не исчезают по таймеру.
- Состав списков вне eligibility не меняется автоматически; CIDR/shared
  memberships и неоднозначные MAC/IP блокируют опасные операции.

## Операционная модель

Source of truth — live router. Существующие Split rules, RU/local/BitTorrent
исключения и транспорт не редактируются. Меняется только exact host membership
в `CENUTA_Devices`/`VPN_Devices` и существующие per-device Direct controls.
Один shared flock сериализует операции обоих источников и legacy writers.
Каждая операция имеет durable intent до первой записи, phase и readback.
Обновление строгого baseline допускается только для доказанного exact diff
списка выбранного IP. При неизвестном drift или непрочитанном результате —
pending, а не успех; восстановление только явной командой на этот же target.
Никаких широких firewall/route/connection flush, смены ключей или failover.

## Задачи

| Шаг | Задача | Приоритет | Статус |
| --- | --- | --- | --- |
| 1 | Read-only audit, fresh backups, исходные назначения и no-touch proof | P0 | Done |
| 2 | Тесты eligibility, конфликтов, safe writer и recovery | P0 | Done |
| 3 | Unified controller и один UI с разными фильтрами площадок | P0 | Done |
| 4 | Локальные/browser regressions, guarded local deployment | P0 | Done |
| 5 | Live readback, private store, monitoring/contracts и документация | P0 | Done |

## Приёмка

Fixture-проверки всех переходов между четырьмя режимами, binding/revision/CSRF,
partial failures, pending recovery, IP reassignment и offline reservations.
Desktop/mobile browser: только один выбор режима, явная Apply, sticky errors,
нет auto-poll, нет overflow, VPN-раздел сохранён. Live-проверки read-only:
семь permanent устройств Нахимова, только Wi-Fi Фетхие, исходные режимы без
изменений. Реальных клиентов ради UI-теста не переключать; это граница приёмки.
Fresh encrypted pre/post backups, unchanged router/TimeWeb snapshots и профили,
два новых monitoring cycles, repository/private-store validation.

Результат: release3.0.0 установлен. 610 tests passed; live desktop/mobile
read-only proof, исходные назначения и sensitive exports неизменны.
Два новых валидных collector cycles, Prometheus/Grafana health и повторные
runtime/BTH/monitoring contracts PASS. Первый runtime check был неуспешным,
причина не установлена; запись сохранена, TimeWeb не исправлялся/не менялся.
Repository validation PASS:67 profiles/22 devices; private evidence сверено.
Полный [протокол и границы](../history/2026-10-19-unified-device-routing.md).

## Откат

До deployment сохраняются исходные local source/config/state. Откат UI и
controller config без изменения пользовательских маршрутов допустим только
пока не было unified операций; после первой операции сначала reviewed reconcile
state/baseline. Старые доступы/контракты TimeWeb не изменяются.
