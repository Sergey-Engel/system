---
type: plan
topic: mikrotik
status: draft
created: 2026-07-09
tags:
  - mikrotik
  - vpn
  - storage
  - reorganization
  - plan
---

## Цель

Target outcome: привести хранение MikroTik/WireGuard/hosting-документов к
однозначной схеме, где Obsidian хранит знания и инструкции, Dropbox `System`
хранит конфиги, backup-и и импортируемые файлы, а старые артефакты не удаляются,
а переводятся в `Deprecated`.

Этот документ является планом. В ходе анализа файлы не перемещались и не
удалялись.

## Проверенные корни

- Obsidian Vault:
  `/Users/sergey/Library/CloudStorage/Dropbox/Obsidian/Personal/RESOURCE/IT/MIKROTIK`
- Dropbox Directory:
  `${SYSTEM_ROOT}`

## Текущее состояние

### Obsidian

В Obsidian сейчас одновременно лежат:

- канонические документы по узлам:
  - `docs/agents/host-state/TimeWeb/TimeWeb_Parameters.md`
  - `docs/agents/host-state/TimeWeb/TimeWeb_Configuration.md`
  - `docs/agents/host-state/TimeWeb/TimeWeb_VPN_Registry.md`
  - `docs/agents/host-state/Cenuta/Cenuta_Configuration.md`
  - `docs/agents/host-state/Fornex/Fornex_Configuration.md`
- человеческие инструкции и обзорные документы:
  - `docs/MikroTik_Quick_Guide.md`
  - `docs/Cenuta_VPS_инструкция_2026-06-22.md`
  - `docs/Турецкие хостинг провайдеры 2026-июнь.md`
- рабочие документы старых задач:
  - `docs/architecture/*_Workplan.md`
  - `docs/agents/host-state/TimeWeb/archive/2026-*`
- sanitized backup/evidence-файлы:
  - `configs_sanitized.txt`
  - `runtime_verification.txt`
  - `file_metadata.txt`
  - `SHA256SUMS`
- копии рабочих скриптов TimeWeb:
  - `docs/agents/host-state/TimeWeb/commands.sh`
  - `docs/agents/host-state/TimeWeb/apply-ru-bth.sh`
  - `docs/agents/host-state/TimeWeb/wg-status`

По типам файлов в разделе MikroTik найдено примерно:

- `56` markdown-документов;
- `50` txt/evidence-файлов;
- `11` png-вложений;
- `9` yaml-файлов;
- `2` shell-скрипта и один `wg-status` без расширения.

Проблема: `SYSTEM/*/backups` в Obsidian фактически стал смесью task-log,
sanitized backup, runtime evidence и чекпоинтов. Это мешает отличать текущее
состояние от истории работ.

### Dropbox System

В Dropbox `System` сейчас одновременно лежат:

- актуальный плоский каталог client configs:
  `.local/clients`
- старый WireGuard-контур:
  `${SYSTEM_ROOT}/WireGuard`
- старые backup-снимки WireGuard:
  `${SYSTEM_ROOT}/wg_backup`
- MikroTik exports/backups:
  `${SYSTEM_ROOT}/Mikrotik`
- отдельные файлы в корне `System`:
  - `wireguard1.conf`
  - `mikrotik.config`
  - `README_VPN_DETECTION.md`
  - `backup-wg-server.ps1`
  - `Switchy.exe`

По типам файлов в `System` найдено примерно:

- `153` `.conf`;
- `309` `.key`;
- `59` `.txt`;
- `17` `.sh`;
- `10` `.md`;
- `5` `.rsc`;
- `4` `.env`;
- `4` `.yml`.

Текущий актуальный каталог `/.local/clients` содержит `32` импортируемых
WireGuard `.conf` и уже имеет правильное правило: хранить только актуальные
client configs в плоской структуре.

Старый каталог `/System/WireGuard/vpn-configs/clients` содержит старые имена
устройств, разложенные `private.key`, `public.key`, `psk.key`, `qr.txt` и
устаревшие `.conf`. Он не соответствует текущей naming convention.

Каталог `/System/wg_backup` содержит несколько полных backup-снимков 2026-04-26
с клиентскими ключами, server configs, `.env`, scripts и Docker compose. Это
backup-данные, но они лежат рядом с активной рабочей структурой.

## Основные проблемы

