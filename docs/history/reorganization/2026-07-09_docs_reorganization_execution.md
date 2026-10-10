# Docs Reorganization Execution 2026-07-09

## Цель

Переделать структуру документации MikroTik/VPN так, чтобы:

- `docs/` содержал основные документы для человека;
- `docs/agents/` содержал агентские runbooks, host-state snapshots,
  reference scripts и исторические task artifacts;
- старый `SYSTEM/` больше не использовался как рабочее хранилище документов;
- пустые каталоги были удалены без удаления файлов.

## Выполнено

- Root human docs перенесены из корня `MIKROTIK/` в `docs/`.
- `MikroTik_Quick_Guide.md` перенесен из `docs/runbooks/human/` в `docs/`.
- `TimeWeb_VPN_Registry.md`, `TimeWeb_Client_Creation.md`,
  `TimeWeb_Parameters.md`, `Cenuta_Parameters.md`, `Fornex_Parameters.md`
  перенесены из `SYSTEM/` в `docs/`.
- `TimeWeb_Configuration.md`, `Cenuta_Configuration.md`,
  `Fornex_Configuration.md` перенесены в `docs/agents/host-state/`.
- `TimeWeb_Agent_Operations.md` перенесен в `docs/agents/runbooks/`.
- Reference scripts `commands.sh`, `wg-status`, `apply-ru-bth.sh` перенесены в
  `docs/agents/reference/timeweb-scripts/`.
- Исторические workplans из `docs/architecture/` перенесены в
  `docs/history/workplans/`.
- Старые archive summaries из `SYSTEM/*/archive/` перенесены в
  `docs/history/{timeweb,cenuta,fornex}/`.
- Старые `SYSTEM` index/redirect README сохранены в
  `docs/agents/deprecated/old-system-index/`.
- Пустые каталоги старой структуры удалены через `rmdir`.
- Skill `create-timeweb-vpn-client` обновлен на новые пути.

## Проверки

- Старые ссылки на `SYSTEM/`, `docs/architecture`, `docs/runbooks/human`,
  `docs/analysis`, `docs/archive`, `docs/catalog`, `mikrotik-quik-guide` не
  найдены.
- Пустые каталоги в `MIKROTIK/` не найдены.
- В корне `MIKROTIK/` остались только `README.md` и `.DS_Store`.
- Secret-like scan по `PrivateKey =` / `PresharedKey =` после redaction не
  находит значений, отличных от `<redacted>`.

## Текущее правило

- Human docs: `docs/`.
- Agent docs/history/reference: `docs/agents/`.
- Full client configs: `.local/clients`.
- Full/evidence backups: `.local/backups`.
