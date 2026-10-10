# BTH: проверка перед установкой, 2026-09-13

Пользователь запросил BTH-профили MacBook Sergey и iPhone Sergey. Работа обоих
зарубежных профилей на iPhone подтверждена пользователем. Серверные изменения
для BTH пока не применены.

## Текущие проверки

- SSH TimeWeb и MikroTik через существующий namespace доступны; локальный ключ
  MikroTik не передавался на сервер, trust проверен через HostKeyAlias 192.168.88.1.
- PID wg-relay: 1181. Правило 300: iif wg-home lookup 300;
  table 300: default dev wg-home.
- 10.30.30.5 отсутствует в runtime peers и постоянном wg-home.conf.
- TimeWeb -> 10.30.30.2: 3/3 ICMP, средний RTT 3.681 мс.
- MikroTik peer TimeWeb допускает 10.30.30.0/24 и 0.0.0.0/0.
- Домашний WAN ether1: 10.12.20.168/22, default через 10.12.20.1.
- NAT домашнего выхода и FastTrack bypass wg-home присутствуют.
- wg-home входит в LAN list: новый /32 обязательно закрыть для input/management
  и private destinations до активации. Старые BTH peers не ограничивать.
- TimeWeb: 1967 МиБ RAM, available 1482 МиБ. Это текущий срез, не измерение
  потребления будущего worker.
- /tool fetch на MikroTik запрещен device-mode. Режим не менялся. Независимое
  HTTP-подтверждение домашнего публичного IP еще не получено; старый endpoint
  не выдавать за доказательство нового egress.

## Следующий шаг

По правилу пользователя установка нового сервиса требует отдельного согласования.
Нужен второй легкий процесс существующего Xray: BTH worker с собственной DNS
маршрутизацией через дом, отдельным UID и лимитом памяти. Новые пакеты и Python
на сервер не требуются. Профили нельзя выдавать как готовые до серверной настройки.

После согласования: свежий backup; scoped-защиты нового /32 на relay и MikroTik;
peer; worker/readiness gate; два UUID; короткий restart основного нового Xray;
тесты DNS, внешнего IP, upload/download и независимости от Fornex/Cenuta;
точный откат при неуспехе. Старые WG-контейнеры не перезапускать.

Мастер read-only аудита: services/transport/timeweb-reality/audit_stage9_bth.py.
Снимки сохраняются в защищенные stage9-audit-* в том же каталоге. Первый
export с параметром show-sensitive=no был отвергнут RouterOS; файл с текстом
ошибки не является backup. Аудитор исправлен: /export terse без вывода секретов
по умолчанию, с проверкой наличия секций конфигурации, а не только SSH exit code.
