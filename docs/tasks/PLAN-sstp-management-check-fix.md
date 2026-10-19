# PLAN: Отказ Проверки Управления Нахимова

Статус: Done. Дата: 2026-10-19.

| Шаг | Состояние |
| --- | --- |
| Read-only локализация | Done |
| RED для SSH transient/identity failures | Done: 5 failed / 3 passed до изменения |
| Ограниченный retry только соединения, точные статусы | Done |
| Тесты, локальный restart, live чтение | Done: 543 passed, HTTP/browser и read-only Add preflight |

Новый отказ `validated_direct_route_unavailable` до записи. В отдельной
read-only проверке Fethiye SSTP running=true, Nakhimova SSH через прежний
management proxy отказал через11.35s. Внутри SSTP5/5 ICMP без потерь.
Далее TimeWeb/WG ICMP3/3 и management TCP22 доступны; три подключения
Nakhimova подтвердили serial, исходный baseline и SSTP running=true.
Это воспроизведенный временный отказ управления, не доказанный обрыв SSTP
или дрейф конфигурации. Низкоуровневая причина исходного отказа не записана.

Изменение только локальных файлов панели: максимум два начальных SSH connect
при транспортной ошибке. Не повторять authentication/host key/serial failures,
проверку drift или команды записи. Полная свежая проверка до Add сохраняется;
при повторном отказе Add по-прежнему заблокирован. Не переключать ноутбук
автоматически, не менять TimeWeb, SSH-forward, PKI, firewall или роутеры.

Снимок до редактирования:
`.local/backups/site-to-site/20261019T111803Z-management-check/`.

Результат и границы: [протокол](../history/2026-10-19-sstp-management-check-fix.md).