1. Нет явного SSOT для каждого типа артефакта.
2. Obsidian смешивает документацию, runtime evidence, backup-материалы и копии
   скриптов.
3. Dropbox смешивает актуальные конфиги, старые конфиги, backup-и, утилиты и
   одиночные файлы в корне.
4. Старые каталоги не помечены как deprecated, поэтому агент может принять их за
   актуальное состояние.
5. `.local/clients` уже является актуальным рабочим каталогом, но он расположен
   отдельно от `System/Mikrotik`, `System/WireGuard` и `System/wg_backup`.
6. Старые документы задач и текущие документы состояния лежат рядом.
7. Нет единого правила: что делать после создания/удаления/переименования
   клиента, где обновлять README, где хранить полный конфиг, где хранить
   отчет/checkpoint.

## Целевая модель

### Правило уровней

Obsidian хранит:

- каноническое текущее состояние;
- инструкции для человека;
- инструкции для агента;
- реестры и индексы;
- планы и отчеты работ;
- ссылки на backup/config locations в Dropbox;
- sanitized summaries без private keys, preshared keys, QR-кодов и полных
  client configs.

Dropbox `System` хранит:

- полные client configs;
- полные backup-и;
- router exports;
- server-side script snapshots;
- old/deprecated config trees;
- временные staging-файлы перед верификацией.

### Рекомендуемая орфография

Использовать `Deprecated`, а не `Depricated`. В запросе указано `Depricated`,
но лучше не закреплять ошибку в структуре. Если нужна совместимость с прежней
оговоркой, можно создать README с пометкой "Depricated is a typo; use
Deprecated", но не плодить две папки.

## Целевая структура Obsidian

```text
Personal/RESOURCE/IT/MIKROTIK/
  README.md
  SYSTEM/
    README.md
    TIMEWEB/
      README.md
      current/
        TimeWeb_Parameters.md
        TimeWeb_Configuration.md
        TimeWeb_VPN_Registry.md
      runbooks/
        human/
          TimeWeb_Client_Creation.md
          TimeWeb_Quick_Guide.md
        agent/
          TimeWeb_Agent_Operations.md
          TimeWeb_Backup_Rules.md
      tasks/
        2026-07-09_storage_reorganization/
        2026-07-09_client_creation_batch/
      archive/
        2026-06-29_timeweb_selector_implementation/
        2026-07-09_device_tunnel_changes/
      Deprecated/
    CENUTA/
      README.md
      current/
      runbooks/
        human/
        agent/
      tasks/
      archive/
      Deprecated/
    FORNEX/
      README.md
      current/
      runbooks/
        human/
        agent/
      tasks/
      archive/
      Deprecated/
  docs/
    runbooks/
      human/
      agent/
    architecture/
    analysis/
    archive/
    Deprecated/
```

Допустимое упрощение для первой итерации: не переносить сразу текущие
`TimeWeb_*.md` в `current/`, а сначала создать README с правилами и
подготовить карту переноса. Но финальная структура должна отделить `current`
от `tasks/archive`.

## Целевая структура Dropbox System

Вариант с минимальным количеством новых корней:

```text
System/Mikrotik/
  README.md
  current/
    clients/
      timeweb/
        *.conf
      bth/
        *.conf
    router/
      exports/
      backups/
    hosts/
      timeweb/
        scripts/
        state/
      cenuta/
      fornex/
  backups/
    timeweb/
      2026-07-09T1510Z-engel-samsung-pad-cenuta-ru/
    cenuta/
    fornex/
    mikrotik-router/
  staging/
    incoming/
    validation/
  Deprecated/
    2026-04-26_legacy_wireguard_tree/
    2026-04-26_legacy_wg_backup/
    2026-07-09_root_system_loose_files/
```

Переходный вариант, если не хотим сразу ломать существующие ссылки:

```text
.local/clients/                    # временно остается активным SSOT
.local/backups/
System/Mikrotik/Deprecated/
System/WireGuard/                  # пометить как deprecated и затем перенести
System/wg_backup/                  # пометить как deprecated и затем перенести
```

Рекомендация: финально перенести `.local/clients` в
`System/Mikrotik/current/clients/timeweb/`, но только после обновления:

