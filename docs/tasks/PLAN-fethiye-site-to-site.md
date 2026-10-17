---
type: plan
status: in-progress
created: 2026-10-16
updated: 2026-10-16
tags: [mikrotik, fethiye, site-to-site]
---

# PLAN: MikroTik Фетхие и соединение с Нахимова

**Статус:** In Progress, шаги 1-4 завершены в минимальном согласованном объеме;
пароль сохранен по решению пользователя. Шаг 5 подготовлен и проверен;
пользователь разрешил изолированный пилот. Шаг 6 принят в служебном ICMP-only
объеме: HTTPS и страница входа WebFig на MacBook подтверждены. В шаге 7A
добавлено второе служебное плечо Нахимова; его HTTPS-проверка принята.
Шаг 7B применен: связь LAN через TimeWeb работает, MacBook -> gateway Нахимова
подтвержден пользователем. Приложения и входящий доступ к MacBook не приняты.
В шаге 8 принят ограниченный тест Local -> Нахимова -> Local: HTTPS и внешний
IPv4 проверены на MacBook. Сейчас Local, прежний адрес закреплен статически.
Постоянный Remote, отказ канала, обратный выход и приложения не приняты;
причина ранее наблюдавшихся внешних ICMP-потерь Нахимова не установлена.
**Создан:** 2026-10-16.
**Файл плана:** `docs/tasks/PLAN-fethiye-site-to-site.md`.

## Принятые решения

Пользователь согласовал 16 октября:

- Deco и подключенные к нему устройства остаются как есть.
- Новый MikroTik работает за Deco, не заменяет провайдерский шлюз.
- В текущем этапе управляемыми клиентами являются только устройства,
  самостоятельно переключенные на Wi-Fi MikroTik. Массового переноса нет.
- Тестовый клиент: MacBook Air (Sergey). Компьютер агента остается в сети Deco.
- Сначала вариант A: соединение площадок через TimeWeb.
- Затем вариант B: прямой канал, TimeWeb остается резервом.
- Выполнение по одному шагу, с реальными проверками после каждого изменения.

Основание: [проект соединения площадок](../architecture/Nakhimova_Fethiye_Site_to_Site_Design.md),
[стартовый аудит](../hosts/fethiye/MikroTik_hAP_ax3_Initial_Audit.md),
[паспорт существующей сети](../hosts/fethiye/network-passport.md).

## Схема подключения

```text
Антенна провайдера -> PoE -> Deco main (PPPoE, без изменений)
                              |
                    LAN 192.168.68.0/24
                     |                  |
              Прежние клиенты      MikroTik ether1 (WAN)
              и компьютер агента   DHCP 192.168.68.117 сейчас
                                        |
                              LAN 192.168.89.0/24 / Wi-Fi
                                        |
                               MacBook Air (Sergey)

Этап A: LAN Нахимова -> MikroTik -> TimeWeb <- MikroTik <- LAN Фетхие
Этап B: основной путь MikroTik Нахимова <-> MikroTik Фетхие
        резервный путь через TimeWeb
```

Порты ether2-ether5 остаются локальными LAN-портами MikroTik, но перенос
кабельных клиентов в текущий этап не входит. ether1 не включать в LAN bridge.
Это маршрутизируемое L3-соединение; общий DHCP, L2 bridge/EoIP и автоматический
AirPlay/Bonjour discovery между площадками не входят в базовый объем.

## Параметры и границы

| Объект | Текущее / целевое решение |
| --- | --- |
| MikroTik Фетхие | hAP ax3, serial `HM20B6QXS8H`; не путать с Нахимова |
| WAN Фетхие | ether1, DHCP от Deco, сейчас `192.168.68.117/24` |
| Доступ агента | Сейчас SSH с `192.168.68.115/32`; не расширять на всю сеть |
| Wi-Fi пилота | Сначала сохранить `MikroTik-12F5ED` и действующий пароль |
| LAN Нахимова | Сохранить `192.168.88.0/24` |
| LAN Фетхие | `192.168.89.0/24`, bridge `192.168.89.1/24`; применено 16 октября в 10:46, MacBook DHCP/Internet/WebFig приняты |
| DHCP пилота | gateway/DNS `192.168.89.1`, pool `192.168.89.100-192.168.89.199`, lease 30 минут |
| Тестовый клиент | Определить заново по IP и MAC именно на Wi-Fi MikroTik; MAC сети Deco не переносить автоматически |
| Регион Wi-Fi | Turkey на wifi1/wifi2 с 16 октября 11:29; MacBook переподключился, интернет подтвержден |
| Транспорт этапа A | Два исходящих WireGuard-плеча к TimeWeb; отдельные идентичности и адреса после live-аудита |
| Межплощадочная связь | Явные маршруты и ограниченные firewall-разрешения; без NAT между управляемыми LAN |
| Интернет по умолчанию | Местный SkyFiberNet; удаленный выход через Нахимова сначала только для тестового клиента |
| Удаленный выход | Отдельная политика маршрутизации, согласованный DNS, исключения endpoint/control traffic и FastTrack |
| Отказ удаленного выхода | Fail-closed для выбранного Remote site; никакого скрытого выхода через местного провайдера |
| IPv6 | Не включать раздачу до согласования маршрутов; исключить обход удаленного выхода по IPv6 |
| Транспортный резерв | Отдельно испытать SSTP/TLS; TCP 443 TimeWeb занят REALITY, не переиспользовать вслепую |
| Прямой канал | Только после отдельного согласования: UDP port forward на Deco либо иной проверенный способ; сейчас Deco не менять |

