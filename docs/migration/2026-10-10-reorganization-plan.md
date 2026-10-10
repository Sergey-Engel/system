---
type: migration-plan
status: approved-and-executed
updated: 2026-10-10
---

# MikroTik / VPN: реорганизация рабочего хранилища

Структура согласована пользователем и применена 10 октября. Ниже сохранён исходный план; фактический результат, проверки и ограничения находятся в [execution report](2026-10-10-execution-report.md). Исходные папки не удалялись.

## Результат

`system` становится единым рабочим репозиторием проекта: документация, операционный код, безопасный inventory, шаблоны конфигураций и инструкции агента. Реальные ключи, импортируемые профили, applied-конфиги, резервные копии и runtime-данные остаются локальными в `.local/`, исключённой из Git. Репозиторий уже имеет remote `Sergey-Engel/system`, ветку `main`; на момент проверки коммитов и рабочего содержимого не было.

Весь перенос выполняется копированием с адаптацией целевых копий. Старые файлы остаются на месте; их последующее удаление выполняет пользователь после приёмки. Серверные VPN-профили и ключи сохраняют действующую идентичность.

## Источники и обнаруженные расхождения

| Источник | Фактический состав | Решение |
| --- | --- | --- |
| Obsidian `Personal/RESOURCE/IT/MIKROTIK` | 197 файлов, включая 125 Markdown; документация, host-state, history, интерактивные схемы, изображения и старый knowledge scaffold | Перенести рабочие документы; единый индекс; текущие схемы; связанную историю. Старые raw exports и пустой scaffold исключить |
| Dropbox `System/clients` | 65 профилей в 21 каталоге устройств: 36 WG, 11 AWG31, 9 XRAY, 9 SOCKS | Сохранить текущие файлы в `.local/clients/`; зарегистрировать секретные identity в едином локальном файле |
| Dropbox `System/transport` | 797 файлов: действующий код, PKI, credentials, дубли профилей, этапные снимки, lab, vendor и evidence | Выделить код и шаблоны; извлечь текущие секреты; исключить старые configs/backups и завершённые миграции |
| Dropbox `System/monitoring` | 1 412 файлов; из них 1 134 файла живых Grafana/Prometheus data | Код в `services/monitoring/`; свежий согласованный snapshot data и переключение bind mounts в `.local/runtime/` |
| Dropbox `System/Mikrotik` | 1 230 файлов, примерно 639 MiB; старые RouterOS exports, backups и Deprecated | Не копировать старую конфигурационную историю; снять новые архивы с хостов и обоих роутеров |
| Локальная интеграция Mac | `timeweb-vpn` symlink и два LaunchAgent указывают на Dropbox; ключи и trust stores находятся в `~/.ssh` | Обновить установку launcher/LaunchAgent; существующие SSH identity зарегистрировать в локальном переносимом хранилище |
| Канонический VPN skill в Vault | Инструкции выдачи туннелей содержат старые абсолютные пути | Адаптировать одну проектную копию skill; `AGENTS.md` ссылается на общую процедуру |
| Выбранный System Design skill | Шаблон документа с retained reference DOCX | Использовать для оформленного проекта миграции; plugin cache не переносится как материал MikroTik |

Общий обследованный состав двух основных деревьев: **3 711 файлов, 1 168 465 376 байт**, без `.git`, virtualenv, `node_modules`, Python caches и `.DS_Store`. Обнаружены **344 группы одинакового содержимого** среди файлов до 8 MB и **289 файлов с привязками к прежним путям**. Это не означает, что все одинаковые файлы можно удалить: fixtures, generated outputs и frozen evidence имеют разные роли.

Количество профилей в ряде README устарело: встречаются 52 и 63, текущий каталог содержит 65. `backup_local.py` закрепляет число 52 и отказывает при новом составе. При адаптации заменить этот gate сверкой ожидаемого inventory и фактического набора, сохранив проверку полноты.

## Предлагаемая структура