- `create-timeweb-vpn-client` skill;
- `TimeWeb_Client_Creation.md`;
- `TimeWeb_VPN_Registry.md`;
- всех README, где указан `/.local/clients`;
- проверок после создания новых клиентов.

## Классификация артефактов

| Тип артефакта | Целевое место | Комментарий |
| --- | --- | --- |
| Текущее состояние узла | Obsidian `SYSTEM/<NODE>/current/` | Без секретов, source of truth для чтения |
| Инструкция для человека | Obsidian `runbooks/human/` | Команды, сценарии, понятные пояснения |
| Инструкция для агента | Obsidian `runbooks/agent/` и Codex skill | Стоп-линии, проверки, запреты, пути |
| Рабочий план новой задачи | Obsidian `tasks/YYYY-MM-DD_slug/` | До завершения задачи |
| Завершенный task/checkpoint | Obsidian `archive/YYYY-MM-DD_slug/` | История без смешивания с current |
| Полный client config | Dropbox `current/clients/...` | Содержит private key, не в Obsidian |
| Router export `.rsc` / `.backup` | Dropbox `current/router/` или `backups/mikrotik-router/` | Не в Obsidian |
| Полный server backup | Dropbox `backups/<host>/<timestamp>/` | При наличии секретов лучше шифровать |
| Sanitized runtime evidence | Dropbox backup evidence + ссылка из Obsidian | В Obsidian хранить только summary |
| Старые конфиги и backup trees | Dropbox `Deprecated/YYYY-MM-DD_reason/` | Не удалять |
| Старые документы задач | Obsidian `archive/` или `Deprecated/` | Дата в имени или папке обязательна |
| Копии host scripts | Dropbox backup/current scripts | В Obsidian только описание и команды |

## Что считать каноническим после реорганизации

### Obsidian canonical current

- `TimeWeb_VPN_Registry.md` - текущий реестр VPN клиентов, файлов, IP и
  маршрутов.
- `TimeWeb_Configuration.md` - текущее фактическое устройство TimeWeb.
- `TimeWeb_Parameters.md` - доступы, endpoints, команды, порты, ключевые пути.
- `docs/MikroTik_Quick_Guide.md` - быстрые команды для человека.
- отдельный agent runbook - как агенту создавать/удалять/проверять клиентов.

### Dropbox canonical current

- один каталог полных импортируемых client configs;
- один каталог актуальных MikroTik exports/backups;
- один каталог host script snapshots;
- один backup-каталог по хостам.

## Кандидаты на перенос в Deprecated

### Dropbox

Перенести в `System/Mikrotik/Deprecated/2026-04-26_legacy_wireguard_tree/`:

- `System/WireGuard/vpn-configs/clients/*`
- старые root configs из `System/WireGuard/*.conf`
- старые инструкции `System/WireGuard/README.md`, `INSTALLATION.md`,
  `ubuntu-update.md`, `wg-sys-doc.md`, `wishes.md`, если их содержание уже
  покрыто Obsidian runbooks.

Перенести в `System/Mikrotik/Deprecated/2026-04-26_legacy_wg_backup/`:

- `System/wg_backup/wg_backup_20260426-*`

Рассмотреть отдельно:

- `System/wireguard1.conf`
- `System/mikrotik.config`
- `System/README_VPN_DETECTION.md`
- `System/backup-wg-server.ps1`
- `System/Switchy.exe`
- `System/ec2-44-222-170-97.compute-1.amazonaws.com.rdp`

Перед переносом каждого одиночного файла нужно проверить, не используется ли он
вне MikroTik/VPN-контекста.

### Obsidian

Перенести из `SYSTEM/*/backups`:

- bulk evidence файлы (`*.txt`, `SHA256SUMS`, `*.sanitized`) в Dropbox backup
  evidence;
- оставить или создать в Obsidian короткий `README.md`/checkpoint summary со
  ссылкой на Dropbox backup path.

Перенести в `SYSTEM/<NODE>/archive/YYYY-MM-DD_slug/`:

- завершенные `*_Workplan.md`;
- checkpoint README старых задач;
- task reports, которые не являются текущей конфигурацией.

Перенести в `SYSTEM/<NODE>/Deprecated/`:

- документы с устаревшими именами клиентов;
- инструкции, которые описывают старый `/opt/wg` legacy-процесс вместо текущего
  `/opt/wg-router/commands.sh`, если они не нужны как historical reference.

