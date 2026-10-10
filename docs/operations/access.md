# Host Access

## Подготовка

Точные существующие ключи и доверенные host keys материализуются из
[.local/secrets.json](../../.local/secrets.json), не создаются заново:

```sh
.venv/bin/python -B scripts/setup_mac.py
.venv/bin/python -B scripts/setup_mac.py --install
```

Первая команда только материализует private files и SSH config. Вторая
сохраняет старые bindings, ставит launcher, SSH include и monitoring LaunchAgents.
Повторный запуск не заменяет пользователей/ключи на сервере. Подробнее:
[перенос на другой Mac](storage-and-transfer.md).

Нельзя пересылать содержимое ключа агенту в чат. Дать агенту эту инструкцию,
корень checkout и разрешение использовать уже имеющиеся локальные файлы.
Если среда не видит `.local`, это ограничение доступа среды, не отсутствие ключа.
Full config/QR/пароли не выводить в tool output или общие логи.

## Узлы

| Alias | Адрес | Пользователь | Private key относительно корня |
| --- | --- | --- | --- |
| `timeweb` | `94.241.171.65` | `root` | `.local/ssh/codex_timeweb_audit_20260628` |
| `fornex` | `103.75.126.143` | `root` | `.local/ssh/codex_fornex_audit_20260628` |
| `cenuta` | `89.252.153.129` | `ubuntu` | `.local/ssh/codex_cenuta_audit_20260628` |
| `mikrotik-nakhimova` | `10.30.30.2`, через TW | `codex` | `.local/ssh/codex_mikrotik_20260704` |
| `mikrotik-orekhovo` | `192.168.88.1`, локальная сеть Орехово | `codex_audit` | `.local/ssh/codex_mikrotik_orekhovo_audit_rsa` |

`timeweb-console` использует тот же TimeWeb identity, добавляя локальный
forward `19118 -> 127.0.0.1:19108`. `timeweb-vpn` управляет его жизненным циклом.
Полный SSH config: [.local/ssh/config](../../.local/ssh/config).
Глобальные aliases и фоновый forward используют идентичный сгенерированный
config из private runtime cache; [причина и правила](storage-and-transfer.md).
Для отдельной команды без глобальной установки:

```sh
ssh -F .local/ssh/config timeweb hostname
ssh -F .local/ssh/config fornex hostname
ssh -F .local/ssh/config cenuta hostname
ssh -F .local/ssh/config mikrotik-nakhimova '/system identity print; /system routerboard print'
```

## Проверка правильного узла

- VPS: hostname, OS и ожидаемый provider IP. Cenuta `ubuntu` использует
  существующий административный `sudo`, не новый root-login.
- Нахимова: hAP ax3, serial `HKM0BDXYG74`; `codex` имеет `full`.
- Орехово: hEX RB750Gr3, serial `8AFF0A501C19`; `codex_audit` имеет `ssh,read`.
  На 10 октября из внешней сети SSH к Орехово недоступен; remote management
  route не придумывать и не публиковать новый WAN management port.

SSH Нахимова использует существующий TimeWeb key и proxy через `wg-relay`.
`HostKeyAlias 192.168.88.1` проверяет ранее доверенный ключ именно Нахимова.
У Орехово отдельный `known_hosts_orekhovo`, у Cenuta `known_hosts_cenuta`.
Остальные узлы используют `.local/ssh/known_hosts`. Не переносить один
`192.168.88.1` trust record между двумя площадками.

## Ограничения

`StrictHostKeyChecking=yes`, `IdentitiesOnly=yes`, `BatchMode=yes`,
password authentication и agent forwarding выключены. RSA compatibility
включена только для старого RouterOS Орехово. При смене host key остановиться,
подтвердить fingerprint, не делать автоматический `ssh-keygen -R` и не
выключать host-key check. `ssh-keyscan` сам по себе не подтверждает подлинность.

Наличие root/full не даёт агенту права изменять узел без поручения. Перед
согласованными изменениями нужны свежие backups и точный rollback. Не
выдавать дополнительные права Орехово как обход ошибки создания backup.
SSH-ключи не равны PKI/WSS-сертификатам: оба вида отдельно сохранены локально.
