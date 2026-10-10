# MikroTik / VPN System

Рабочее хранилище инфраструктуры: TimeWeb, Fornex, Cenuta, MikroTik Нахимова
и Орехово. Документация, исходники и безопасные реестры версионируются в Git.
Профили, ключи, полные конфигурации, runtime и резервные копии остаются локально.

## Начать работу

- [Quick Guide: запуск и диагностика](docs/quick-start.md).
- [Доступ ко всем узлам](docs/operations/access.md).
- [Архитектура](docs/architecture/overview.md) и [схемы](docs/architecture/diagrams/index.html).
- [Реестр тоннелей](docs/registry/tunnels.md), [реестр конфигурации](docs/registry/configuration.md).
- [Правила изменений для агента](AGENTS.md).
- [Хранение, перенос и откат](docs/operations/storage-and-transfer.md).
- [Результаты миграции 10 октября](docs/migration/2026-10-10-execution-report.md).

## Каталоги

| Каталог | Назначение |
| --- | --- |
| `docs/architecture` | Описание и схемы действующей системы |
| `docs/operations` | Актуальные процедуры |
| `docs/hosts` | Карточки площадок и хостов |
| `docs/registry` | Читаемые реестры |
| `docs/history`, `docs/reference` | Датированные свидетельства и справочные материалы; не deployment baseline |
| `docs/migration` | План, карта файлов и проверки переноса |
| `services/transport` | Исходники транспорта и controllers |
| `services/monitoring` | Collectors, console, dashboards, provisioning |
| `config/inventory` | Машиночитаемые реестры профилей и наблюдений |
| `config/templates` | Только безопасные шаблоны без секретов |
| `scripts` | Локальная настройка, приватное хранилище и проверки |
| `.agents/skills` | Инструкция сопровождения тоннелей |
| `.local` | Исключённые из Git секреты, профили, конфигурации, backups и runtime |

Файл [clients.json](config/inventory/clients.json) описывает выданные файлы;
[observations.json](config/inventory/observations.json) определяет наблюдения
экспортера и карточки Grafana. Наличие профиля не означает его активацию на
устройстве. Live state не заменяется значениями из исторического документа.

Команды ниже и в runbooks выполняются из корня этого checkout:

```sh
timeweb-vpn
timeweb-vpn status
.venv/bin/python -B scripts/validate_repository.py
```

Перенос не изменил ключи, адреса клиентов или live routing. В GitHub публикуется
только публичное дерево: `.local`, секреты, backups и runtime остаются локально.
