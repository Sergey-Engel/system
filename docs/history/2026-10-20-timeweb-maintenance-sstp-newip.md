# TimeWeb: обслуживание и независимый SSTP на новом IP

Дата: 20 октября 2026. Статус: **принят как изолированный транспорт**;
автозапуск и реальный reboot проверены. Пользовательская маршрутизация
и автоматическое переключение не включены.

## Разрешение И Границы

Пользователь явно разрешил обновления TimeWeb и reboot с временным перерывом
WireGuard/Xray, затем настройку SSTP на дополнительном IPv4. Все действия
и проверки выполняет агент; автоматического выбора транспорта нет.
Проверенный SSH hostname: 6275803-hh441050. Пользователь вошёл в аварийную
консоль Lucky Bridge, открыта страница сервера 6275803 у TimeWeb.

Существующие VPN keys, выданные профили, конфигурации и выбранные режимы
сохранены. Docker container ID и image не заменялись; container не
пересоздавался. Direct SSTP Нахимова - Фетхие не перенастраивался.
Предыдущий [непринятый кандидат](2026-10-20-sstp-timeweb-candidate.md)
остаётся отдельной исторической попыткой, не переименован в успешную.

## Обслуживание ОС

Перед работой containerd-shim wg-relay имел 9027 потоков, RSS 989292 kB;
9014 потоков находились в wait_for_partner. Выборочные kernel stacks
показали блокировку fifo_open/openat. Это локализация механизма, а не
доказательство тождества конкретному upstream issue.
Исходный load 10.37 / 14.94 / 14.22, доступно около 93 MiB RAM.

Добавлен swap 2 GiB: /swapfile-timeweb-maintenance, mode600, отдельная строка
в /etc/fstab. Исходный fstab сохранён приватно. После этого полный refresh
подписанных apt indices прошёл, установлено 25 обновлений существующих
пакетов, без удаления пакетов и release upgrade Ubuntu.

| Компонент | До | После |
| --- | --- | --- |
| Docker CE | 29.8.1 | 29.9.1 |
| containerd.io | 2.3.6 | 2.4.2 |
| Kernel после reboot | Старый загруженный kernel | 6.8.0-147-generic, ранее уже установленный |
| Доступная RAM после первого reboot | Около 93 MiB до обслуживания | Около 1.3-1.4 GiB |
| containerd-shim после первого reboot | Более 9000 потоков | 13, затем 22 при операционных проверках |

Также обновлены существующие apparmor, ca-certificates, git, xz/liblzma,
tzdata, snapd, open-iscsi/open-vm-tools и установленные Docker plugins/Mesa
libraries. Полный exact package plan и installed versions сохранены приватно.
Старые deb Docker CE/CLI/containerd скачаны для возможного адресного отката;
downgrade не выполнялся. Docker images не скачивались и не заменялись.

Во время установки controllers/collector и runtime recovery были штатно
остановлены, чтобы не выполнять параллельные изменения namespace.
Временный policy-rc.d запрещал внеплановые package-driven service starts;
он удалён после установки, исходная политика не подменена постоянно.
При reboot старые службы восстановлены штатным runtime recovery.
Policy bindings/hash сохранены, неизвестный drift не публиковался.

## Новый Endpoint

- Приём: **91.222.238.208:443/TCP**; Xray остаётся на **94.241.171.65:443**.
- Дополнительный адрес 91.222.238.208/24 добавлен overlay-файлом
  /etc/netplan/90-sstp-timeweb-additional-ip.yaml. DHCP, исходные network
  files и default gateway не заменялись; общий netplan apply не выполнялся.
  Настройка проверена реальной последующей перезагрузкой.
- RouterOS client Нахимова: sstp-timeweb, 10.60.65.2;
  server namespace: sstp-timeweb, interface sstptw0, 10.60.65.1.
- MTU/MRU1400; TLS1.2, AES256-GCM/PFS, отдельный CA и серверный сертификат
  с новым IP в SAN; проверка CA и адреса включена на MikroTik.
  MSCHAPv2 использует отдельный высокоэнтропийный secret. Это не mutual TLS.
- Новый серверный private key и CA/PPP material находятся только в private
  store/защищённых masters. CA private key не передавался на VPS.
