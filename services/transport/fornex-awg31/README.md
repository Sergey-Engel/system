# Fornex AWG 3.1: действующий выпуск

Обновлено 2026-09-15. Работает **fornex-awg31**, UDP **46056**, **11 peers**. Старый **amnezia-awg2 удален**, UDP 46055 не является рабочим AWG2 endpoint. Обычный WG, wg-exit и остальные Amnezia-контейнеры не удалялись.

## Мастер и сервер

- Действующий конфиг: `release/awg0.conf`; сервер `/opt/fornex-awg31/awg0.conf`.
- SHA-256 master = live: `19c67ab3a7a86de6709c704532ea769d87d61749d4a17b7264988120a49ee2e4`.
- Устройства: `fleet.json`, отдельные ключи в `credentials.json`, 11 `Fornex-AWG31-*.conf`.
- Файлы выдачи: .local/clients (source reference not migrated); все 11 совпадают с master.
- `release/start.sh`, `Dockerfile`, `source/`, `image-id.txt`, `run-command.txt`: материалы установленного выпуска.
- Сеть 10.83.1.0/24, MTU 1280, DNS 1.1.1.1/1.0.0.1. Адрес .3 отозванного тестового peer не используется.
- Прямой Fornex egress; TimeWeb/REALITY/BTH не участвуют.
- RO bind конфигурации, userspace AWG, /dev/net/tun, NET_ADMIN, 256 MiB, pids 128, log 2 x 2 MiB, restart unless-stopped.

Строка daemon `0.0.20250522` не отражает однозначно версию протокола. AWG 3.1 проверен принятыми параметрами и передачей данных. Сборочные источники закреплены на материалы AmneziaVPN 5.0.1.5.

## Статус устройств

MacBook Sergey и iPhone Sergey проверены пользователем. Остальные девять файлов выпущены; подтверждение импорта и работы каждого устройства еще не получено. AWG31 профиль Mac Mini M4 Sergey перевыпущен с новым ключом 15 сентября 2026. После расширения выполнен ограниченный server-side smoke, не полная клиентская приемка.

## Скрипты: что нельзя повторять автоматически

- `prepare.py` и `deploy.py`: RETIRED до действий. `build.py` оставлен как отдельная явная сборка без установки, безопасный импорт.
- `finalize.py`: RETIRED, не перезапишет текущий fleet двухклиентской версией.
- `expand_fleet.py`: выполненная миграция; CLI и старый sync теперь заблокированы, не универсальный add/delete.
- `verify.py --profile <file>`: активный тест. Использовать только неработающий сейчас профиль, иначе endpoint roaming нарушит сессию устройства.
- `rollback.sh`: RETIRED до Docker-команд, не останавливает AWG31 и не восстанавливает AWG2.

Новые изменения требуют свежего backup и scoped diff runtime/persistent/credentials/fleet/exports. Python только `python3 -B`.

## Backup

`backup/` и `retirement-backup/` содержат закрытые конфиги/metadata/export прежнего AWG2 и историю миграции; `sha256.json` фиксирует целостность. Это не каталог выдачи профилей и не автоматический full restore. Тестовый ключ исключен из активного credentials, его старый файл оставлен только в retirement.

При этом `retirement-backup/credentials.before.json` содержит также действующие секреты AWG31 сервера и первых двух клиентов. Отзыв AWG2 не обезвреживает весь архив; закрытый режим хранения обязателен.

Общий firewall restore, перезапуск Docker или удаление обычного WG не являются способом отката этого выпуска.

[Эксплуатационная инструкция](<../../../docs/operations/Fornex_AWG31_Operations.md>) · [Реестр устройств](<../../../docs/registry/tunnels.md>) · [Мастер-копии](<../../../docs/registry/configuration.md>).