## Что не переносить без отдельного решения

- `artifacts/`, `akb/`, `.antigravity/` - это ADK-структура проекта, ее лучше не
  трогать в рамках storage cleanup.
- `attachments/` - изображения для Obsidian-документов; переносить только если
  конкретный документ переводится в archive/deprecated.
- `Current_Mikrotik_hAP_ax3_Config.md` - вероятно current-state документ; перед
  переносом нужно сверить дату и актуальность.
- `docs/VPN_HLD.md` - архитектурный документ, не backup.

## Правила именования

### Документы current

Без даты в имени, потому что это живой текущий документ:

```text
TimeWeb_Configuration.md
TimeWeb_Parameters.md
TimeWeb_VPN_Registry.md
MikroTik_Current_Config.md
```

### Рабочие задачи

Дата в папке или имени обязательна:

```text
tasks/2026-07-09_storage_reorganization/PLAN.md
tasks/2026-07-09_storage_reorganization/REPORT.md
archive/2026-06-29_timeweb_selector_implementation/README.md
```

### Dropbox backup-и

```text
backups/timeweb/2026-07-09T1510Z_engel_samsung_pad_cenuta_ru/
backups/mikrotik-router/2026-07-09T1200Z_before_route_change/
```

### Deprecated

```text
Deprecated/2026-07-09_legacy_wireguard_tree/
Deprecated/2026-07-09_old_root_system_files/
```

## Правила backup-процесса

### Перед live-изменением

1. Создать серверный backup штатной командой.
2. Зафиксировать путь backup в task log.
3. Если backup копируется локально и содержит private keys/PSK, хранить его
   только в Dropbox `.local/backups/...`, не в Obsidian.
4. В Obsidian записывать только:
   - путь backup;
   - список покрытых файлов;
   - checksum/manifest;
   - результат проверки восстановления или хотя бы проверки наличия ключевых
     файлов.

Для TimeWeb базовая команда:

```bash
/opt/wg-router/commands.sh backup
```

После создания/удаления/переименования клиента:

1. Обновить полный `.conf` в Dropbox current clients.
2. Обновить `TimeWeb_VPN_Registry.md`.
3. Обновить task/checkpoint summary.
4. Проверить `sessions`, state-файлы и route test.
5. Проверить, что устаревшие `.conf` не остались в current-каталоге.

### Что не делать

- Не хранить private keys, preshared keys, QR-коды и полные client configs в
  Obsidian.
- Не оставлять старый backup tree в активной зоне без `Deprecated`.
- Не копировать весь `/opt/wg` в Obsidian даже в sanitized виде, если это не
  текущий короткий отчет.
- Не удалять старые артефакты без отдельного подтверждения.

## План выполнения

### Фаза 0. Read-only validation

Status: частично выполнено этим документом.

Scope:

- снять список каталогов и типов файлов;
- определить active/current и legacy/deprecated candidates;
- не перемещать файлы.

Acceptance:

- есть план с целевой структурой;
- есть список кандидатов на перенос;
- есть stop-lines и backup rules.

### Фаза 1. Ввести README и правила, ничего не переносить

Status: Ready for Codex after approval.

Действия:

- обновить `Personal/RESOURCE/IT/MIKROTIK/README.md`;
- обновить `Personal/RESOURCE/IT/MIKROTIK/SYSTEM/README.md`;
- создать или обновить `System/Mikrotik/README.md`;
- явно объявить временный current SSOT:
  - Obsidian current docs;
  - Dropbox `.local/clients`.

Acceptance:

- README объясняют, где хранить docs/current/tasks/backups/configs;
- старые каталоги помечены как legacy/deprecated candidates, но еще не
  перемещены.

### Фаза 2. Разделить Obsidian current/runbooks/tasks/archive

Status: Needs approval.

Действия:

- создать `current/`, `runbooks/human/`, `runbooks/agent/`, `tasks/`,
  `archive/`, `Deprecated/` в `docs/agents/host-state/TimeWeb`, `docs/agents/host-state/Cenuta`,
  `docs/agents/host-state/Fornex`;
- перенести текущие `TimeWeb_*.md` в `current/` или оставить временно на месте
  и создать redirects/index;
- перенести quick guide и client creation docs в `runbooks/human/`;
- создать agent runbook с точными правилами работы;
- перенести старые workplans/checkpoints в `archive/YYYY-MM-DD_slug/`;
- обновить wikilinks.

