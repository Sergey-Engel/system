# VPN Connectivity Monitoring: локальный master

Mac probe, Prometheus и Grafana provisioning.
[Quick Guide](<../../../docs/operations/VPN_Connectivity_Monitoring_Quick_Guide.md>)
и [архитектура/ограничения](<../../../docs/architecture/VPN_Connectivity_Monitoring_Architecture.md>).

## Текущий статус

Проверка при обновлении device-first dashboard 2026-09-15 подтвердила:

- Compose-контейнеры Grafana и Prometheus запущены, Prometheus targets
  `macbook-wg-peer`, `vpn-host-probe` и `timeweb-uplink-pilot` имеют статус `up`.
- LaunchAgent `com.sergey.wg-peer-probe` запущен и отдает метрики на
  `127.0.0.1:19108`.
- Grafana подхватывает provisioned JSON без ручного сохранения из UI.

Это срез работоспособности наблюдения, а не приемка всех VPN-профилей или
клиентских устройств. Снимок 2026-09-13 (source reference not migrated)
с отсутствующими listeners остается историческим ограниченным аудитом; его
пустой `local_docker` не доказывал отсутствие контейнеров.

## Состав и интервалы

- `probe/host_probe.py`: HTTP endpoint `127.0.0.1:9105/metrics`.
- `probe/wg_peer_probe.py`: параллельные read-only SSH-срезы TimeWeb
  `wg-relay` (`wg0`, `wg-clients`, `wg-home`), Fornex `fornex-awg31`
  (`awg0`) и TimeWeb `xray-timeweb-reality.service` через локальный журнал
  сервиса. Отдельный read-only вызов `timeweb-flex-macbook status` читает
  проверенное состояние маршрута FLEX. HTTP endpoint `127.0.0.1:19108/metrics`,
  опрос **15 s**.
- `config/inventory/observations.json`: единственный структурированный inventory
  устройств и наблюдаемых server-side peers. Его используют одновременно
  exporter и генератор device-first dashboard; он должен синхронно меняться с
  `TimeWeb_VPN_Registry.md`.
- `prometheus/prometheus.yml`: Mac scrape **10 s**, timeout **8 s**;
  TimeWeb job scrape **30 s**, timeout **8 s**.
- `grafana/provisioning/`: dashboard VPN Connectivity и отдельный TimeWeb pilot.
- `compose.yaml`: loopback 9090/3000, Prometheus retention **30d**.
- `data/`: живые bind mounts Prometheus/Grafana внутри Dropbox по master Compose.
  Перенос в несинхронизируемое хранилище не выполнен.
- Образы в Compose имеют tag `latest`; это не закрепленные runtime-версии.

Серверные пробы TimeWeb имеют отдельные **120 s / 45 s / 180 s** и
SQLite retention **7 дней**. Mac scrape/refresh не добавляет новых сетевых
измерений TimeWeb и не подкачивает его пропуски.

## Реальная семантика Mac probe

Каждый GET `/metrics` запускает сетевые проверки, затем запрос public IPv4.
Нет фонового cache/scheduler; ручной curl также создает пробы.
10 s scrape является настройкой, не гарантией точного периода или быстрого ответа.

Internet status отражает curl GET exit к api.ipify.org, не агрегат всех тестов.
Код не проверяет ожидаемый HTTP-код/body: 4xx/5xx могут не дать failure.
Отдельно выполняются LAN gateway, внешний ICMP, system DNS и маленький HTTPS POST.
Latency является временем выполнения проверки, не чистым RTT или bandwidth.

`site_profile/egress_profile` задаются окружением. Default
`nakhimova_domru/fornex_amnezia` не является текущей площадкой/транспортом.
Последний UP `utun` из ifconfig не обязательно относится к проверяемому VPN.
Имя по public IPv4 является lookup по карте, не распознаванием протокола;
один exit IP может использоваться разными транспортами.

## Server-side VPN telemetry