```text
system/
  README.md                         # вход для человека; карта проекта
  AGENTS.md                         # один вход для агента
  .gitignore
  .agents/skills/create-timeweb-vpn-client/
  docs/
    quick-start.md                  # запуск, доступ, основные проверки
    architecture/                   # общая схема, маршруты, транспорт, DNS
      diagrams/                     # текущие интерактивные HTML-схемы
    operations/                     # access, backup, recovery, tunnel lifecycle
      agent-workflow.md             # общая эксплуатационная процедура агента
    hosts/{timeweb,fornex,cenuta,nakhimova,orekhovo}/
    registry/                       # tunnel inventory и master/runtime registry
    reference/                      # оборудование, справки, исследования
      assets/                       # проверенные связанные изображения
    history/                        # датированные текстовые решения/инциденты
    migration/                      # план, карта переноса, результаты приёмки
  services/
    transport/
      timeweb-reality/              # FLEX, BTH, backup и recovery helpers
      fornex-awg31/                 # текущие исходники и сборочные инструкции
    monitoring/
      timeweb-uplinks/              # collector, console, guards, launcher
      vpn-connectivity/             # probes, provisioning, Compose
  config/
    inventory/                      # безопасные hosts/devices/tunnels
    templates/                      # конфиги с secret references
  scripts/                          # setup, backup, проверки путей/секретов
  .local/                           # полностью исключена из Git
    secrets.json                    # единый локальный файл секретов
    clients/                        # текущие профили импорта по устройствам
    config/                         # полные applied-конфиги и PKI
    ssh/                            # materialized existing keys/trust stores
    backups/{timeweb,fornex,cenuta,nakhimova,orekhovo,local}/
    runtime/monitoring/              # живые Grafana/Prometheus данные
    evidence/                       # приватные результаты новой приёмки
```

В пределах `services/` сохраняются внутренние имена каталогов и файлов, когда на них завязаны Python imports, относительные пути и deployment packaging. Вынос состояния и секретов требует точечной адаптации reader/writer paths; простое перемещение каталога недостаточно.

Новые `AGENTS.md` и skill будут направлять агента к `docs/quick-start.md`, host inventory и `docs/operations/agent-workflow.md`. Правила lifecycle, публикации профиля, обновления inventory/Grafana и recovery policy описываются в одном месте. Датированные журналы не являются второй актуальной инструкцией.

## Карта переноса

Для каждого обследованного файла предложены action, destination, reason и исходный checksum в [полной карте CSV](2026-10-10-file-map.csv). Сводка и список credential candidates без значений находятся в [результатах аудита](2026-10-10-audit-summary.json). Оформленный обзор подготовлен в [шаблоне System Design](2026-10-10-system-design.docx). Строки с `review_*` требуют проверки до разрешения копирования; CSV не является готовым автоматическим allowlist. Карта охватывает два основных дерева; внешние SSH-файлы, LaunchAgent и проектный skill учитываются дополнительно перед setup. Hashes исходного аудита рассчитаны для файлов до 8 MB; при переносе контроль содержимого выполняется для всех перенесённых файлов.

| Исходная группа | Целевое место | Операция |
| --- | --- | --- |
| `MikroTik_Quick_Guide.md` | `docs/quick-start.md` | Адаптировать команды и относительные ссылки |
| `VPN_HLD.md`, design docs и текущие HTML | `docs/architecture/` | Перенести с сохранением смысла и статуса реализации |
| `TimeWeb_VPN_Registry.md` | `docs/registry/tunnels.md` | Сверить с текущими 65 профилями; связать с machine inventory |
| `VPN_Configuration_Registry.md` | `docs/registry/configuration.md` | Обновить master/runtime mapping и provenance |
| Access, backup, recovery, creation runbooks | `docs/operations/` | Один актуальный документ на процедуру |
| Parameters, RouterOS observations, host-state | `docs/hosts/<host>/` | Сохранить даты наблюдений; свежие конфиги закрытые |
| Агентские runbooks | `docs/operations/agent-workflow.md` | Объединить повторяющиеся обязательные шаги |
| Агентская текстовая history | `docs/history/` | Сохранить датированные факты; не объявлять прошлую приёмку текущей |
| Code/tests/units/provisioning/Compose | `services/` | Адаптировать пути, secret loading и output directories |
| `System/clients/<owner>/<device>` | `.local/clients/<owner>/<device>` | Текущие импортируемые файлы, byte-for-byte verification |
| Действующие credentials/PKI | `.local/secrets.json` и generated `.local/config/` | Извлечь и связать по secret ID; подтвердить свежим runtime snapshot |
| Live monitoring data | `.local/runtime/monitoring/` | Консистентный snapshot и проверка после переключения |
| Старые `.conf`, stage before/after, backups, Deprecated | Не переносятся | Остаются в старом хранилище для удаления пользователем |
| `.visual-check.*`, caches, PID/log, vendor binaries, completed migration outputs | Не переносятся | QA пересоздать; versions/hashes сохранить; output направить в `.local/` |

