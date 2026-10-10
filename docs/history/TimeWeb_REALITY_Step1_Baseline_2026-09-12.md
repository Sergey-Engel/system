---
type: implementation-log
status: client-compatibility-pending
created: 2026-09-12
updated: 2026-09-12
parent: "[TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>)"
---

## Шаг 1: baseline и совместимость

Разрешение пользователя: выполнить только шаг 1 архитектурного плана. Окно серверных проверок: **2026-09-12 15:13:04-15:19:43 UTC**, 18:13-18:19 Europe/Istanbul.

**Итог:** серверный read-only preflight завершен. Доступны все три VPS и MikroTik Нахимова, 11. Выбраны кандидат версии Xray, REALITY target и три адреса. После первоначального скриншота MacBook с 5.0.0.5 пользователь сообщил об обновлении до предложенной **5.0.1.5** и указал **5.0.2.1** на **iPhone (iOS)**. Сбор версий клиентов выполнен; импорт и соединение еще не проверены, совместимость клиентов не принята. Разрешения на установку или серверные изменения нет.

## Артефакты и границы

Локальный master: services/transport/timeweb-reality (source reference not migrated).

- `manifest.json`: выбранные параметры, проектные резервы, статусы проверок, ограничения, исходные хеши и открытые условия.
- `baseline_20260912T151304Z.json`: датированные sanitized выводы проверок. Это **не восстанавливаемый backup**.
- Ключи, UUID, client profiles, исполняемые deployment scripts и серверные конфиги нового решения **не создавались**.
- На серверах не выполнялись установки, перезапуски, изменения firewall/routes/rules/peers. Файлы WG на трех VPS сверены по SHA-256 до/после: совпали.
- Не возобновлялись мониторинг, Grafana, Prometheus и SQL-синхронизация. Новые папки созданы только для реально записанных файлов.
- Полные конфиги и секреты не выводились. Большой справочник RU IP не включен в evidence; необходимые nft chains записаны отдельно.

## Последовательность действий

1. Прочитаны архитектура, правила доступа и правила разделения Obsidian/System. Подтверждена штатная локальная `/Users/sergey/.venv`.
2. Через OpenSSH, `BatchMode=yes`, `StrictHostKeyChecking=yes`, `UpdateHostKeys=no` выполнены краткие проверки TimeWeb/Fornex/Cenuta. Для Cenuta сохранен отдельный `known_hosts_cenuta`.
3. На TimeWeb прочитаны ресурсы, TCP listeners, Docker inventory, WG peers, routes 100/200/300, policy rules, NAT/FORWARD и relevant `ru_bth` chains.
4. На exit-хостах прочитаны runtime WG peers и безопасные поля постоянных конфигов; сопоставлены адреса и public keys. Ни один peer не менялся.
5. SSH до MikroTik выполнен через существующий namespace TimeWeb: локальный SSH-клиент использовал ProxyCommand с `nsenter -t 1181 -n nc -w 10 10.30.30.2 22`. Ключ MikroTik остался на Mac, agent forwarding не использовался, trust проверен по существующему HostKeyAlias `192.168.88.1`.
6. Роутер идентифицирован как Нахимова hAP ax3 по модели/serial. Прочитаны WG Allowed Address, NAT, mangle/filter, FastTrack, address lists, main default, обратная connected route и LAN/WAN membership.
7. С TimeWeb проверены DNS, TCP, TLS 1.3, сертификат, ALPN h2 и HTTP для REALITY target, затем повторена проверка по закрепленному IP.
8. С Fornex/Cenuta выполнены ограниченные HTTPS GET к независимым сайтам. Ответы HTTP отделены от TCP/TLS и timeout.
9. Из `wg-relay` выполнены короткие ICMP пробы до соседей с явным интерфейсом. При единичном пропуске Cenuta выполнена одна повторная проба.
10. В конце повторно сверены хеши конфигов и времена старта контейнеров, прочитаны handshake/traffic counters. Новые параметры записаны только локально.

ProxyCommand выше является **описанием этого запуска**, а не вечной командой: PID контейнера каждый раз определяется заново. Не отключать host-key checking и не выбирать Нахимова по совпадающему LAN IP без подтвержденного пути и идентификации модели.

## Ресурсы и сервисы

| Узел    | RAM available | Свободно на диске | Подтверждение                                            |
| ------- | ------------- | ----------------- | -------------------------------------------------------- |
| TimeWeb | 1461 MiB      | 18 GiB            | 1 vCPU, wg-relay CPU 0,14%, память 39,21 MiB             |
| Fornex  | 1414 MiB      | 11 GiB            | 1 vCPU, wg-exit и все существующие Amnezia containers Up |
| Cenuta  | 1645 MiB      | 44 GiB            | 1 vCPU, wg-quick@wg-cenuta и nftables active             |

