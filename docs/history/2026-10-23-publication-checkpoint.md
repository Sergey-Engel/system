# Checkpoint23 Октября: Панель И Восстановление Direct

## Завершённые Изменения

- Панель4.2.2: после успешного чтения прогресс скрывается через20 секунд,
  зелёный Updated под Refresh сохраняет checked_at; ошибки не скрываются.
  Повторный опрос отменяет старый таймер, нет фоновых запросов или переключений.
  [Контракт UI и проверки](2026-10-22-panel-poll-progress.md).
- Исправлен ложный drift: RouterOS при предупреждении interface not ready
  разделяет путь и add. Parser сохраняет параметры/порядок, неизвестные
  изменения по-прежнему блокируются. Наблюдаемый baseline вслепую не принимался.
  [Разбор причины](2026-10-23-panel-export-warning.md).
- Direct восстановился после исправления владельцем кабеля в ether1.
  Сеть Deco192.168.68.0/24, LAN MikroTik Фетхие192.168.89.0/24,
  WebFig из его Wi-Fi: http://192.168.89.1; владелец подтвердил вход.
  В Deco сохранены reservation Mac115 и MikroTik117; SSH восстановлен.
  [Диагностика и приёмка](2026-10-23-direct-fethiye-unreachable.md).
- По отдельному явному разрешению владельца добавлен SSH/TCP22 с Deco LAN
  через ether1. Другие службы/Internet-доступ не открывались. При смене IP
  Mac в68/24 SSH больше не зависит от115. WebFig80 по-прежнему только115.
  [Точный diff, риск доверия LAN и откат](2026-10-23-local-ssh-access.md).

VPN transports, routes, NAT и назначения устройств агент не менял. Смена
физического подключения и DHCP reservation выполнены владельцем. Контроллер
и исходники панели локальные, TimeWeb controller не redeploy/restart.
Все7 устройств и Direct/четыре Split-канала в свежем UI показывали готовность.
Проверены двусторонние router-originated ICMP и крупные DF-пакеты. Клиентский
Internet-выход, IPv6 и длительный soak сегодня не принимались. Вход в WebFig
с MacBook подтверждён владельцем, не выдан за Internet-проверку.

## Свежие Копии

Все пути ниже внутри закрытого.local/backups, не публикуются в Git:

| Объект | Run | Проверка |
| --- | --- | --- |
| Фетхие и Нахимова | site-to-site/20261023T065829Z-publication | Оба VERIFIED_TRANSFER: sensitive export, AES-SHA256 encrypted RouterOS backup, две одинаковые загрузки, export до/после без изменений |
| TimeWeb | timeweb/2026-10-23T065744Z_current-config | VERIFIED:448 host files,122 temporary restore files |
| Fornex | fornex/2026-10-23T065854Z_current-config | VERIFIED:135 host files и конфиги6 containers |
| Cenuta | cenuta/2026-10-23T065920Z_current-config | VERIFIED:84 host files,10 temporary restore files |
| Орехово | orekhovo/20261023T065830Z | BLOCKED:SSH/identity недоступны; свежая копия не получена |

Локальный configuration snapshot run:
`local/2026-10-23T070014Z_current-config`. Финальный результат, состав,
проверка свежего read-only export и пробного восстановления определяются
его private verification.json; PARTIAL/FAILED нельзя трактовать как VERIFIED.
Canonical store содержит новые router backup passwords и проверенные файлы
восстановления. Архивы VPS не дублируются внутрь JSON-store. Копии конфигураций
не являются дисковыми образами; live restore и reboot не выполнялись.

## Публикация

Полный suite:694 passed,45.13s. Ранее отдельный site-to-site suite352 passed.
Перед commit проверяются git diff --check, repository validator, canonical
store и точный staged inventory. Validator сверяет public files с известными
секретами private store и private-key markers. Git-ignore исключает.local,
ключи и архивы; приватные пути не должны быть tracked или staged.
Публикуются только source/tests, безопасный inventory и документация.
