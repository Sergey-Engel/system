---
type: quick-guide
status: runtime-unverified
updated: 2026-09-23
---

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.


## Назначение и статус

Локальные пробы интернет-доступа **самого Mac**. Профили Fornex Amnezia,
Cenuta и другие имена являются метками/историческими наблюдениями, а не
указанием, какой VPN обязан быть активен сейчас.

Live snapshot (source reference not migrated)
от **2026-09-13 14:45:01 UTC**: аудит не обнаружил TCP listeners на проверенных
портах **3000, 9090, 9105, 19106**; порт 19107 не обследовался.
В отфильтрованном `local_launchagents` есть только приложение AmneziaVPN.
Monitoring agents не показаны, но наличие plist на диске не проверено.

**Пустой `local_docker` не означает пустой Docker.** Audit берет только
`.stdout` от `docker ps -a`, игнорирует returncode и не сохраняет stderr.
Ошибка CLI/daemon может выглядеть так же, как отсутствие контейнеров.
Returncode/stderr `lsof` тоже не сохранены: отсутствие listeners здесь
означает только «не обнаружены на проверенных портах в данном аудите».
`command missing` / `command not found` означает отсутствие инструмента,
не отказ VPN. Снимок не содержит такого сообщения в этих полях.

Второй, отдельный контур: [TimeWeb_Uplink_Pilot_Quick_Guide](<TimeWeb_Uplink_Pilot_Quick_Guide.md>).
Оба серверных monitoring units TimeWeb в этом снимке
`inactive / dead / disabled`. Это не статус клиентского VPN.

## Как устроен master

[System/vpn-connectivity](<../../services/monitoring/vpn-connectivity/README.md>)
содержит Compose, Prometheus/Grafana provisioning и `probe/host_probe.py`.

- Probe слушает `127.0.0.1:9105/metrics`.
- Prometheus: `127.0.0.1:9090`, Mac scrape **10 s**, timeout **8 s**.
- Grafana: `127.0.0.1:3000`, dashboard `vpn-connectivity`, refresh **10 s**.
- TimeWeb job в этом же Prometheus опрашивается **30 s**; его сетевые пробы
  выполнялись на сервере каждые **120 s**, пока collector был включен.
- Retention локального Prometheus в Compose: **30d**, не TimeWeb SQLite 7 дней.

Mac probe **выполняет сетевые пробы при каждом HTTP GET /metrics**.
Это не кэшированный exporter с отдельным фоновым циклом.
Ручной запрос тоже создает новые проверки; не считать его чистым чтением.
При нескольких запросах проверки могут перекрываться. Ответ может превысить
scrape timeout: обещание «всегда менее секунды» не соответствует master.

## Как читать панели

- **Internet status**: результат curl GET к `api.ipify.org`, а не агрегат
  всех проверок. Код смотрит exit curl, но не проверяет ожидаемый HTTP status
  или body. HTTP 4xx/5xx при успешной передаче могут не дать красный статус.
- **Connectivity checks**: gateway, external ICMP, системный DNS,
  HTTPS GET и небольшой POST к `httpbin.org/post`. Gateway только LAN-диагностика.
- **Latency**: длительность выполнения проверки/процесса, включая ожидание
  и timeout, не чистый ICMP RTT и не пропускная способность.
- **Tunnel status**: найден хотя бы один UP `utun`; не подтверждены протокол,
  выбранный VPN, default route, handshake или реальная связность.
- **Current route**: данные default route, локальный адрес и найденный
  `utun`. При нескольких UP `utun` master выбирает последний в выводе
  `ifconfig`, не обязательно интерфейс целевого VPN.

`site_profile` и `egress_profile` задаются окружением, не определяются
автоматически. Default `fornex_amnezia` не доказывает, что запрос шел через Fornex.
Имя `VPN` выводится из карты публичных IPv4; это подсказка об адресе выхода,
не распознавание транспорта. При общем Fornex IP разные транспорты неразличимы.
`Unknown VPN` и `No public IP` не равны доказанному отказу туннеля.