- accel-ppp source pin и off-host build не изменены: b8a3c54aa34434312aa0053686ec37a133fb54e6.
  Собственные библиотеки сохранены. Build dependencies на VPS не ставились.

Public socket передаётся proxy в отдельный namespace, backend остаётся
127.0.0.1:5444. Root veth/NAT/firewall changes не требуются. Namespace не
имеет default/LAN route, forwarding выключен; восемь новых RouterOS rules
разрешают только peer ICMP/SSH и запрещают transit/IPv6. Новые default routes,
выбор устройств и автоматическое переключение не добавлялись.

Новый listener ограничен текущим аутентифицированным публичным endpoint
Нахимова и self-test адресами TimeWeb. Старое предположение об IP отвергнуто
до записи служб. IP/Cloud показывал другой, ранее сообщённый адрес;
authority для текущего source — свежий WG handshake закреплённого peer
10.60.60.2, успешный peer ping и проверенный serial роутера. Наблюдавшийся
TCP peer нового SSTP совпал с этим endpoint.
**При смене внешнего IP Нахимова source allowlist потребует отдельного
reviewed обновления. Автоматического расширения доступа нет.**

## Проверки

- Свежий полный post-OS backup VERIFIED, immutable runtime/config bindings,
  прежние WG runtime keys/policy и per-device desired values сохранены.
- Runtime recovery check прошёл после каждого reboot. Автоматический
  recovery сохранил тот же container ID/image и прежние профили/ключи.
- Два последовательных свежих цикла Fornex/Cenuta после первого reboot:
  fresh=1, все HTTPS probe_valid=1, cycle timestamps выросли.
- По новому каналу проверены SSH host key и serial HKM0BDXYG74,
  двусторонний DF1400 и SFTP 524288 байт в каждую сторону с точным hash.
  После контрольного reboot передача повторно прошла.
- Неверный PPP password отклонён; authentication failure есть в server/router
  logs. Недоверенный CA отклонён; правильный сертификат/credential восстановлены.
  Три reconnect прошли, persistent RouterOS export после тестов совпал.
- Проверены CA chain/IP серверного сертификата и включённая строгая проверка
  на действующем peer. Одновременный generic OpenSSL self-test непригоден:
  max-sessions=1 закрывает вторую сессию до TLS. Неуспешный self-test сохранён;
  он не переименован в успешный handshake.
- Внешняя проба с Fornex (не разрешённый source) не установила TLS: timeout7.
- Autostart четырёх собственных units включён. Контрольный reboot сохранил
  оба публичных IP, автоматически поднял старые VPN и новый SSTP без ручного
  repair. У нового канала нет зависимости от Docker/WireGuard units.
- Read-only status проверяет собственные file hashes, units, PPP/MTU/counters,
  expiry с предупреждением за 30 дней. Старые Grafana WG metrics не выдаются
  за телеметрию SSTP; отдельный transport включён в infrastructure inventory.

Пятнадцатиминутный soak: **PASS**, 904.9 s, 26 успешных наблюдений.
Обе стороны DF1400 и RouterOS ICMP64 прошли без потерь в пробах;
server/proxy PID и PPP ifindex2 не менялись, счётчики монотонны.
В финальном sample shim имел 15 потоков и RSS14036 kB, load оставался
6.35 / 6.97 / 5.15. Высокая CPU-нагрузка не скрыта успешным сетевым тестом.
Пользовательские приложения и маршрутизация устройств через SSTP этим
этапом не принимаются: production routing намеренно не включён.

## Исправления И Неуспешные Попытки

Первый configuration backup сохранил FAILED из-за одного timeout docker ps;
архив проверен независимо с явно указанным исключением. Все последующие
полные копии прошли штатный verifier. [Исходный preflight](2026-10-20-timeweb-maintenance-preflight.md).

После чистого reboot iproute2 возвращает пустой stdout для пустого списка
named namespaces. Первоначальный parser ожидал JSON и отказал до создания
namespace. Release **1.1.1** корректно принимает пустой список, но отвергает
повреждённые данные; добавлены regression tests. RouterOS print as-value
не выдаёт вычисляемый certificate fingerprint: используется отдельный get.
Неуспешный импорт проверен по SHA256 fingerprint, удалён только новый CA,
точный исходный export восстановлен перед повторным deployment.

