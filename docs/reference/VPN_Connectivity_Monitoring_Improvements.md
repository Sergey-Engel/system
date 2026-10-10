---
type: architecture
topic: vpn-connectivity-monitoring
status: backlog-not-deployed
created: 2026-08-18
updated: 2026-09-13
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

## Статус предложения

Backlog расширения, **не описание уже развернутой fleet-системы**.
Полный прежний текст:
[agents/history/VPN_Connectivity_Monitoring_Improvements_Before_Review_2026-09-13](<../history/VPN_Connectivity_Monitoring_Improvements_Before_Review_2026-09-13.md>).

На снимке 2026-09-13 14:45:01 UTC (source reference not migrated)
collector/exporter TimeWeb `inactive / dead / disabled`.
Аудит не обнаружил TCP listeners на проверенных портах 3000, 9090, 9105,
19106; 19107 не проверялся. Пустой `local_docker` не доказывает отсутствие
контейнеров: returncode проигнорирован, stderr не сохранен.
Отфильтрованный launchd-список не дает полного статуса установленного стека.
Отсутствующая диагностическая команда не означает DOWN.

Актуальные контуры:
[VPN_Connectivity_Monitoring_Quick_Guide](<../operations/VPN_Connectivity_Monitoring_Quick_Guide.md>) и
[TimeWeb_Uplink_Pilot_Quick_Guide](<../operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).
Ранее описанный серверный Prometheus/Infinity не является установленным пилотом.

## Приоритеты

1. **Вернуть доказуемость текущей документации и наблюдений.**
   Сначала полноценный snapshot, runtime/master equality, freshness и coverage.
   Не включать monitoring автоматически только потому, что он установлен.
2. **Завершить приемку TimeWeb pilot.**
   120 s измерения, 45 s deadline, 180 s stale, 7-дневная SQLite policy.
   Сервер должен реально работать, чтобы собирать историю без Mac.
3. **Завершить candidate backfill.**
   [TimeWeb_Uplink_History_Sync_Plan](<TimeWeb_Uplink_History_Sync_Plan.md>): API и cache уже есть в master,
   но успешный deployment/Grafana integration не подтвержден.
4. **Уточнить Mac probe.**
   HTTP status/body validation, freshness, bounded request/cache,
   достоверная связь target-route и labels. Текущий `utun` и public-IP name
   не являются доказательством выбранного транспорта.
5. **Только затем расширять fleet monitoring.**
   Отдельный согласованный scope, ресурсный бюджет, безопасность и приемка.

## Предлагаемый fleet scope

- Внешняя достижимость TimeWeb/Cenuta/Fornex с независимой точки.
- Состояние ожидаемых systemd/Docker services, reboot/restart и заполнение диска.
- Read-only WG telemetry без ключей: наличие интерфейса/peer, handshake age,
  RX/TX и их изменения, если эти поля действительно доступны.
- Ресурсы CPU/RAM/disk/inodes и синхронизация времени.
- Fleet Overview и Host Detail после проверки labels и источников.
- Уведомления с работающей независимо от Mac стороны, если нужен режим 24/7.

Выбор SSH polling или host-side exporters остается проектным решением.
Ни существующие scripts, ни этот список не разрешают новые SSH sessions,
установки, публичные порты или автоматические перезапуски.

## Исправленные критерии

Handshakes не задают универсальные UP/DOWN:
180 s в TimeWeb pilot является диагностическим порогом, а не доказательством
работоспособности/отказа по времени последнего handshake.
Старые предлагаемые `>600 s = DOWN` не являются действующей политикой.

Отказ management SSH отделяется от отказа WG/HTTPS.
Сам TimeWeb не может наблюдать себя при полном выключении.
Работающий Mac измеряет только свою площадку, маршрут и время присутствия;
это не непрерывная история домашней сети.

Host-side успешный GET не доказывает полный клиентский FORWARD/NAT-путь,
REALITY, Apple TV, DNS/IPv6 leak protection или стабильность приложений.
Без returncode/stderr ошибка инструмента не должна превращаться в сетевой инцидент.

## Apple TV и другие клиенты

Старая гипотеза об Apple TV, адресе 192.168.88.11 и address-list сохранена
в архиве. Назначенный IP или запись policy-routing сами по себе не доказывают
фактическую связность. Нужны актуальные DHCP/ARP/bridge данные, маршрут,
трафик клиента и его прикладной результат в одном временном окне.

Эта клиентская диагностика не выполнялась в текущем документационном ревью.
Registry, host-state, REALITY-архитектура и VPN_HLD остаются отдельной зоной
ответственности; данный backlog не переписывает их конфигурацию.