В dashboard `TimeWeb Uplinks - Pilot` карточки устройств внизу страницы
показывают самый свежий наблюдаемый WG/AWG handshake (<180 s) или недавнее
Xray access-событие (<90 s). Xray access выделяется жёлтым: это не подтверждение
открытого VPN-соединения.
MacBook `SOCKS-TW-FLEX` отображается отдельно от старых профилей. Суффикс
`FX/CEN · RU TW/FX/CEN` появляется только при свежем проверенном состоянии
контроллера TimeWeb; «маршрут неизвестен» означает сбой или устаревание его
опроса, а не автоматическое переключение. При отсутствии свежего Xray-события
настройка FLEX не означает активного подключения. В DrillDown видны все
наблюдаемые тоннели устройства, но Xray IN/OUT без отдельной статистики клиента
не измеряются. Подробнее: [VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>).

Системный DNS, curl environment/proxy и split routes могут различать пути
запросов. Один `route -n get default` не доказывает full-tunnel.
Успех GET/маленького POST не доказывает upload speed, UDP-медиа, отсутствие
DNS/IPv6 утечек или fail-closed. Пропуск на графике не равен сетевому DOWN.

## Проверка перед согласованным запуском

В данном ревью **ничего не запускается**. После отдельного решения:

1. Проверить Docker daemon и существующие контейнеры с кодом возврата/stderr,
   не переустанавливая стек и не пересоздавая данные.
2. Проверить listener 9105, процесс и LaunchAgent
   `com.sergey.vpn-host-probe`. Не запускать второй экземпляр.
3. Сверить время, актуальную площадку, маршрут к проверяемой цели, public IP,
   транспорт и реальные environment labels. Не переключать VPN ради совпадения
   с историческим `utun4` или старым профилем.
4. Проверить target Prometheus, длительность/ошибки scrape и HTTP health Grafana.
   Учесть, что обращение к probe само запускает пробы.
5. Открыть [VPN Connectivity](http://127.0.0.1:3000/d/vpn-connectivity).
   Ссылка и старые графики не подтверждают свежий работающий сбор.

Штатный Python для Mac: `python3 -B`.
Master wrapper/старые plist пока не добавляют `-B`; здесь runtime не правился.
Файл агента по прежнему deployment:
`~/Library/LaunchAgents/com.sergey.vpn-host-probe.plist`;
лог: `~/Library/Logs/vpn-connectivity/host_probe.log`.
Наличие и соответствие этих файлов текущему процессу еще требуют проверки.

## Остановка и сохранность

Остановка Grafana/Prometheus прекращает сбор/просмотр, но не обязана останавливать
host probe. `Ctrl-C` относится только к вручную запущенному foreground-процессу,
а не к LaunchAgent. Контейнеры также используются dashboard пилота TimeWeb:
их остановка затрагивает оба локальных представления.

Не удалять volumes, историю или каталоги в качестве диагностики.
Mac Compose использует `./data/prometheus` и `./data/grafana` внутри Dropbox.
Перенос живых БД в локальное несинхронизируемое хранилище остается отдельной
задачей с backup/restore, а не выполненным фактом. На выключенном Mac
нет новых локальных измерений; Prometheus не восстанавливает пропуски задним числом.

## Документы

- [VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>)
- [VPN_Connectivity_Monitoring_Implementation_Plan](<../reference/VPN_Connectivity_Monitoring_Implementation_Plan.md>)
- [VPN_Connectivity_Monitoring_Improvements](<../reference/VPN_Connectivity_Monitoring_Improvements.md>)
- [agents/history/VPN_Connectivity_Monitoring_Handoff_2026-08-17](<../history/VPN_Connectivity_Monitoring_Handoff_2026-08-17.md>)

История 2026-08-17 и последующие разовые проверки не подтверждают текущий
маршрут или uptime. Секреты, полные VPN-конфиги и ключи сюда не добавляются.