Acceptance:

- current docs больше не смешаны с task artifacts;
- `rg` по старым именам файлов не показывает битых ссылок;
- Obsidian backlinks сохранены или заменены.

### Фаза 3. Перенести backup/evidence из Obsidian в Dropbox

Status: Needs approval.

Действия:

- создать `.local/backups/{timeweb,cenuta,fornex,mikrotik-router}`;
- перенести bulk evidence из `SYSTEM/*/backups/` в соответствующие Dropbox
  backup-папки;
- в Obsidian оставить короткие checkpoint README и ссылки на Dropbox path;
- проверить, что в Obsidian не осталось `configs_sanitized.txt`,
  `runtime_verification.txt`, `file_metadata.txt`, `SHA256SUMS` в active
  current-разделах.

Acceptance:

- backup/evidence больше не раздувает Obsidian current tree;
- checkpoint summary остается читаемым в Obsidian;
- все moved paths отражены в README.

### Фаза 4. Нормализовать Dropbox current configs

Status: Needs approval.

Действия:

- выбрать финальный путь:
  - либо оставить `.local/clients`;
  - либо перенести в `System/Mikrotik/current/clients/timeweb`.
- если переносим, обновить:
  - `create-timeweb-vpn-client` skill;
  - `TimeWeb_Client_Creation.md`;
  - `TimeWeb_VPN_Registry.md`;
  - `.local/clients/README.md` или заменить его на redirect README;
  - все команды копирования `scp`.
- проверить, что текущих импортируемых `.conf` ровно столько же, сколько в
  реестре current client configs.

Acceptance:

- один current-каталог client configs;
- нет конкурирующих current-каталогов;
- после тестового `find` старые client configs встречаются только в
  `Deprecated` или `backups`.

### Фаза 5. Перевести старые Dropbox каталоги в Deprecated

Status: Needs approval.

Действия:

- создать `System/Mikrotik/Deprecated/2026-07-09_legacy_wireguard_tree`;
- переместить туда `System/WireGuard`;
- создать `System/Mikrotik/Deprecated/2026-07-09_legacy_wg_backup`;
- переместить туда `System/wg_backup`;
- отдельно разобрать loose files в корне `System`.

Acceptance:

- `System/WireGuard` и `System/wg_backup` не выглядят активными;
- README в `Deprecated` объясняет, почему каталог сохранен;
- ни один текущий процесс не ссылается на deprecated paths.

### Фаза 6. Обновить agent memory/skills

Status: Needs approval.

Действия:

- обновить skill `create-timeweb-vpn-client` с новым путем client config cache;
- добавить правило: после любого изменения VPN клиента обновлять Dropbox
  current configs и Obsidian registry;
- добавить правило: backup/evidence хранить в Dropbox, summary в Obsidian;
- при необходимости добавить ADK memory note.

Acceptance:

- будущие задачи создания клиентов не возвращают файлы в старый каталог;
- в skill нет ссылок на deprecated paths;
- новая структура отражена в quick guide.

## Stop-lines

Остановиться и запросить подтверждение, если:

- нужно переместить или переименовать файлы с private keys/PSK;
- нужно менять путь `/.local/clients`, потому что он зашит в текущий процесс
  создания клиентов;
- обнаружены full configs или ключи в Obsidian;
- есть файл, назначение которого неясно;
- есть активная ссылка из документа или skill на каталог, который предлагается
  перевести в `Deprecated`;
- требуется удалить, а не переместить.

## Проверки после реорганизации

Команды проверки:

```bash
find /Users/sergey/Library/CloudStorage/Dropbox/Obsidian/Personal/RESOURCE/IT/MIKROTIK -type f \
  \( -name '*.conf' -o -name '*.key' -o -name 'qr.txt' \)

find ${SYSTEM_ROOT}/Mikrotik/current -type f -name '*.conf'

rg -n '/.local/clients|System/WireGuard|System/wg_backup|SYSTEM/.*/backups' \
  /Users/sergey/Library/CloudStorage/Dropbox/Obsidian/Personal/RESOURCE/IT/MIKROTIK \
  /Users/sergey/.codex/skills

find ${SYSTEM_ROOT}/Mikrotik/Deprecated -maxdepth 2 -type d
```