TimeWeb: uptime 64 дня; `wg-relay` PID 1181, StartedAt `2026-07-10T00:10:37.662464526Z` сохранились. TCP/443 и 127.0.0.1:10831 не имеют слушателей. Входящие TCP/443 с клиентской площадки **не проверены**, потому что новый listener отсутствует. `vpn-uplink-pilot` и `vpn-uplink-exporter` inactive/disabled; `systemctl --failed` не вывел units. В PATH TimeWeb Xray не найден; это не полный поиск всех бинарников диска.

Fornex: `wg-exit` PID 2481, StartedAt `2026-08-26T07:25:48.81006629Z` сохранились. Существующая Amnezia использует Xray **25.8.3**, commit `bd86732`, Go 1.24.5; ее TCP/443 не конфликтует с TCP/443 другого VPS TimeWeb. Эту установку не обновлять в рамках нового входа.

Плановый общий бюджет двух новых процессов: MemoryHigh 384 MiB, MemoryMax 512 MiB, CPUQuota 60% одного ядра, запас ОС не ниже 512 MiB. На момент снимка 1461 - 512 = **949 MiB** остаются вне максимального бюджета новых процессов, до прочих колебаний нагрузки. Пилот по RAM/диску допустим; производительность userspace WG на одном CPU не измерена.

## Выбранная версия и формат

Кандидат для изолированных тестов: **Xray v26.3.27**, commit `d2758a023cd7f4174a5a5fa4ff66e487d4342ba0`.

На момент проверки GitHub API `releases/latest` вернул этот release с `prerelease=false`; более новые видимые releases, включая v26.9.9, помечены prerelease. Это основание для консервативного кандидата, а не обещание отсутствия уязвимостей или полной совместимости. Перед staging повторить просмотр advisories/release notes, не переключать версию автоматически.

Архив `Xray-linux-64.zip`: 21 136 402 bytes; ожидаемый SHA-256 из GitHub API:
`23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae`.
Архив **не скачивался и не запускался**, digest фактического скачанного файла еще не сверялся.

В исходниках выбранного tag подтверждены:

- `infra/conf/wireguard.go`: поля `noKernelTun`, `secretKey`, `address`, peer `preSharedKey`, `keepAlive`, `allowedIPs`.
- `proxy/wireguard/config.go`: `NoKernelTun=true` явно выбирает gVisor userspace stack.
- `infra/conf/transport_internet.go`: aliases `tcp/raw`, `target/dest`, `publicKey/password`.
- `infra/conf/vless.go`: `decryption=none` и конфигурационные поля VLESS.

Для исходного совместимого client JSON выбрать `network=tcp`, `security=reality`, `flow=xtls-rprx-vision`, `encryption=none`, `realitySettings.publicKey`; на новом сервере `target`. Финальная приемка парсера/бинарника и обмена не выполнена. Новые PQ/Mux/экспериментальные параметры не включать.

Mac Mini: AmneziaVPN `CFBundleShortVersionString=5.0.0`, `CFBundleVersion=5`. Точная версия встроенного Xray не определена; отдельный бинарник Xray внутри app не найден. Эти plist поля не доказывают полный четырехкомпонентный release Amnezia. На момент серверного аудита версии на MacBook и телефоне не были известны; последующее подтверждение MacBook записано ниже отдельно.

