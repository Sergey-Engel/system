# Хранение, перенос и откат

## Что является источником

Git хранит исходники, описание, схемы и безопасные реестры. Полные приватные
файлы собраны в [.local/secrets.json](../../.local/secrets.json): идентификаторы,
происхождение, состояние, checksum и исходные байты. Это JSON без шифрования,
не безопасный файл для отправки в чат или публикации. Права: `.local` 700,
secret store и материализованные секреты 600. Base64 не является шифрованием.

Копии [.local/clients](../../.local/clients), [.local/config](../../.local/config)
и [.local/ssh](../../.local/ssh) созданы для существующих инструментов.
Для фонового SSH установка также создаёт private runtime cache в
`~/.local/state/system-project/ssh`. macOS не разрешает прямому SSH из launchd
читать `Documents`; cache использует те же ключи, права 600/700 и strict trust.
Это производная копия, не второй источник секретов; переносить её отдельно
не нужно. После изменения ключей повторить setup с обновлённым canonical store.
Live host остаётся источником runtime-состояния; `config/hosts/*/current` означает
снимок текущей конфигурации на момент датированной миграции, а не live mirror.
Пароли, которых нет в доступных материалах, не выдумываются и не сбрасываются.

Старые конфигурации и backups из исходного хранилища не копировались.
История Grafana/Prometheus перенесена отдельно в
[.local/runtime/monitoring](../../.local/runtime/monitoring).

## Перенос на другой Mac

1. Получить checkout Git и передать **только один** `secrets.json` по доверенному
   локальному/зашифрованному каналу. Хранить в `.local/secrets.json` с правами 600;
   каталог `.local` должен иметь 700. Не добавлять его в Git.
2. Из корня checkout создать окружение и материализовать файлы:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B scripts/setup_mac.py
.venv/bin/python -B scripts/private_store.py --verify-only
```

3. Установить локальные bindings существующих пользователей/ключей:

```sh
.venv/bin/python -B scripts/setup_mac.py --install
timeweb-vpn
```

Установка не создаёт серверных пользователей или ключей. Она сохраняет прежние
локальные bindings перед заменой launcher/SSH include/трёх LaunchAgents.
`~/.local/bin` должен быть в PATH. Если он не в PATH, выполнить launcher прямо:

```sh
services/monitoring/timeweb-uplinks/pilot/open_console.sh
```

Docker Desktop нужен только для локальных Prometheus/Grafana. При чистой
установке сначала загрузить закреплённые в compose образы, затем:

```sh
docker compose -p vpn-connectivity -f services/monitoring/vpn-connectivity/compose.yaml up -d
```

`secrets.json` переносит профили и доступ, **не историю мониторинга**. Для
переноса истории остановить оба контейнера, скопировать весь runtime каталог,
проверить байты/целостность базы и запустить на новом месте. Копирование живой
SQLite/Prometheus storage без остановки не считать проверенным backup.

## Изменения секретов

После отдельно согласованного изменения обновить соответствующую запись
canonical store с происхождением, timestamp и SHA-256. Затем материализовать
точные файлы и проверить отсутствие секретов в публичном дереве. Не запускать
materialize поверх более новых профилей: сперва сравнить diff и обновить store.
Не перезаписывать approved identities и не генерировать новые при переносе.

## Свежие резервные копии

```sh
.venv/bin/python -B services/transport/timeweb-reality/run_backup.py all
.venv/bin/python -B scripts/backup_router.py nakhimova
.venv/bin/python -B scripts/backup_router.py orekhovo
.venv/bin/python -B services/transport/timeweb-reality/backup_local.py
```

Результаты в [.local/backups](../../.local/backups). Сверять `verification.json`,
не только существование архива. RouterOS encrypted backup использует пароль,
сохранённый в secret store. `VERIFIED_TRANSFER` подтверждает двойное скачивание
и checksum, **не восстановление на реальном роутере**. VPS `VERIFIED` включает
проверку состава и инертное восстановление файлов; это не reboot/restore drill.
Орехово требует доступности именно этой площадки; совпадающий LAN IP другого
роутера нельзя использовать вместо неё. Текущий `codex_audit` имеет read/ssh,
а не право создавать binary backup.

Local archive безопасно кодирует буквальный backslash в именах systemd units
как `%5C` (сам `%` как `%25`); точное исходное имя записано в `inventory.json`.
Проверка архива не исполняет файлы и не декодирует имена при временном
восстановлении. Для реального restore использовать inventory, не слепую распаковку.

## Откат локального переключения

Перед переключением сохранены SSH config, launcher и старые LaunchAgents в
[integration-before](../../.local/backups/local/20261010T150854Z-integration-before).
Live VPN не изменялся, откат касается только Mac:

1. `timeweb-vpn stop` закрывает принадлежащий launcher SSH, не VPN-сервисы.
2. Остановить три изменённых LaunchAgents и оба monitoring контейнера.
3. Восстановить сохранённые SSH config, launcher и plist; загрузить старые agents.
4. Запустить исходный compose с прежними data mounts, проверить fresh cycles.
   Если после миграции были важные наблюдения, предварительно сохранить новое
   runtime storage; старые данные не включают наблюдения после переключения.

Не удалять новые/старые runtime каталоги, не делать общий reset и не откатывать
хостовые конфигурации ради отката путей на Mac. В этом переносе исходные
документы, конфигурации и backups не удалены.