HTTP fetch с роутера запрещён его device-mode. Device-mode не менялся;
полезный трафик проверен через SFTP вместо включения дополнительных функций.
Исходы неуспешных проверок сохранены, неизвестные contracts не переподписаны.

## Копии И Реестры

Private evidence root: .local/backups/timeweb-maintenance/20261020/.

| Копия | Результат / SHA256 |
| --- | --- |
| TimeWeb post-OS 2026-10-20T170031Z_current-config | VERIFIED, 436 host files, 110 required offline restores; 202162bd5dee27993e93b436d757e9f56c43669e8729dcc2cc808527d317c81f |
| TimeWeb с новым SSTP 2026-10-20T171800Z_current-config | VERIFIED, 437 host files, 112 required offline restores; edf194e1db202298abb930cec7b56a2769352f60c6de8f5a1732b9559a29ab70 |
| TimeWeb после контрольного reboot 2026-10-20T173151Z_current-config | VERIFIED, 437 host files, 112 required offline restores; 9c335540ac198be85f440421fb45aafd3655ac736f05d09c8788e494994b49ca |
| RouterOS post-SSTP | VERIFIED_TRANSFER; 0f994ab2c51a752bf1f8d387b6f0b73a0ea62f0d48865534a216740686f8b170 |

Backup collector теперь включает SSTP binary/libs/config/units/manifest,
netplan overlay и fstab; verifier проверяет полный owned manifest и hashes.
Это конфигурационные копии, не образы диска и не disaster-recovery drill.
Клиентские profiles67 и устройства22 не менялись; новый transport не выдаёт
новых end-device profiles и не добавляет режим в UI выбора устройств.

Canonical private store и явно изменённые masters синхронизированы и
прошли verify-only; 3314 files / 360 records на момент финального checkpoint.
Все 67 клиентских профилей сравнивались по SHA256, mandatory старые
конфигурации и Xray binary совпали с pre-maintenance архивом.
HTTP/state консоли и оба Device routing read API доступны без ошибок;
fleet3/3 ready проверен внутри mount namespace работающей консоли.
Prometheus показывает 22 device activity series, Grafana health database=ok.
Dashboard resources подтверждены read-only в реально используемой Grafana
SQLite DB; authenticated render не проверялся, API search требует входа.
Никакие Grafana credentials/authentication не менялись.
Полный локальный suite: **633 passed**; focused transport/backup gates: **54 passed**.

По отдельному запросу владельца позднее сохранены ещё более свежие
TimeWeb/Nakhimova backups и локальный переносимый набор, повторены
read-only health/hash gates и подготовлена безопасная Git-публикация.
[Публикационный checkpoint с точными SHA256](2026-10-20-timeweb-publication-checkpoint.md).

## Ограничения

Пятнадцать минут не доказывают отсутствие многодневной resource leak.
Снижение памяти/потоков после restart не является доказательством полного
исправления её upstream причины. CPU load оценивается отдельно от памяти.
При наблюдении после второго reboot CPU busy около 100%, pressure avg10
97.98%, load 7.92 / 5.80 / 2.87. В верхней части CPU sample — runc/docker
и фоновые Python controllers. У shim 13 потоков: 11 futex_wait_queue,
2 ep_poll, **нет wait_for_partner**; memory pressure отсутствует.
Это отдельная CPU-нагрузка существующего control plane, не повторение
прежнего FIFO/thread accumulation. Частота/логика старых routing controllers
и их защитные проверки не ослаблялись. Для снятия CPU-ограничения требуется
отдельная оптимизация проверок либо согласованное увеличение ресурсов VPS.
Смена внешнего IP Нахимова требует reviewed source allowlist update.
Routing/failover, LAN transit и клиентская Internet-приёмка вне этого этапа.

## Источники

- [TimeWeb: дополнительный IP](https://timeweb.cloud/docs/unix-guides/adding-ip-addresses).
- [Docker 29 release notes](https://docs.docker.com/engine/release-notes/29/).
- [MikroTik IP/Cloud](https://help.mikrotik.com/docs/spaces/ROS/pages/97779929/Cloud):
  public-address показывает адрес ранее выполненного cloud request.
- [accel-ppp pinned SSTP source](https://github.com/accel-ppp/accel-ppp/blob/b8a3c54aa34434312aa0053686ec37a133fb54e6/accel-pppd/ctrl/sstp/sstp.c):
  max-sessions проверяется до TLS handler.
