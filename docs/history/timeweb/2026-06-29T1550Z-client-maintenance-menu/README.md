# TimeWeb Client Maintenance Menu Checkpoint

Date: 2026-06-29.

Sanitized checkpoint после добавления интерактивного обслуживания WireGuard client configs на TimeWeb.

## Что изменено

- `sudo wg-client-config` после выбора client config показывает меню:
  - `view`;
  - `delete`;
  - `regenerate`.
- Добавлены прямые команды:
  - `sudo /opt/wg-router/commands.sh delete-client <config-name>`;
  - `sudo /opt/wg-router/commands.sh regenerate-client <config-name>`.
- `delete` удаляет client peer и локальные client files; интерактивно требует подтверждение `DELETE`.
- `regenerate` сохраняет имя/IP клиента, перевыпускает ключи, обновляет peer и всегда показывает новый config и QR-code.
- `backup` расширен: теперь root-only backup включает selector state/configs, legacy `/opt/wg/clients`, BTH `/opt/wg/clients_bth`, active WireGuard server configs и helper scripts.

## Server-Side Backup

Перед установкой новой версии создан backup:

```text
/opt/wg-router/backups/20260629T154639Z-pre-client-maintenance-menu
```

Перед расширением backup-процедуры создан backup:

```text
/opt/wg-router/backups/20260629T155234Z-pre-backup-expansion
```

Финальное проверенное состояние после smoke-test и расширения backup-процедуры:

```text
/opt/wg-router/backups/20260629T155257Z
```

## Проверка

- `bash -n /opt/wg-router/commands.sh`: OK.
- Help показывает `show-client [config-name] [view|delete|regenerate]`, `delete-client`, `regenerate-client`.
- Интерактивный список показывает 27 configs: 4 selector, 21 legacy, 2 bth.
- Smoke-test на временных клиентах прошел для всех типов: selector, legacy, bth.
- Временные smoke logs с private keys удалены.
- Активных ссылок на временные тестовые имена не осталось.

## Files

- `commands_and_docs_sanitized.txt` - sanitized script and docs snapshot.
- `runtime_verification.txt` - verification summary without secrets.
- `SHA256SUMS` - file checksums.
