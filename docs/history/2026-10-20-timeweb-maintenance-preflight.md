# TimeWeb: подготовка согласованного обслуживания

Дата: 20 октября 2026. Это исторический первоначальный preflight:
обслуживание тогда не начиналось до входа в аварийную консоль.
Пользователь затем вошёл; дальнейшее обслуживание и новый SSTP описаны
в [актуальном протоколе](2026-10-20-timeweb-maintenance-sstp-newip.md).

Пользователь разрешил обновления и перезагрузку с временным перерывом
WireGuard/Xray, затем SSTP на дополнительном IP без failover.
[План](../tasks/PLAN-timeweb-maintenance-newip-sstp.md).

## Свежие Наблюдения

- SSH hostname 6275803-hh441050; uptime более 22 дней, ОС требует reboot.
- Load 10.37 / 14.94 / 14.22; около 93 MiB доступной RAM, swap отсутствует.
- containerd-shim существующего wg-relay: 9027 потоков, RSS 989292 kB.
  9014 потоков находились в wait_for_partner; пять выборочных kernel stacks
  подтверждают блокирующий fifo_open/openat. Это подтверждение механизма
  накопления заблокированных потоков, не доказательство конкретного upstream bug.
- Docker CE 29.8.1, containerd.io 2.3.6. Начальный cached upgrade plan:
  22 обновления, без удаления пакетов. Доступны Docker CE 29.9.1 и
  containerd.io 2.4.2. Их наличие не доказывает устранение FIFO-проблемы.
- Обновление индексов apt остановлено ограничением 120 s: часть индексов
  загружена, успешного полного refresh нет. Пакеты не устанавливались.
- Bindings recovery совпадают с действующим policy; ID/image контейнера
  совпадают. Полный recovery check отказал на fleet_ready, самостоятельный
  последующий fleet status показал 3/3 ready. Drift не переподписывался.
- Новый IPv4 по-прежнему не назначен в ОС. DHCP/default route не менялись.

## Копия И Её Ограничение

Архив .local/backups/timeweb/2026-10-20T164307Z_current-config/backup.tar.gz:
SHA256 8dd72e1189d4f0c69d705c5713fdd4a4572bad92a1354738b57a1b345870be9f.
Штатный verifier сохранил FAILED: одна команда docker-ps.json до сбора
завершилась timeout124. Этот исход не удалён и не заменён PASS.

Дополнительная независимая проверка дала
VERIFIED_CONFIGURATION_WITH_DIAGNOSTIC_EXCEPTION: 391 host file,
полный внешний и внутренний hash inventory, source hashes/metadata
before/after/final, обязательный состав, инертное восстановление обычных
файлов, все runtime comparisons, BTH и S2S guards прошли. Единственное
исключение строго проверено; inventory подтверждён успешными docker inspect
и container-inventory. Это конфигурационная копия, не образ диска и не
проверка восстановления всей машины.

## Блокирующее Условие

Перед изменениями runbook требует проверенную консоль провайдера вне SSH.
В доступном Chrome создана вкладка TimeWeb; она перенаправлена на login.
API credentials в canonical store не найдены. Попытки управления браузером
завершились timeout/Debugger unattached. Подтверждённой авторизованной
консоли нет; пользователю отправлен запрос открыть её.

Reboot, установка пакетов, restart Docker/container/WireGuard/Xray,
назначение IP и запуск SSTP не выполнялись. Новые зависимости и контейнерные
образы не устанавливались. Пользовательские маршруты не переключались.
Локальный source 1.1.0 подготовлен для 91.222.238.208:443; backend в
namespace остаётся 127.0.0.1:5444. Это не deployed release.

Доказательства приватно: .local/backups/timeweb-maintenance/20261020/.
После открытия консоли требуется свежая повторная оценка нагрузки,
завершение apt update и review полного плана пакетов перед установкой.

## Первичные Источники

- [TimeWeb: дополнительный IP](https://timeweb.cloud/docs/unix-guides/adding-ip-addresses).
- [Docker 29 release notes](https://docs.docker.com/engine/release-notes/29/).
- [Containerd FIFO resource leak report](https://github.com/containerd/containerd/issues/13952):
  похожий механизм, но другой CRI-сценарий; тождество нашему shim не доказано.