Дубли 11 AWG-профилей в `transport/fornex-awg31/` сравниваются с текущим `clients/` по ключам и параметрам, затем в новом хранилище остаётся только пользовательская выдача и её canonical secret record. Не выбирать копию по mtime.

Дубли `docs/agents/reference/timeweb-scripts` сравниваются с текущим кодом и fresh runtime. Сохраняется один рабочий исходник. RETIRED scripts переносить только при доказанной необходимости для текущих imports/tests; guards, запрещающие их старый CLI, сохраняются.

## Секреты и перенос между машинами

Автоматический проход отметил **333 файла-кандидата**, включая старые конфиги, synthetic fixtures и дубли. Значения в аудит и Git не записываются. В текущей текстовой документации подтверждённые значения действующих секретов пока не найдены; один языковой candidate относится к описанию смены пароля в старой заметке и требует ручной проверки. В исходниках явно присутствуют клиентские WG private/PSK, Xray identity, AWG credentials и шесть WSS private key PEM-файлов. Бинарные backups, SQLite и картинки не считаются проверенными текстовым сканером.

**`.local/secrets.json` — один переносимый файл текущих секретов.** Записи получают устойчивые IDs, тип, узел/устройство, источник и значение. В него собираются существующие административные SSH keys, известные passwords/tokens, WG/AWG keys/PSK, REALITY identity и WSS private PKI. Содержимое password manager нельзя восстановить по одной ссылке в документе: такие записи помечаются `unresolved`, значения не придумываются. Старые revoked identities и архивные ключи не переносятся в current secrets.

Full configs и import profiles сохраняются в `.local/` как materialized файлы. Их генерация/извлечение использует canonical records; independent copies credentials больше не редактируются вручную. Приватный исходный архив содержит секреты даже после извлечения: он целиком остаётся вне Git.

Для переноса доступа на другой Mac достаточно передать `secrets.json`; setup материализует необходимые локальные ключи и конфиги с правами directory 700 / file 600. Для переноса также клиентских профилей предусмотрен один локальный `private-transfer.tar.gz` с secrets, current profiles и scoped trust stores. Тяжёлые backups/runtime data в этот пакет по умолчанию не входят. Файл и пакет содержат открытые секреты и передаются приватным каналом; дополнительные encrypted containers не нужны для базовой схемы.

До любого `git add` проверяются публичные копии, diff и staged files; `.local/` проверяется через `git check-ignore`. Приватные архивы, ключи, DB и credentials должны оставаться excluded и после обычного `git add .`. Принудительное `git add -f` исключённых файлов запрещается проектной инструкцией. Gitignore не заменяет проверку содержимого Markdown, JSON, HTML и исходников.

## Свежие архивные копии

Архивы снимаются после согласования структуры напрямую с **TimeWeb, Fornex, Cenuta, Нахимова и Орехово**, по одному узлу. Предыдущие backups не копируются. Для каждого архива: UTC timestamp, node identity, состав, checksum, verification и ограничения восстановления. VPS schema-3 backup сохраняет source drift, metadata и offline restore gates. Это архив конфигурации, а не диск/VM image.

Для RouterOS нужны fresh text export и, при доступных правах, штатный binary backup. Нахимова и Орехово имеют одинаковый LAN IP; идентичность проверяется по hostname/model/site и scoped trust store. Нахимова имеет описанный маршрут через TimeWeb/wg-home, Орехово требует отдельной проверки текущей достижимости. Недоступный узел отмечается `BLOCKED`, не заменяется старой копией и не считается заархивированным.