Критерии готовности:

- в Obsidian нет private keys, PSK, QR и полных client configs;
- один current-каталог client configs в Dropbox;
- старые каталоги физически сохранены, но находятся в `Deprecated`;
- текущие документы состояния отделены от рабочих task artifacts;
- README на каждом уровне объясняет назначение папок;
- skill и quick guide указывают на новую структуру;
- создание нового тестового клиента не создает файлов в deprecated paths.

## Открытые вопросы

1. Финальный current path для client configs:
   - оставить `/.local/clients`;
   - или перенести в `/System/Mikrotik/current/clients/timeweb`.
2. Нужны ли full server backups в Dropbox без шифрования, или вводим правило
   шифрования для backup-ов с private keys.
3. Сохраняем ли sanitized runtime evidence в Obsidian archive, или переносим
   весь evidence в Dropbox.
4. Нужна ли отдельная структура для не-MikroTik файлов в `System`
   (`Switchy.exe`, `.rdp`, workspace file), чтобы не смешивать с VPN.
5. Нужно ли разделять Dropbox current clients по провайдерам (`timeweb`,
   `cenuta`, `fornex`) или хранить плоско, как сейчас.

## Рекомендация

Начать с консервативной схемы:

1. Утвердить этот план.
2. Обновить README и объявить временный SSOT без перемещения файлов.
3. Перенести backup/evidence и старые Dropbox trees в `Deprecated`.
4. Только после этого решать, переносить ли активный `/.local/clients`.

Такой порядок снижает риск сломать текущий процесс создания VPN-клиентов и
позволяет сразу убрать главную неоднозначность: старые конфиги и backup-и не
будут выглядеть как актуальные.

## Выполнено 2026-07-09

Статус: консервативная реорганизация выполнена без переноса активного
`.local/clients`.

Сделано:

- создана целевая Dropbox-структура `System/Mikrotik/{current,backups,staging,Deprecated}`;
- создана целевая Obsidian-структура `SYSTEM/<NODE>/{current,runbooks,tasks,archive,Deprecated}`;
- добавлены README:
  - `README.md`;
  - `${SYSTEM_ROOT}/Mikrotik/README.md`;
  - `.local/backups/README.md`;
  - `${SYSTEM_ROOT}/Mikrotik/Deprecated/README.md`;
  - `docs/agents/host-state/TimeWeb/runbooks/agent/TimeWeb_Agent_Operations.md`;
- старые Dropbox trees перемещены в Deprecated:
  - `System/WireGuard` -> `System/Mikrotik/Deprecated/2026-07-09_legacy_wireguard_tree/WireGuard`;
  - `System/wg_backup` -> `System/Mikrotik/Deprecated/2026-07-09_legacy_wg_backup/wg_backup`;
- Obsidian `SYSTEM/*/backups/20*` перемещены в `SYSTEM/*/archive/20*`;
- не-README evidence из Obsidian archive вынесен в Dropbox:
  - `.local/backups/timeweb/<checkpoint>/evidence/`;
  - `.local/backups/cenuta/<checkpoint>/evidence/`;
  - `.local/backups/fornex/<checkpoint>/evidence/`;
- старые RouterOS exports/backups из `System/Mikrotik` root перемещены в
  `.local/backups/mikrotik-router/2026-07-09_legacy_root_exports`;
- `russia.rsc` перемещен в `System/Mikrotik/current/router/ip-lists/russia.rsc`;
- `codex_mikrotik_20260704.pub` перемещен в `System/Mikrotik/current/router/keys/codex_mikrotik_20260704.pub`;
- старые loose VPN/MikroTik файлы из `System` root перемещены в
  `System/Mikrotik/Deprecated/2026-07-09_root_system_loose_files`;
- legacy markdown docs из Dropbox перенесены в
  `docs/archive/2026-07-09_system_legacy_docs`;
- skill `create-timeweb-vpn-client` обновлен: новые task checkpoints теперь
  создаются в `docs/agents/host-state/TimeWeb/archive/<timestamp>-<slug>/README.md`.

Текущее решение:

- active full client config cache остается:
  `.local/clients`;
- future checkpoint summaries создаются в Obsidian `archive`;
- full/evidence backups хранятся в Dropbox `.local/backups`;
- `SYSTEM/*/backups` оставлены только как redirect README на `archive`.