Новые адреса VPN, порты и имена интерфейсов назначаются после сверки реестра
и live-состояния, не по одному только историческому документу. Удаленный выход
Фетхие ограничивается реальным upload площадки: последний прямой замер 5.48 Mbps.

## Список задач

| # | Задача | Приоритет | Зависимость | Статус | Дата завершения |
| --- | --- | --- | --- | --- | --- |
| 1 | Исходная связь и тестовый MacBook | P0 | Нет | Готово и проверено | 2026-10-16 |
| 2 | Безопасное управление и свежая копия | P0 | 1 | Готово с исключением: пароль сохранен по решению владельца | 2026-10-16 |
| 3 | Выбор свободной LAN и смена адресации | P0 | 2 | Готово: Router, DHCP, интернет и WebFig PASS | 2026-10-16 |
| 4 | Регион Wi-Fi и минимальное усиление защиты | P1 | 3 | Готово: country/services/NTP приняты, strong SSH проверен | 2026-10-16 |
| 5 | Live-аудит Нахимова и TimeWeb, точный changeset | P0 | 4 | Готово: scope одобрен, backups/preflight/dry-run PASS | 2026-10-16 |
| 6 | WireGuard Фетхие -> TimeWeb, только служебная связь | P1 | 5 | Готово в ICMP-only объеме: Router/Server/monitoring PASS, MacBook HTTPS и страница WebFig подтверждены | 2026-10-16 |
| 7 | Новое плечо Нахимова и доступ между LAN | P1 | 6 | Готово в сетевом объеме: router tests и MacBook -> gateway Нахимова PASS; входящий MacBook/apps не приняты | 2026-10-16 |
| 8 | Выбор Local / Нахимова на MacBook и обратный выход | P1 | 7 | Проба Local -> Нахимова -> Local принята: IPv4/HTTPS PASS; сейчас Local. Fail-closed, приложение и обратный выход впереди | Нет |
| 9 | Резервный транспорт и автоматическое восстановление | P1 | 8 | Не начат | Нет |
| 10 | Приемка этапа A, документация и verified backup | P0 | 9 | Не начат | Нет |
| 11 | Отдельное согласование и пилот прямого канала B | P2 | 10, доступность входящего канала | Отложен | Нет |

## Порядок выполнения и проверок

Каждый шаг: зафиксировать исходное состояние и точный rollback, внести одно
ограниченное изменение, прочитать настройки обратно, проверить реальный путь.
Следующий шаг не начинать, пока текущая проверка не пройдена. Клиентская
проверка выполняется на MacBook, а не подменяется ping с самого роутера.
Тесты с отключением WAN, сменой Wi-Fi, restart или reboot предварительно
объявлять пользователю и проводить в согласованное окно.

### Шаг 1: исходная связь

Без изменения настроек сверить serial, DHCP WAN, Ethernet link, DNS и ping.
Пользователь подключает MacBook к Wi-Fi MikroTik и открывает внешний HTTPS-сайт.
Затем агент сверяет его lease и регистрацию; при нескольких кандидатах
пользователь сообщает IP. Записать исходный IP, MAC, gateway и результаты.

Лог 16 октября 2026, 09:48 Europe/Istanbul: strict SSH успешен, serial
`HM20B6QXS8H` подтвержден; WAN `.117`, LAN `.88.1`, ether1 link-ok 1 Gbps
full-duplex. Ping Deco 3/3 (avg 0.348 ms), `1.1.1.1` 3/3 (avg 45.941 ms),
DNS `example.com` разрешается. Wi-Fi видит только iPhone и Watch; MacBook
еще не зарегистрирован. Настройки не менялись. Статус: ожидается MacBook.

Дополнение 09:52 Europe/Istanbul: пользователь подтвердил открытие внешнего
сайта на MacBook. Live: lease `192.168.88.252`, hostname `MacBookAir`, MAC
`A2:C1:5E:29:F5:8E`; wifi1 (5 GHz), сигнал -60 dBm, ft-wpa3-psk.
Это MAC текущего SSID, не MAC из прежнего inventory Deco. Шаг 1 завершен.

### Шаг 2: безопасное управление

Сначала свежая зашифрованная резервная копия и экспорт в `.local`, проверка
переноса и private store. Устранить раскрытие SSH host key и пароля admin,
описанное в аудите, отдельными подшагами с переподключением после каждого.
Метод ротации, доверенное подтверждение нового public key и способ выдачи
пароля/SSH-доступа определить до исполнения; не доверять неизвестному ключу
автоматически и не экспортировать приватный host key повторно. Сохранить
резервный локальный доступ до успешного теста нового. Не отключать используемый
способ входа до проверки замены. Нужные дополнительные identities согласовать.
Проверки: новый strict SSH, локальный вход, интернет MacBook, новая копия;
старые backups пометить как содержащие прежний ключ. Restore не запускать.