Хостовые snapshots становятся источником applied конфигурации на дату переноса. Public templates и code сравниваются с ними; прежний stage config не принимается за современный deploy master. Архивы и точные runtime identities остаются приватными.

## Ссылки, переносимость и runtime

1. Составить старое имя → новое место для каждого документа и активного исходника. В целевых копиях преобразовать Obsidian wiki-links/embeds и absolute local links в относительные Markdown links.
2. Сохранять anchors и image relationships; проверить file existence и fragment targets. Внешние HTTP references остаются внешними; server paths `/opt/...` в командах сохраняют операционный смысл.
3. Repo root определяется из расположения scripts; приватное хранилище — `.local/` относительно root. Убрать `Users/sergey`, Dropbox и фиксированный venv из локальных путей исполнения. Рендерируемый LaunchAgent получает реальные пути только при локальной установке.
4. Inventory является одним machine source; tunnel Markdown и Grafana/exporter inventory синхронизируются через проверяемый генератор/adapter. Сохраняются device identity, overrides и current-vs-active семантика.
5. Обновить `timeweb-vpn` symlink и два Mac LaunchAgent после проверки новых копий. Compose mounts/config/provisioning переключить на новое место. Snapshot live DB выполнять при корректно приостановленной записи; сначала резервная точка.
6. Server runtime paths сами по себе не меняются при переносе репозитория. Новую публикацию recovery policy выполнять только при изменении покрываемых конфигураций/controllers и после штатных gates.

Generated HTML, dashboards и изображения QA обновляются из исходных генераторов. После замены path root проверить, что generators не продолжают писать в Dropbox и deployment scripts читают новые private inputs.

## Последовательность работ

1. **Выполнено:** inventory, поиск credential candidates, duplicate/path audit, целевая схема и draft file map.
2. **Согласование:** структура, приватная `.local/` и правило current-only. Это предусмотренная пользователем точка согласования перед копированием.
3. Зафиксировать согласованный inventory и hashes. Разрешить review-строки; проверить связанные изображения, synthetic fixtures, retired dependencies и действительность private material.
4. Создать bootstrap/secret readers, checks и backup destinations в целевой копии. Адаптировать backup completeness к фактическому inventory; тестировать до live backup.
5. Снять fresh архивы узлов последовательно; собрать current secrets и profiles, сохранить provenance.
6. Скопировать code/docs/assets, переработать indices и ссылки, актуализировать registry без переписывания исторических результатов.
7. Запустить tests, link/secret/inventory checks и local setup из новой папки. Проверить console, exporter, Prometheus и Grafana до переключения runtime.
8. Переключить launcher, LaunchAgent и Compose mounts; получить свежие server probe cycles, проверить все devices в мониторинге и отсутствие обращений к старому root.
9. Итоговая карта `copied/adapted/excluded/blocked`, checksums, подтверждение Git exclusion и восстановление локального пакета в отдельном каталоге. Передать пользователю конкретный список старых каталогов, готовых к его удалению.

## Критерии завершения

- Каждый перенесённый файл имеет mapping и source hash; новые generated artifacts имеют свои manifests.
- Все current profile filenames и ключи сохранены, registry содержит фактический состав; статус клиента не выводится из одного наличия файла.
- Публичное дерево и staged diff не содержат действующих secrets, old private snapshots, DB или archives.
- В документах нет local absolute hyperlinks и unresolved file links; допустимые `.local/` destinations перечислены отдельно.
- SSH setup, console launcher и probes используют новый root; local monitoring сохраняет историю и выдаёт свежие samples.
- Fresh VPS/router archives проверены или конкретный узел отмечен BLOCKED; старый архив не подставляется для формального PASS.
- Источники остаются неизменны до пользовательского удаления. Удаление peer, ротация identity и массовый replay старого deployment в эту миграцию не входят.

Для начала копирования достаточно согласовать предложенную структуру и локальное размещение секретов. Оставшиеся технические решения агент выполняет по этому плану.