`wg_peer_probe.py` читает counters и latest handshake на TimeWeb и Fornex через
SSH, а также подписанные Xray access-события из `journald` на TimeWeb. Он не
подключается к клиентам, не читает клиентские конфиги или ключи и не выгружает
содержимое журналов в метрики. `vpn_wg_peer_*` имеют labels `device`,
`device_name`, `tunnel`, `interface`, `source`; `vpn_xray_client_*` имеют те же
идентифицирующие labels без интерфейса. `vpn_device_*` выбирают один текущий
наблюдаемый тоннель на устройство по самому новому наблюдению: handshake
WG/AWG младше **180 s** или access-событию подписанного Xray-клиента младше
**90 s**. Access-событие означает только недавний запрос, а не открытое
соединение или работоспособный клиентский тоннель.

`activity=1` означает недавний WG/AWG handshake, `3` — недавний Xray access
(карточка помечает его жёлтым `access <90s`), `2` — свежий полный опрос без
недавней активности, `0` — отсутствующее или неполное наблюдение. Один недоступный источник
не удаляет срез другого: последний успешный срез остается видимым до истечения
**45 s**, а следующая скорость после сбоя рассчитывается только с новой парой
WG/AWG-счетчиков. `vpn_source_observation_fresh` показывает freshness по
каждому серверному источнику. IN — server TX к клиенту, OUT — server RX от
клиента; скорость появляется только для WG/AWG после пары корректных
последовательных счетчиков. Xray access-журнал не содержит побайтной статистики
отдельного клиента, поэтому для Xray карточка показывает прочерки IN/OUT.

Для `SOCKS-TW-FLEX` карточка MacBook показывает выбранные FX/CEN и путь RU
только при одновременном свежем Xray access-событии и свежем успешном read-back
контроллера. Метрики `vpn_flex_route_observation_fresh`,
`vpn_flex_route_exit_code` (1 FX, 2 CEN) и `vpn_flex_route_ru_direct` (0/1)
показывают серверную настройку независимо от активности профиля. При сбое
опроса спустя 45 s маршрут обозначается неизвестным, а не прежним FX/CEN.
Опрос не меняет маршрут и не доказывает сквозную работу клиента.

Эта телеметрия не подтверждает здоровье браузера, пропускную способность Xray,
UDP-медиа, DNS/IPv6 leak protection или fail-closed. Inventory покрывает
**21 устройство, 36 TimeWeb WG, 11 Fornex AWG31 peer и 13 подписанных TimeWeb
Xray identity** из клиентского реестра. Несколько файлов могут использовать
одну identity. Отсутствующий peer или Xray
access-событий будет обозначать конфигурационное несоответствие либо отсутствие
недавнего трафика, а не доказательство выключенного клиента.

## Эксплуатационные границы

LaunchAgents: `com.sergey.vpn-host-probe` и `com.sergey.wg-peer-probe`;
plist в `~/Library/LaunchAgents/`, диагностические логи в
`~/Library/Logs/`.
Файлы, загруженный job и работающий процесс проверяются отдельно.
Не запускать второй экземпляр probe.

Перед согласованным возобновлением проверить Docker/process/listeners с
returncode/stderr, runtime/master equality, реальные labels и сохранность истории.
Mac Python только `python3 -B`;
после изменения `wg_peer_probe.py` требуется `launchctl kickstart -k` именно
этого job, без перезапуска Docker или VPN-тоннелей.

[Открыть VPN Connectivity](http://127.0.0.1:3000/d/vpn-connectivity)
можно при работающем локальном стеке. Ссылка не доказывает текущую доступность.
Остановка общего Grafana/Prometheus затрагивает также dashboard TimeWeb;
не удалять volumes или старые данные. Без Mac нет новых локальных измерений,
пропуски не восстанавливаются обычным scrape.

Порты заданы loopback в master; аудит не обнаружил TCP listeners
на 3000/9090/9105/19106. Другие порты этим выводом не покрываются.
Секреты, ключи и полные VPN-конфиги в README/метрики не помещать.