Лог 09:53 Europe/Istanbul: свежая копия
`.local/backups/fethiye/20261016T065347Z-pre-management-rotation/` сохранена;
encrypted binary дважды прочитан по SFTP с совпадением байтов, экспорты
до/после совпали без служебных комментариев. Статус VERIFIED_TRANSFER,
restore не испытан. Пять файлов, включая verification.json, внесены в private
store; initial/current не перезаписаны. Ключи и пароль не менялись.
Перед ротацией требуется подтвердить вход пользователя в WebFig с MacBook
по локальному `192.168.88.1`, независимый от SSH-доступа агента через ether1.

Лог 09:57 Europe/Istanbul: пользователь подтвердил локальный WebFig-вход.
Заменен только SSH host key. Новая RSA 2048 пара создана локально; encrypted
PKCS8 передан по ранее закрепленному SSH и импортирован, временный файл
удален. Это не пользовательский SSH-ключ, новые пользователи не создавались.
Доверенный public key известен до импорта; неизвестный сетевой ключ не
принимался. Повторный strict SSH с новым ключом прошел, serial подтвержден,
ping `1.1.1.1` 3/3. Fingerprint:
`SHA256:eH3GEIpmWD19iX55MwgWYoIoj0J1sA7QUCukDb8GZPc`.
Ротация не потребовала restart/reboot; пароль admin не менялся.
Метод предусмотрен [RouterOS SSH](https://help.mikrotik.com/docs/spaces/ROS/pages/132350014/SSH).

Evidence: `.local/backups/fethiye/20261016T065709Z-host-key-rotation/`;
зашифрованный ключ и passphrase сохранены только в private store. После
замены создан fresh binary/export backup
`.local/backups/fethiye/20261016T065747Z-post-host-key-rotation/`,
VERIFIED_TRANSFER (два чтения SFTP, body export без drift), без restore drill.
Initial/current dated snapshots не перезаписаны; текущий known_hosts обновлен
вместе с canonical store. До следующего изменения нужна повторная проверка
внешнего сайта на MacBook. Старый backup восстанавливать как актуальный нельзя:
он вернет раскрытый ключ. Шаг 2 целиком еще не завершен.

Пользователь подтвердил повторное открытие внешнего сайта на MacBook после
ротации host key: клиентская проверка PASS. Предложен отдельный ключ входа
SSH для существующего admin (не новый пользователь), чтобы смена пароля
WebFig не прерывала доступ агента. Это другой ключ, не host key сервера.
До согласования ключ входа не создавать и не импортировать. Новый пароль
пользователь задает и хранит приватно; не просить его отправлять в чат.

Лог 10:09-10:12 Europe/Istanbul: пользователь разрешил SSH-ключ для admin.
Перед изменением сделан свежий VERIFIED_TRANSFER backup
`.local/backups/fethiye/20261016T070848Z-post-host-key-rotation/`.
Создан отдельный RSA 4096 ключ входа `.local/ssh/fethiye_admin_rsa`;
на роутер передан только публичный ключ, импортирован для существующего admin.
Новых пользователей и разрешений firewall нет. Приватный ключ mode 600,
каталог 700, файлы ключа внесены в canonical private store до импорта.
Повторный strict SSH без пароля прошел; serial подтвержден, ping Deco и
`1.1.1.1` по 3/3, DNS работает, lease MacBook остается bound.
Негативный контроль: отдельный SSH-вход только с прежним паролем отклонен
при существующем `always-allow-password-login=no`. Браузерный пароль не менялся.

Первый helper остановился при cleanup с ENOENT: public source уже отсутствовал
после импорта. Не повторяли импорт; независимым strict key-login проверили
точный key-owner `codex-fethiye-admin-20261016T070953Z` и отсутствие файла.
Evidence: `.local/backups/fethiye/20261016T070953Z-admin-key-install/`.
Свежий backup после импорта:
`.local/backups/fethiye/20261016T071211Z-post-admin-key-install/`,
VERIFIED_TRANSFER; restore не испытывался. Initial/current не перезаписаны.
Откат только этого подшага: через локальный WebFig удалить SSH-key с указанным
key-owner; пароль admin не менять и не удалять другие ключи. Сейчас откат не нужен.
Следующий gate: повторный вход WebFig с MacBook в новой сессии.
Server-side VPN/маршруты и TimeWeb не менялись, tunnel inventory и recovery
generation не затронуты. При смене пароля старую запись private store отметить
как historical, не выдавать ее за актуальную; дальнейший SSH использует ключ.

Пользователь подтвердил новый браузерный вход с MacBook после установки
пользовательского SSH-ключа: WebFig PASS. Следующий подшаг: интерактивная
смена своего пароля командой `/password` в WebFig Terminal, без передачи
нового пароля в чат или вывода его агенту. До подтверждения пользователя
смену не считать выполненной. После смены нужны новый вход WebFig,
проверка key-only SSH, клиентского интернета и свежий backup.

Решение пользователя после успешного повторного WebFig-входа: «не надо -
оставим этот». Смена пароля исключена из текущего плана. Не менять его
автоматически и не запрашивать заново. Риск ранее сообщенного в чат пароля
остается; он не устранен SSH-ключом. Пароль действует для WebFig, SSH только
с паролем отклоняется, WAN firewall не расширен. Шаг 2 закрыт с этим явным
исключением, не как полное устранение замечаний аудита.

### Шаг 3: адресация

Проверить LAN/VPN/route ranges на всех затрагиваемых узлах. После выбора
свободной сети согласованно сменить bridge IP, DHCP network/pool и зависимые
правила только Фетхие; учесть старые leases. Контрольный доступ через ether1
из Deco сохранить. Проверки: MacBook получает новый адрес/gateway/DNS,
открывает HTTPS; управление доступно, пересечения с Нахимова нет.

Read-only preflight 16 октября: strict SSH к Нахимова, serial `HKM0BDXYG74`,
LAN `192.168.88.0/24`; кроме нее адреса WAN `10.12.20.168/22`, WG
`10.10.10.24/24`, `10.30.30.2/24`, `10.50.50.24/32`. Проверены destinations
всех его IPv4 routes и peer allowed-address, маршруты всех таблиц TimeWeb
host и namespace wg-relay, host-маршруты Fornex и Cenuta. Default routes
не считаются занятым LAN диапазоном. В этом объеме явных пересечений с
`192.168.89.0/24` нет; общий поиск публичного реестра также не дал назначения
этой LAN. Это не полный аудит всех контейнеров и офлайн-площадок; перед VPN
дополнительно проверить peer/namespace inventories и сохраняемые конфигурации.
На удаленных узлах изменений не было.

Фетхие: WAN `.68.117`, LAN `.88.1`, единственный pool `.88.10-.88.254`,
DHCP network `.88.0/24`, gateway/DNS `.88.1`; firewall input по-прежнему
пускает TCP 22/80 с admin Mac `.68.115`. Четыре dynamic bound leases:
iPhone `.251`, Watch `.253`, MacBookAir `.252`, безымянный клиент `.254`.
Смена LAN затронет только клиентов MikroTik; Deco не меняется. До выполнения
согласовать короткое окно и обновление DHCP на MacBook; доступ агента через
ether1 сохранить. Новая LAN еще не назначена, шаг не принят.

Лог 10:43-10:46 Europe/Istanbul: пользователь разрешил окно смены LAN.
Дополнительно просмотрены 47 сохраненных config-файлов: совпадения
`192.168.0.0/16` относятся к Local_Networks / policy lookup / private-address
guards Нахимова и private-block Xray, а не к назначенной LAN. Их не удаляли;
влияние guards на будущие VPN-сценарии проверяется отдельно в шагах 5-8.
Fresh pre-backup `.local/backups/fethiye/20261016T074328Z-pre-lan-renumber/`
VERIFIED_TRANSFER. До записи сверены serial и точный export против этой копии.

Выполнены ровно три изменения persistent export: bridge IP/network,
default-dhcp pool, DHCP network/gateway/DNS. Новый bridge `192.168.89.1/24`,
pool `.89.100-.89.199`, gateway/DNS `.89.1`; старого `.88.1` нет.
Сравнение export до/после подтвердило только этот diff. Удалены только старые
dynamic leases сервера defconf, чтобы клиенты получили новые при DHCP renewal.
Wi-Fi, firewall, WAN, пароли и удаленные узлы не менялись.
Повторный strict SSH через `.68.117` успешен, WAN сохранился; ping Deco и
`1.1.1.1` по 3/3, DNS разрешается. Это не клиентская приемка.

Evidence и точный scoped rollback:
`.local/backups/fethiye/20261016T074605Z-lan-renumber-change/`.
Fresh post-backup `.local/backups/fethiye/20261016T074642Z-post-lan-renumber/`,
VERIFIED_TRANSFER, restore не выполнялся. В `.local/config/hosts/fethiye/current/`
материализованы три файла этого snapshot с проверкой старой canonical копии;
initial не изменен. Все evidence/masters внесены в private store.
Новых VPN identities, серверных маршрутов и controller changes нет; поэтому
серверные BTH/monitoring contracts и recovery generation не публиковались.

Следующий gate: пользователь переподключает MacBook к `MikroTik-12F5ED`;
подтверждаем новый lease `.89.x`, WebFig `192.168.89.1` и внешний HTTPS.
До этого шаг 3 не завершен и шаг 4 не начинается. При необходимости откатить
только три записанных settings через неизмененный WAN SSH; после отката
клиентам также понадобится DHCP renewal. Не применять общий binary restore.

Клиентская проверка после переподключения: пользователь подтвердил
восстановление интернета. Live lease `MacBookAir`, MAC `A2:C1:5E:29:F5:8E`,
`192.168.89.197`, bound; wifi1 5 GHz, -61 dBm, ft-wpa3-psk. Watch и iPhone
тоже получили новые адреса `.89.199` и `.89.198`. Безымянный клиент остается
в Wi-Fi registration table, но нового DHCP lease пока нет; его прикладная
связь не проверена. Gateway/DNS DHCP `.89.1` подтверждены на роутере.
До следующего шага требуется подтвердить локальный WebFig-вход с MacBook
по `http://192.168.89.1`; Интернет не подменяет эту проверку управления.

Пользователь подтвердил вход в WebFig по новому локальному адресу.
Клиентская приемка шага 3 завершена: DHCP, внешний сайт и управление PASS.

### Шаг 4: базовая защита

Отдельно сменить country, отдельно отключать только ненужные сервисы,
настроить синхронизацию времени. Не менять SSID/пароль Wi-Fi без необходимости.
Проверки после каждого подшага: регистрация MacBook, реальный HTTPS, strict SSH,
действующие firewall-ограничения; не отключать рабочий канал управления.

Read-only Wi-Fi preflight: обе radio сообщают current-country Latvia;
профили configuration/channel отсутствуют, параметры заданы на интерфейсах.
wifi1 running, `5500/ax/Ceee/D`, четыре клиента; wifi2 running,
`2472/ax/eC`, клиентов нет. У wifi1 текущий канал DFS: после изменения региона
готовность радио может потребовать ожидания, не обещать восстановление за
несколько секунд. Точная длительность зависит от выбранного канала и CAC.
Не выполнять frequency-scan и не отключать DFS как диагностический обход.
До записи country согласовать окно прерывания Wi-Fi; имя/пароль, ширину и
автовыбор канала этим подшагом не менять. Новый backup обязателен.
Синтаксис country проверен по [RouterOS WiFi](https://help.mikrotik.com/docs/spaces/ROS/pages/224559120/WiFi).

Лог 11:27-11:32 Europe/Istanbul: пользователь разрешил переключение региона.
Pre-backup `.local/backups/fethiye/20261016T082742Z-pre-wifi-country/`,
VERIFIED_TRANSFER. Первое чтение остановилось до изменения: shell parser не
учел RouterOS backslash-continuation. После учета продолжений записан Turkey
на wifi1/wifi2. Сравнение ошибочно сочло новую группировку полей drift:
`configuration.country=Turkey .mode=ap` вместо `configuration.mode=ap`.
Попытка автоматического rollback через пустой country была отклонена RouterOS;
live-состояние осталось Turkey. Повторную запись и отключение DFS не выполняли.

Независимый read-back с раскрытием dot-shorthand подтвердил точный persistent
diff: только `configuration.country=Turkey` на двух интерфейсах. SSID,
passphrase, security, width, skip-dfs, LAN, WAN, firewall не менялись.
Оба effective country Turkey, state running. Каналы после автоподбора:
wifi1 `5500/ax/Ceee/D`, wifi2 `2412/ax/Ce`. Router ping Deco и `1.1.1.1` по
3/3, DNS разрешается, повторный strict key SSH успешен. Клиентов в регистрации
на контрольном чтении не было: MacBook должен переподключиться и пройти приемку.

Evidence: `.local/backups/fethiye/20261016T082955Z-wifi-country-change/`,
включая описание отказов helper и независимую verification.json.
Writer помечен retired и останавливается до записей при повторном запуске.
Scoped rollback в evidence исправлен на явный Latvia, а не пустую строку;
он восстанавливает прежний effective region, не исходное отсутствие поля.
Это только аварийный reference, не рекомендация эксплуатации в Турции.
Preventive rule: до следующих live writers отдельно тестировать RouterOS
continuations/dotted namespace normalization и допустимость rollback значений;
не применять shell grammar к RouterOS export без такой проверки.

Fresh post-backup `.local/backups/fethiye/20261016T083227Z-post-wifi-country/`,
VERIFIED_TRANSFER, без restore drill; current материализован из него,
initial не изменен. Masters/evidence сохранены в canonical private store.
Дальнейшие сервисные/NTP подшаги не начинать до клиентской проверки MacBook.

Приемка country: пользователь подтвердил работу внешнего сайта. Live в 11:41:
MacBook MAC `A2:C1:5E:29:F5:8E`, lease `.89.197` bound, wifi1, -54 dBm,
ft-wpa3-psk. Оба радио effective Turkey. Неизвестный Wi-Fi-клиент получил
lease `.89.196`; его принадлежность/прикладная приемка не установлены.

Сервисы, отдельный подшаг 11:42-11:43: active sessions до изменения только
SSH, зависимости от FTP/Telnet/API в текущем пилоте не выявлены. Fresh pre
VERIFIED_TRANSFER: `.local/backups/fethiye/20261016T084217Z-pre-services/`.
Отключены только ftp, telnet, api, api-ssl. SSH, www и winbox enabled;
www-ssl остался disabled. Export diff проверен: ровно четыре service disabled
entries, иных изменений нет. Повторный strict key SSH, SFTP read, ping Deco
и `1.1.1.1` по 3/3, DNS PASS; HTTP WAN management с admin Mac вернул 200.
Ни отсутствие TCP-сервиса на WAN за firewall, ни HTTP 200 не заменяют
клиентский WebFig-вход: он ожидается. Сканирование LAN портов с MacBook
не выполнялось; disabled flags подтверждены на самом роутере.

Evidence и scoped rollback (включить только эти четыре сервиса):
`.local/backups/fethiye/20261016T084315Z-services-change/`.
Fresh post `.local/backups/fethiye/20261016T084353Z-post-services/`,
VERIFIED_TRANSFER; current синхронизирован, initial сохранен, private store
проверяется. Сетевые и VPN identities, маршруты, firewall, Wi-Fi не менялись.
NTP и SSH strong-crypto еще не менялись; шаг 4 целиком не закрывать.
Основание: [RouterOS Services](https://help.mikrotik.com/docs/spaces/ROS/pages/103841820/Services).

Пользователь подтвердил WebFig-вход после отключения сервисов и разрешил
продолжить. Подшаг services принят; пароль admin оставлен по его решению.

NTP, 11:49-11:51 Europe/Istanbul: исходно client disabled, server list пуст;
оба FQDN турецкого NTP Pool разрешаются. Fresh pre-backup
`.local/backups/fethiye/20261016T084902Z-pre-ntp/`, VERIFIED_TRANSFER.
Включен только NTP client, добавлены `0.tr.pool.ntp.org` и `1.tr.pool.ntp.org`
с уникальным comment `codex-fethiye-ntp-20261016T085018Z`.
Export diff проверен: ровно client enabled=yes и две server entries;
остальная конфигурация совпала. Через 10 секунд status synchronized;
в последующем чтении synced-server `0.tr.pool.ntp.org`, stratum 3,
system-offset 66.762 ms (моментное значение, не SLA).

Timezone Europe/Istanbul, autodetect и IP Cloud update-time=yes оставлены
без изменений. NTP server не включен, DHCP NTP options не добавлялись,
разрешений входящего UDP 123 нет. Обычный public NTP без authentication/NTS;
это не криптографически удостоверенный источник времени.
Strict key SSH reconnect, router ping Deco и `1.1.1.1` по 3/3, DNS PASS,
HTTP admin-WAN 200, MacBook lease `.89.197` сохраняется. Wi-Fi/маршруты,
firewall, пароли и удаленные узлы не менялись. Новый браузерный тест с
MacBook после NTP пока ожидается; reboot acceptance не выполнялась.

Evidence/точный rollback: `.local/backups/fethiye/20261016T085018Z-ntp-change/`.
Откат отключает NTP client и удаляет только две добавленные записи по их
уникальному comment; остальные настройки времени/сети не затрагивать.
Fresh post `.local/backups/fethiye/20261016T085126Z-post-ntp/`, VERIFIED_TRANSFER;
current материализован из него, initial сохранен, private store обновлен.
Профили VPN/monitoring и серверные recovery contracts не менялись.
Источники: [RouterOS NTP](https://help.mikrotik.com/docs/spaces/ROS/pages/40992869/NTP),
[NTP Pool Turkey](https://www.ntppool.org/zone/tr).

Пользователь подтвердил открытие внешнего сайта после NTP. Подшаг принят.
11:55-11:57 Europe/Istanbul: fresh pre-backup
`.local/backups/fethiye/20261016T085553Z-pre-ssh-crypto/`; включен только
`/ip ssh strong-crypto=yes`. Export delta проверен, ключ host не менялся.
Новый key-only strict SSH и SFTP прошли; согласованы aes192-ctr и
hmac-sha2-256 в обоих направлениях. NTP synchronized, router ping 3/3,
MacBook lease `.89.197`, HTTP с admin Mac 200. Wi-Fi/LAN/firewall/пароли
не менялись. Физическая проверка этого подшага - новое реальное SSH/SFTP
соединение, не только чтение установленного флага.
Evidence/rollback: `.local/backups/fethiye/20261016T085647Z-ssh-crypto-change/`.
Fresh post/current `.local/backups/fethiye/20261016T085739Z-post-ssh-crypto/`,
VERIFIED_TRANSFER; private store обновлен, initial сохранен.

Шаг 4 закрыт как минимальная подготовка к VPN. Не означает полного hardening:
пароль сохранен по решению пользователя, WebFig остается HTTP; USB/media/SMB
defaults не менялись (дисков в исходном аудите нет), обновление RouterOS и
расширенные service restrictions требуют отдельного changeset. Не расширять
этот этап до незапрошенной перенастройки всего роутера.

### Шаг 5: серверная подготовка

Прочитать live routing/firewall/identities и recovery contracts Нахимова и
TimeWeb. Подготовить точный diff, адреса, порты, identities, обратные маршруты,
rollback и свежие schema-3 backups. Не переиспользовать `wg-home` вслепую.
Существующие VPN и Smart Split проверить до/после; запрещены retired writers,
общий flush и пересоздание контейнеров. Если нужен новый guarded writer,
сначала реализовать и проверить его, а не обходить защиту ручными правками.

Read-only baseline 12:04-12:06 Europe/Istanbul:
`.local/backups/site-to-site/20261016T090427Z-preflight/`.
Собраны export Нахимова, routing/firewall TimeWeb host и wg-relay, AllowedIPs,
службы, listeners и проверки contracts. Runtime recovery check PASSED,
BTH --check PASSED, monitoring guard check PASSED. Реальные units называются
`timeweb-runtime-recovery.*` и `vpn-uplink-console.service`; не угадывать
имена из каталога `/opt`. Collector/exporter/console active.
Metrics observation_fresh=1, HTTPS probe_valid=1 для обоих upstream.

Первый GET console `/state` с timeout 10 s истек. Повтор с 90 s вернул полный
HTML fragment. Попытка разобрать его как JSON отказала; сверка с исходником
подтвердила штатный HTML fragment, затем применен HTMLParser без вывода CSRF.
Обе upstream cards ok и controls enabled; FLEX 3/3 routes ready, 0 active,
3 inactive, 0 unknown. Это реальные данные из service context, не только
root CLI. Два post-deploy collector cycles этим срезом не подменяются.

Предлагается [изолированный host-WG пилот](../architecture/Fethiye_TimeWeb_Pilot_Changeset.md)
вне защищенного wg-relay, сначала только TimeWeb <-> Фетхие по служебным IP;
Нахимова на первом плече не менять. Candidate network `10.60.60.0/29`,
UDP 51860 не заняты в проверенных routes/listeners; это не окончательное
выделение до расширенной сверки и scope approval. Host ip_forward=1, поэтому
до поднятия peer нужен отдельный deny-transit/deny-host-services guard.
Существующий `inet reality_fornex`, BTH/FLEX и protected namespace не менять.

На момент этого read-only среза серверных записей/новых VPN identities не было.
Последующее согласование scope, writer, deploy/rollback diff, расширенная
проверка диапазонов, fresh schema-3 backup и monitoring coverage выполнены;
результат следующего подшага записан ниже.

### Шаг 6: первое VPN-плечо

Создать только согласованное плечо Фетхие -> TimeWeb, без изменения default
маршрута клиентов. Проверки: handshake плюс двусторонние пакеты по туннельным
адресам; интернет MacBook остается местным. Синхронизировать inventory,
contracts и monitoring согласно [agent workflow](../operations/agent-workflow.md).

16 октября: изолированный пилот применен и технически проверен. На TimeWeb
сначала guard, затем host WG; Фетхие `.3/29` к hub `.1/29`, keepalive 25,
MTU 1420. Новый ICMP-only контур не содержит LAN/default routes или NAT.
Первый ping блокировался неправильным порядком собственных input rules;
после отказа move `cannot move builtin` правила переведены в собственную
цепочку без изменения старого FastTrack/firewall. Повтор: пакеты обе стороны
и 1400 bytes PASS, TCP 22 закрыт с ростом counters, host transit закрыт с
реальными тестовыми пакетами. Временный test namespace/veth удален.

Старые snapshots/identities/contracts unchanged, runtime/BTH/monitoring/pilot
checks PASS. Два свежих валидных collector cycles для Fornex/Cenuta,
Prometheus свежесть/peer/rate valid=1; Grafana импортировала device resources.
Авторизованный Grafana UI render отдельно не проверялся. Новый device/source
не входит в переключаемый FLEX fleet, его console permissions не расширены;
существующий fleet из namespace консоли 3/3 ready, HTTP cards/controls PASS.

TimeWeb post-backup `2026-10-16T101524Z_current-config` VERIFIED;
Фетхие `20261016T102035Z-post-s2s-pilot` VERIFIED_TRANSFER, current обновлен,
initial сохранен. 66 profiles / 22 devices; прежние 65 profiles неизменны.
Пользователь подтвердил внешний HTTPS на MacBook после VPN, затем открытие
страницы WebFig по `http://192.168.89.1`. Это проверка доступности страницы,
не новая проверка авторизации. Шаг 6 закрыт в служебном ICMP-only объеме.
Reboot/restore drill, публичный IP клиента и полный клиентский
egress/межплощадочный тест не проверены и не объявлены принятыми.
[Checkpoint](../history/2026-10-16-fethiye-timeweb-pilot.md).

### Шаг 7: две LAN

Подшаг 7A применен 16 октября: второе новое плечо Нахимова -> изолированный
hub, адрес `.2/29`. Старый BTH/wg-home не переиспользован. Двусторонний
ICMP/1400, отрицательные TCP/transit тесты, сохранность первого плеча,
мониторинг и post-backups проверены. Обычный HTTPS
на MacBook после изменения подтвержден пользователем. [Changeset](../architecture/Nakhimova_TimeWeb_Second_Leg_Changeset.md),
[checkpoint](../history/2026-10-16-nakhimova-second-leg.md).

Подшаг 7B применен по [точному changeset](../architecture/Site_to_Site_LAN_Changeset.md):
только `192.168.88.0/24` ↔ `192.168.89.0/24`, без NAT и изменения default.
Router LAN-source ping 3/3 в обе стороны, 1400 байт; обе служебные связи и
местный интернет роутеров сохранены. TCP управления закрыт с ростом counters;
VPS и чужой transit не получили доступа. Пользователь подтвердил
`ping -c 3 192.168.88.1` с MacBook на Wi-Fi MikroTik: ответы без потерь.
Первоначальный входящий ping к `.89.197` не ответил ни с Нахимова, ни локально
с Фетхие; причину на MacBook не устанавливаем без дополнительной диагностики.
Это не полная приемка приложений, входящих сервисов MacBook или discovery.
Deco, DNS и Internet egress не менялись; VPN-приложения на MacBook отдельно
не проверялись. [Checkpoint и post-backups](../history/2026-10-16-site-to-site-lan.md).

### Шаг 8: интернет-выход

Первый, исторический Local-подшаг: пользователь подтвердил выключенные VPN-приложения и сообщил исходный public
IP MacBook; значение сохранено в private evidence, не исправлялось по старому
паспорту Deco. [Отдельный changeset](../architecture/Site_to_Site_Egress_Changeset.md)
развернут в Local: IPIP внутри WG активен, 10 Remote controls выключены;
DHCP lease остается dynamic, прежние default/NAT/DNS/Wi-Fi/Deco сохранены.
IPIP/LAN/service pings 1400 bytes по 3/3 в обе стороны; TCP управления и
чужой transit закрыты с ростом drop counters. Пользователь подтвердил
`example.com` после изменения. Внешние пробы Нахимова дали также потери
4/10 к `1.1.1.1`, 1/5 к `9.9.9.9`, WAN gateway 5/5. Последующий 3/3 не
отменяет это предупреждение. Remote/его fail-closed и приложение не приняты.
Отдельно выявлено расхождение двух DNS-ответов `1.1.1.1` с TLS reference;
три ответа `9.9.9.9` совпали. Только два выключенных DNS targets пилота
изменены на `9.9.9.9`; общий DNS не менялся. На этом историческом срезе
lease еще был dynamic; следующий протокол описывает последующие пробы.
[Текущий протокол](../history/2026-10-16-egress-local.md),
[предварительная подготовка](../history/2026-10-16-egress-preparation.md).

18:27-18:34 Europe/Istanbul: первая ограниченная проба завершилась автоматическим
Local. Пользователь сообщил прежний IP и до, и после; эта приемка не пройдена,
причина расхождения не установлена. Затем пользователь подтвердил gateway
`.89.1` и собственный IP `.89.197`, разрешил повторное переключение.
18:49-18:55: повторный Remote дал `5.18.141.112` в terminal `curl -4`
с обычной TLS-проверкой и без proxy; `example.com` открылся в браузере.
После явного Local тот же terminal HTTPS дал `194.61.140.217`.
Ограниченное переключение IPv4/HTTPS принято, MacBook оставлен Local.
Lease `.89.197` закреплен static без смены DNS/gateway; другие устройства,
WG profiles и Deco не менялись. [Evidence, backups и ограничения](../history/2026-10-16-egress-trials.md).

Сначала на MacBook испытать Local и Нахимова: внешний IP, DNS, HTTPS,
нужное пользователю приложение. Испытать обратный выход через Фетхие на
одном согласованном клиенте Нахимова. Затем проверить взаимный Remote site
без петель и fail-closed при потере удаленного пути. Не менять политику всех
устройств. Учесть существующие клиентские VPN на MacBook при сравнении путей.

### Шаг 9: резервирование

Выбрать реальный доступный TLS endpoint, проверить сертификат/имя; не занимать
REALITY TCP 443. Плечи резервировать независимо. Разделять проверки транспорта,
LAN и удаленного интернет-выхода. Стартовые критерии испытаний: три отказа с
интервалом 10 секунд с учетом timeout, возврат после 2-3 минут устойчивой связи.
Проверить реальным трафиком отказ UDP, восстановление, отсутствие flapping.
Два протокола на TimeWeb не резервируют отказ самого TimeWeb или его IP.

### Шаг 10: приемка этапа A

Согласованно проверить reboot, переподключение WAN, большие пакеты/MTU,
скорость и нужные приложения. Проверить DNS/IPv6 и оба режима выхода.
Сверить masters/runtime, registry, inventory, BTH и monitoring contracts,
консоль и runtime recovery; получить два свежих валидных collector cycles.
Создать verified backup; записать все непроверенные пункты, не объявлять их
успешными. Только после приемки расширять использование по выбору владельца.

### Шаг 11: прямой канал

Отдельное решение после этапа A. Подтвердить доступность UDP и право изменения
Deco; при их отсутствии сохранить рабочий A и не обходить ограничение владельца.
Прямой путь квалифицировать по полезному трафику; затем испытать уход на
TimeWeb и возврат с сохранением выбранного интернет-выхода.

## Открытые условия, не блокирующие шаг 1

- Свободный LAN диапазон и VPN адреса определяются live-аудитом до назначения.
- Способ безопасной ротации управления фиксируется до шага 2.
- Какие приложения и сервисы проверяем между LAN, уточняется до шага 7.
- TLS endpoint и необходимость дополнительных ресурсов согласуются до шага 9.
- Вариант B не разрешает сейчас менять Deco: потребуется отдельное согласование.

## Хранение и отчетность

Пароли, private keys, полные exports и backups только в `.local` и portable
private store; в плане только sanitized результаты. Начальная копия от
16 октября остается неизменной. Обновлять статусы и лог сразу после проверки,
различать Router PASS и клиентскую приемку. Документация без commit/push,
если пользователь отдельно не попросит.
