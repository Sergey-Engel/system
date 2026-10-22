# Нахимова - TimeWeb: Ручной Выбор Выхода

21 октября 2026. Device routing4.1.0, SSTP data plane2.0.0 поверх
существующего транспорта1.1.1. BTH, управление и отдельный wg-s2s-tw
остаются на WireGuard. Автоматического переключения нет.

## Панель

[Device routing](http://127.0.0.1:19118/#site-to-site), площадка Nakhimova:
только постоянные DHCP reservations, имя из справочника и IP.

| Режим | Путь |
| --- | --- |
| Standard | Обычные правила Нахимова, без членства в четырёх VPN-списках и без Direct |
| WG-Cenuta-RU | Прежний Split Cenuta, тот же mode ID cenuta и CENUTA_Devices |
| WG-Fornex-RU | Прежний Split Fornex, тот же mode ID fornex и VPN_Devices |
| SSTP-Cenuta-RU | SSTP до TimeWeb91.222.238.208:443, затем существующий выход Cenuta |
| SSTP-Fornex-RU | SSTP до того же TimeWeb endpoint, затем существующий выход Fornex |
| Direct SSTP-RU via Fethiye | Прямой канал Нахимова - Фетхие с RU bypass в провайдера Нахимова |

Новые SSTP режимы наследуют действующие RU/local/BitTorrent исключения и
специальное назначение из исходной политики, но RU bypass теперь выше
него по приоритету. Direct обоих направлений также исключает российские IPv4:
[правила, источник CIDR и границы](Panel_RU_Direct.md). Это не full-tunnel
для абсолютно всех направлений. На Фетхие по-прежнему только Standard/Direct
для клиентов Wi-Fi MikroTik; новых режимов там нет.

Выбор меню сам по себе ничего не меняет. Галочка Apply явно применяет
режим; для SSTP дополнительно подтверждается устройство/IP/выход.
Нельзя выбрать недоступный путь. Перед записью SSTP выполняется свежая
проверка реального HTTPS egress; обычный Refresh читает проверенное состояние.
Health timer измеряет выходы, но никогда не меняет назначения.

Кнопка со стрелкой Undo восстанавливает предыдущее подтверждённое назначение
того же MAC/IP/lease, включая исходную запись списка и комментарий.
Изменившаяся привязка, устаревший revision и неизвестный drift запрещают
запись. После неизвестного результата операции сохранён pending: доступен
Standard либо доказуемый откат; нельзя слепо повторять запрос.
Сообщения сохраняются до явного закрытия, обновление статуса их не стирает.

## Технические Границы

Один аутентифицированный PPP/SSTP несёт оба класса IP-трафика. На Нахимова
разные списки/таблицы и SNAT sources10.60.65.10/10.60.65.11. В namespace
sstp-timeweb классы преобразуются в зарезервированные инфраструктурные
sources10.50.50.245/10.10.10.245. Узкий veth connector соединяет только
sstp-timeweb и закреплённый namespace существующего wg-relay.
В root namespace нет нового veth, NAT или default route.

В wg-relay добавлен только source selector218 для Cenuta, адреса/возвратные
маршруты connector и собственный nft guard. Он запрещает неправильный
egress, частные/служебные назначения и вход к самому relay. Не меняются
WG keys, peers, выданные профили, исходные tables100/200/300 и Xray config.
Новые источники не являются дополнительными WG identities или профилями
пользователей; их нельзя выдавать другим клиентам.

Новые таблицы RouterOS имеют blackhole254 при недоступном SSTP, а namespace
guards запрещают выход в обход нужного зарубежного интерфейса. RU/local
исключения остаются намеренно обычными. IPv6/full-device DNS leak приёмка
не заявляется; отдельные глобальные IPv6 адреса до установки не обнаружены.

BTH routing/peers/interface и management proxy остаются WG. Его полный
RPDB contract расширен ровно новым селектором218, monitoring manifest и
runtime recovery policy согласованы отдельно на точный additive diff.
Неизвестный drift не подписывается. Временная приостановка проверочных
timers при смене baseline не означает остановку работающего BTH/VPN.

pppd-compatible ip-up hook восстанавливает только две alias /32 routes
после переподключения. Connector запускается до runtime recovery;
собственный health timer не реализует failover. Перезапуск собственного
connector не меняет старую политику, кроме допускаемой смены ifindex.
Отдельный полный reboot хоста для этого изменения не выполняется.

## Проверка И Откат

Runbooks/исходники: [SSTP](../../services/transport/sstp-timeweb/README.md),
[исходный план](../tasks/PLAN-nakhimova-timeweb-manual-transport.md).
Серверная команда status проверяет hashes, namespace guards и свежесть
измерений; probe обновляет только измерения. Для каждого выхода измеряется
настоящий IPv4 HTTPS egress, не только handshake.

При ошибке per-device Apply используется явный Undo или Standard после
проверки pending. Полный откат установки - отдельный reviewed changeset:
сначала исключить SSTP назначения через тот же контроллер, затем удалить
только новые RouterOS objects/alias и connector, вернуть точные сохранённые
BTH/monitoring/recovery bindings и private masters. Нельзя останавливать
WireGuard, пересоздавать wg-relay или восстанавливать весь роутер из старого
backup ради отката одного устройства. Архивы - конфигурационные копии,
не образы диска и не доказательство live restore.

## Источники

- [RouterOS policy routing](https://help.mikrotik.com/docs/spaces/ROS/pages/59965508/Policy%20Routing).
- [RouterOS SSTP](https://help.mikrotik.com/docs/spaces/ROS/pages/2031645/SSTP).
- [accel-ppp ip-up hook](https://docs.accel-ppp.org/configuration/pppd_compat.html).
