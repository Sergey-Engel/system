---
type: historical-document
status: historical-superseded
archived: 2026-09-13
---

> [!WARNING] Историческая версия, не текущий runbook
> Полный текст документа до документационного ревью 2026-09-13 сохранен ниже без изменения. Старые статусы, планы, команды, интервалы и пути не подтверждают состояние runtime и не разрешают повторное внедрение.
> Актуальная версия: [VPN_Connectivity_Monitoring_Improvements](<../reference/VPN_Connectivity_Monitoring_Improvements.md>). Текущий статус TimeWeb: [Pilot Quick Guide](<../operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).
> Относительные ссылки внутри оригинала относятся к прежнему расположению в `MIKROTIK/docs/`.

<!-- ORIGINAL DOCUMENT START -->
---
type: architecture
topic: vpn-connectivity-monitoring
status: proposed
created: 2026-08-18
updated: 2026-09-11
tags:
  - monitoring
  - prometheus
  - grafana
  - wireguard
  - mikrotik
source:
  - "[VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>)"
  - "[VPN_Connectivity_Monitoring_Quick_Guide](<../operations/VPN_Connectivity_Monitoring_Quick_Guide.md>)"
  - "[MikroTik_Quick_Guide](<../quick-start.md>)"
---

## Назначение

Рабочее предложение по расширению мониторинга трёх внешних хостов: TimeWeb,
Cenuta и Fornex. Документ предназначен для дальнейшего обсуждения; изменения
на хостах и в маршрутизации по этому документу пока не выполняются.

## Рекомендуемая схема

Приоритет для круглосуточного контроля upstream уточнен 2026-09-11:
[отдельный проект мониторинга на TimeWeb](<../architecture/TimeWeb_Uplink_Monitoring_Architecture_and_Plan.md>)
предусматривает сбор, хранение истории и определение отказов Cenuta/Fornex
непосредственно на TimeWeb, независимо от Mac. Это проект, еще не deployment.
Существующая Grafana на Mac используется для просмотра серверной истории через
SSH; отдельную Grafana на TimeWeb не устанавливаем. Mac также остается
дополнительной внешней точкой наблюдения. Для upstream порядок
внедрения и критерии статусов брать из нового документа, а не из старых
порогов и последовательности ниже. Остальные предложения здесь остаются backlog.

Исходный гибридный вариант для внешних проверок и расширения на все сервисы:

1. Внешний polling с Mac проверяет доступность хоста и сервисов с текущей
   площадки и текущего маршрута.
2. Read-only SSH collector с Mac получает внутреннее состояние VPS.
3. Prometheus хранит метрики, Grafana показывает общий обзор и детали.
4. Host-side exporters устанавливаются только после того, как SSH-сбор окажется
   недостаточным.

Такой вариант не требует открывать новые публичные порты на VPS и сохраняет
диагностическую ценность внешней проверки.

## Метрики хоста

- ICMP, TCP/22 и время SSH-подключения;
- uptime, load average, CPU, RAM, swap;
- заполнение диска и inode;
- версия ОС, kernel, pending updates, `reboot-required`;
- синхронизация времени/NTP;
- внешний IPv4 и DNS/HTTPS-доступ.

## Метрики сервисов

Для каждого хоста собирать состояние ожидаемых systemd units и Docker-контейнеров:

- WireGuard interfaces и `wg-quick` units;
- Amnezia/WireGuard сервисы, если установлены;
- Docker daemon и состояние контейнеров;
- nftables/firewall;
- restart count и health status контейнеров;
- список слушающих портов.

## Метрики WireGuard

- интерфейс поднят или отсутствует;
- listen port;
- количество зарегистрированных peers;
- количество peers с актуальным handshake;
- возраст последнего handshake каждого peer;
- RX/TX counters и их изменение за интервал;
- endpoint и allowed IPs;
- отдельный статус соседних туннелей TimeWeb-Cenuta,
  TimeWeb-Fornex и других upstream-соединений.

Рекомендуемые начальные пороги:

- handshake до 180 секунд: `UP`;
- 180-600 секунд: `STALE`;
- более 600 секунд или отсутствует: `DOWN/NO HANDSHAKE`.

Порог должен учитывать `PersistentKeepalive` конкретного peer.

## Grafana

### Fleet Overview

Компактная таблица по трём хостам:

`Host | Reachability | Services | WG peers active/total | Handshakes | Public IP | Disk`

### Host Detail

Для каждого VPS отдельные панели:

- доступность и время ответа;
- systemd/Docker services;
- WireGuard interfaces и peers;
- handshake age;
- RX/TX;
- CPU/RAM/disk;
- public IP, DNS и HTTPS;
- последние ошибки и события.

## Варианты доставки данных

### Внешний SSH polling

Основной вариант для первой реализации. Mac раз в 30-60 секунд выполняет
ограниченный набор read-only команд по SSH и публикует результат локальному
Prometheus exporter.

Плюсы: не нужны новые входящие порты, используются существующие ключи, видна
доступность снаружи. Минусы: при недоступном SSH внутреннее состояние получить
нельзя, а Mac должен быть включён.

### Exporter на VPS

Возможный второй этап: `node_exporter`, WireGuard collector и Docker collector,
доступные только через разрешённый management path.

Плюсы: полнее внутренние метрики и стандартный Prometheus API. Минусы: новые
сервисы, дополнительная поверхность атаки и необходимость организовать доставку
метрик до Mac.

## Предлагаемый порядок внедрения

1. Составить реестр хостов, интерфейсов, systemd units, контейнеров и peers.
2. Создать локальный read-only SSH collector.
3. Добавить метрики доступности, ресурсов, сервисов и WireGuard.
4. Собрать Fleet Overview.
5. Добавить alerts: host down, service down, no handshake, disk > 80%,
   RAM > 90%, reboot required, изменение public IP.
6. Проверить collector на реальных сбоях и исключить ложные срабатывания.
7. Только после этого решить, нужны ли exporters на самих VPS.

## AppleTV Gostinnaya: отдельная диагностика

Запись в `/ip firewall address-list` только включает IP в policy-routing. Она не
подтверждает, что AppleTV действительно получил адрес `192.168.88.11`, виден в
ARP, имеет активный DHCP lease, проходит firewall и отправляет трафик.

Проверять нужно в следующем порядке:

1. запись `CENUTA_Devices` и отсутствие дубликата в `VPN_Devices`;
2. DHCP lease, MAC и статус lease;
3. ARP entry и bridge host для `192.168.88.11`;
4. counters mangle rules для `CENUTA_Devices`;
5. active firewall connections от устройства;
6. DNS/DHCP доступность и default route;
7. фактический внешний IP после генерации трафика.

До получения этих данных конфигурацию не менять.
