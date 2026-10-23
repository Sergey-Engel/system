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

Фетхие добавлена 16 октября: новый hAP ax3 `HM20B6QXS8H`, динамический WAN
`192.168.68.117` за Deco. С23 октября по явному запросу владельца SSH/TCP22
разрешён с192.168.68.0/24 только через ether1; правило local-admin-ssh-deco-v1.
HTTP/TCP80 остаётся доступен только с192.168.68.115, как и прежде.
Публичный SSH, управление через VPN и другие порты не открывались.
Это доверие всей локальной сети Deco для попыток SSH-входа, не обход
аутентификации. [Изменение и откат](../history/2026-10-23-local-ssh-access.md).
Используется существующий admin. 16 октября в 10:09-10:12 Europe/Istanbul
с разрешения пользователя добавлен ключ входа RSA 4096
`.local/ssh/fethiye_admin_rsa`, public key-owner
`codex-fethiye-admin-20261016T070953Z`. Повторный strict SSH без пароля проверен;
вход SSH только с паролем отклонен. Новых пользователей не создавали.
Браузерный пароль прежний (`access:fethiye:admin`); пользователь явно решил
сохранить его 16 октября. Не ротировать без нового поручения. Риск передачи
пароля в чат остается; SSH-ключ не устраняет риск для WebFig.
Первоначальный `.local/ssh/known_hosts_fethiye` закреплен по public key,
прочитанному в авторизованном WebFig. 16 октября в 09:57 Europe/Istanbul
раскрытый SSH host key заменен: новый RSA 2048 создан локально, передан
зашифрованным PKCS8 по ранее закрепленному SSH и импортирован; временный файл
удален. Новый public key был известен до импорта, strict SSH проверен;
known_hosts и private store синхронизированы. Fingerprint:
`SHA256:eH3GEIpmWD19iX55MwgWYoIoj0J1sA7QUCukDb8GZPc`.
Пароль admin пока не менялся. [Лог и backup после ротации](../tasks/PLAN-fethiye-site-to-site.md).
Автоматический alias не добавлялся. Этот доступ локальный из сети Deco,
не удаленный через TimeWeb. Для входа без глобального SSH config:

```sh
ssh -i .local/ssh/fethiye_admin_rsa -o UserKnownHostsFile=.local/ssh/known_hosts_fethiye -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -o BatchMode=yes -o PasswordAuthentication=no -o ForwardAgent=no admin@192.168.68.117
```

Команда выполняется из корня System; ключ и known_hosts материализуются из
private store. Последняя копия после импорта ключа:
`.local/backups/fethiye/20261016T071211Z-post-admin-key-install/`.
Ограничения, рекомендации по ротации и [backup](../hosts/fethiye/MikroTik_hAP_ax3_Initial_Audit.md).

`StrictHostKeyChecking=yes`, `IdentitiesOnly=yes`, `BatchMode=yes`,
password authentication и agent forwarding выключены. RSA compatibility
включена только для старого RouterOS Орехово. При смене host key остановиться,
подтвердить fingerprint, не делать автоматический `ssh-keygen -R` и не
выключать host-key check. `ssh-keyscan` сам по себе не подтверждает подлинность.

Наличие root/full не даёт агенту права изменять узел без поручения. Перед
согласованными изменениями нужны свежие backups и точный rollback. Не
выдавать дополнительные права Орехово как обход ошибки создания backup.
SSH-ключи не равны PKI/WSS-сертификатам: оба вида отдельно сохранены локально.