[Официальный release](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27), [поля WG выбранного tag](https://github.com/XTLS/Xray-core/blob/v26.3.27/infra/conf/wireguard.go), [выбор userspace](https://github.com/XTLS/Xray-core/blob/v26.3.27/proxy/wireguard/config.go), [REALITY/transport aliases](https://github.com/XTLS/Xray-core/blob/v26.3.27/infra/conf/transport_internet.go), [форматы импорта Amnezia](https://docs.amnezia.org/documentation/supported-configuration-formats/).

## REALITY target

Кандидат: `www.microsoft.com`, закрепленный IPv4 **23.12.158.97:443**, SNI `www.microsoft.com`.

- 15:14:57 UTC: DNS вернул этот IP; HTTP 200, HTTP/2; TCP 13 ms, TLS 51 ms, полный GET 121 ms.
- 15:16:32 UTC: запрос через `--resolve` к тому же IP дал HTTP 200, HTTP/2, полный GET 115 ms.
- OpenSSL с проверкой сертификата и hostname: TLS 1.3, X25519, `TLS_AES_256_GCM_SHA384`, ALPN h2, Verify return code 0.
- Endpoint нужно перепроверить перед созданием allowlist. Это не постоянный IP Microsoft и не гарантия доступности с любой сети.
- Выбор target не означает разрешения прямого выхода пользовательского трафика. Служебное исключение будет ограничено новым UID/IP/портом и согласовано перед применением.
- Это CDN-адрес: отдельно учитывать риск использования публичного REALITY fallback посторонними; не обещать, что выбор известного домена сам по себе обеспечивает неотличимость.

[Требования REALITY к target](https://github.com/XTLS/REALITY#readme), [семантика target и ограничения](https://xtls.github.io/en/config/transports/reality.html).

## Адреса и постоянные конфиги

| Выход  | Проектный резерв | Серверная сторона и persistent path                      |
| ------ | ---------------- | -------------------------------------------------------- |
| Fornex | 10.20.0.3/32     | wg-exit / wg0, /opt/wg/config/wg_confs/wg0.conf          |
| Cenuta | 10.40.40.3/32    | wg-cenuta, /etc/wireguard/wg-cenuta.conf                 |
| BTH    | 10.30.30.5/32    | wg-relay / wg-home, /opt/wg/config/wg_confs/wg-home.conf |

Резерв существует **только в проектном manifest**; никто не получил новые ключи и адреса на сервере. В проверенных runtime peers, активных persistent configs и локальных `.conf` из .local/clients и System/Mikrotik/current точных занятых адресов не найдено. Это не блокировка других администраторов: сверка непосредственно перед записью обязательна.

У BTH существующий peer MikroTik уже имеет 0.0.0.0/0. Новый более специфичный .5/32 должен направлять ответы к worker; наличие default AllowedIPs у домашнего peer само по себе не является конфликтом.

На Fornex обнаружены старые generated peer1-peer5 с адресами 10.13.13.2-.6; они не пересекаются с новым .3 в 10.20.0.0/24. Их не меняли и не удаляли.

У существующего Fornex peer persistent Endpoint указывает TimeWeb:51820, а runtime изучил TimeWeb:55839. Это исходное состояние, а не изменение этого шага. При добавлении peer не переносить весь старый конфиг в runtime слепо и не исправлять существующий Endpoint попутно.

## BTH: что подтверждено и чего не хватает

Роутер: hAP ax3, модель `C53UiG+5HPaxD2HPaxD`, serial `HKM0BDXYG74`, RouterOS 7.22.1. WG адрес 10.30.30.2/24; WAN ether1 имеет частный адрес 10.12.20.168/22, main default через 10.12.20.1. Наблюдаемый внешний endpoint дома на TimeWeb: 5.18.237.241; независимый HTTP echo внешнего IP из дома не выполнялся.

- TimeWeb rule `iif wg-home -> table 300`, default `dev wg-home`. Read-only `ip route get 1.1.1.1 from 10.30.30.5 iif wg-home` выбирает wg-home/table 300. Это lookup, не передача от нового peer.
- На MikroTik Allowed Address TimeWeb включает 10.30.30.0/24 и 0.0.0.0/0; есть connected return route для .5 через wg-home.
- Есть WAN masquerade, включая правило для 10.30.30.0/24. Расширять NAT ради .5 не требуется по текущему снимку.
- Bypass FastTrack для WG-Home стоит до самого FastTrack.
- VPN_Devices пуст; CENUTA_Devices содержит только 192.168.88.35/.252/.11/.28. Новый source .5 не попадает в эти policies.
- **wg-home входит в LAN list MikroTik.** Без отдельного запрета новый peer мог бы получить нежелательный доступ к роутеру/LAN. Защита нового /32 в INPUT/FORWARD relay обязательна до активации.
- Два старых MSS clamping правила BTH отключены. Не включать их попутно: большие ответы/upload будут отдельным MTU/MSS тестом.
- По текущим данным изменение Allowed Address/NAT MikroTik для .5 не требуется. Это не отменяет проверку защит и реального full-route до публикации BTH профиля.

## Сетевые пробы и ограничения вывода

| Проба                        | Результат                                    |
| ---------------------------- | -------------------------------------------- |
| TimeWeb -> Fornex 10.20.0.2  | 2/2 ICMP, среднее 56,1 ms                    |
| TimeWeb -> Cenuta 10.40.40.1 | 1/2 ICMP, затем 3/3, RTT около 103 ms        |
| TimeWeb -> BTH 10.30.30.2    | 2/2 ICMP, среднее 3,64 ms                    |
| Fornex -> Google             | HTTP 204, 56 ms                              |
| Fornex -> Speedtest          | HTTP 200, 416 ms                             |
| Cenuta -> Google             | HTTP 204, 328 ms                             |
| Cenuta -> Speedtest          | HTTP 200, 666 ms                             |
| Fornex/Cenuta -> Microsoft   | TCP/TLS успешны; HTTP не ответил за 8 секунд |

Один пропуск в пяти ICMP-пробах Cenuta нельзя превращать в оценку устойчивой доли потерь. Причина не установлена. Таймаут Microsoft после успешного TLS на двух exit-хостах не доказывает блокировку WG или полный отказ Интернета. Диагностика HTTP-цели остается отдельной от живости хоста и handshake.

Свежие handshake существующих домашних wg0/wg-clients peers сохранились в конце. **Прикладной regression с реального старого клиента, новый VLESS-сеанс, новый egress /32, DNS/IPv6 leak-tests и нагрузка не выполнялись.** Пакеты коротких ICMP/SSH/HTTPS проверок не являются доказательством работоспособности всех пользовательских профилей.

## Технические замечания выполнения

- urllib в штатной Python .venv сообщил `CERTIFICATE_VERIFY_FAILED` для GitHub. Системный curl с обычной проверкой TLS успешно прочитал API; JSON разбирался Python из той же .venv. CA store, пакеты и verify настройки не менялись.
- Попытка прочитать версию Xray на Fornex по предполагаемому /opt/amnezia/xray/xray не нашла файл. Через command -v найден /usr/bin/xray, версия прочитана; контейнер не перезапускался.
- Для URL с query string требуется shell quoting; один discovery-вызов остановлен zsh до запроса, исправлен кавычками. Для большой nft таблицы вывод был избыточным; использованы отдельные chains без копирования RU prefix set.
- Возврат exit 1 у command -v/getent/rg без совпадений означает отсутствие найденного объекта, а не отказ сервера. Итоги определялись по отдельным результатам, не по одному общему exit code.

## Дополнение: версия MacBook, 12 сентября

По двум скриншотам пользователя, предоставленным в ответ на запрос версии на **MacBook Sergey**:

- Экран Contacts/About показывает установленную **AmneziaVPN 5.0.0.5**, дату сборки **Jul 26 2026**, commit **4d28f81**. Исходное вложение: `codex-clipboard-e7604f8b-3f5a-4a58-9b87-008b53161d43.png`.
- Экран обновления предлагает **5.0.1.5**, с датой release **2026-08-21T14:47:49Z**. Это предложение обновления, не установленная версия. Исходное вложение: `codex-clipboard-29d86292-9ef7-4071-8e4f-19a56f095108.png`.
- Обновление не запускалось. Скриншоты не являются разрешением на установку. Версия встроенного Xray и совместимость импорта/соединения с новым сервером из них не следуют.
- Обновлены только локальные manifest и документация; датированный серверный baseline не изменен. Данные Mac Mini не заменялись данными MacBook. На серверы в этом дополнении не подключались.

## План после получения скриншотов, до следующего сообщения

Получить у пользователя экран с точной версией AmneziaVPN на **телефоне**, указать его OS/имя устройства. Версия MacBook подтверждена, но проверка импорта и реального соединения остается отдельным этапом. Не устанавливать Xray по итогам одного read-only шага.

После фиксации клиентов предложить согласование шага 2: точный состав установки/изменений, свежие восстанавливаемые backups и rollback manifest. Дальше изолированные тесты, только затем поэтапный production pilot согласно [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>).

## Дополнение: обновление MacBook и версия iPhone, 12 сентября

Запись: **2026-09-12 15:40 UTC**. Пользователь сообщил, что уже обновил приложение на MacBook, и указал версию на телефоне.

- **MacBook Sergey: AmneziaVPN 5.0.1.5**, то есть предложенная на предыдущем экране версия. Основание: сообщение пользователя об обновлении; новый экран About не проверялся. Старые 5.0.0.5, дата сборки и commit 4d28f81 сохранены как история, не как текущие параметры.
- **iPhone: AmneziaVPN 5.0.2.1**, со слов пользователя. Платформа iOS; ее версия и точная модель iPhone не сообщены. Номер 5.0.2.1 относится к приложению, не к iOS.
- Агент обновил только локальный manifest и архитектуру/журнал. Приложения обновлял пользователь; серверные установки, новые подключения и изменения конфигурации не выполнялись. Датированный baseline сохранен без изменений.
- Сбор версий двух клиентов завершен. Версии встроенного Xray, импорт и реальное соединение еще не проверены и не объявляются совместимыми только по номеру приложения.

**Следующее действие:** согласовать шаг 2 по архитектуре: точные объекты изменения, свежие восстанавливаемые backups и rollback manifest. До согласования не устанавливать Xray и не менять peers/firewall. Просмотр версий не заменяет изолированные и последующие клиентские тесты.
