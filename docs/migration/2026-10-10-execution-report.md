# Перенос MikroTik / VPN: 10 октября 2026

Структура согласована пользователем. Исходные документы, конфигурации и backups
не удалены. На этапе переноса commit/push не выполнялись; этот отчёт фиксирует
проверки до последующей публикации Git. Live VPN routing, identities и
серверные пользователи не менялись.

## Выполнено

- Рабочие материалы собраны в этом checkout: документация, шесть HTML-схем,
  транспорт, controllers, collectors, console, dashboards и правила агента.
- 65 профилей в 21 папке перенесены с исходными байтами и checksum.
- Канонические реестры: [profiles](../../config/inventory/clients.json) и
  [observations](../../config/inventory/observations.json); второй используется
  экспортёром и Grafana, без отдельной копии в service directory.
- Секреты собраны в один [.local/secrets.json](../../.local/secrets.json),
  исключённый из Git. Private factory-label image также только там и в private
  materialized copy. Все остальные изображения просмотрены перед публикацией.
- Старые configs/backups, лабораторные credentials/results и дублированные
  экспортированные скрипты исключены. 11 AWG client aliases сверены по
  параметрам с опубликованными profiles, второй комплект не перенесён.
- PKI: 10 файлов совпали со свежими applied snapshots; два CA private keys
  проверены как ключи действующих локальных issuer certificates.
- Перенесён runtime Grafana/Prometheus при остановленных контейнерах:
  1 135 файлов, 302 029 219 bytes, 0 различий до нового запуска. Проверка
  целостности базы Grafana — `ok`. Container/project names сохранены,
  image versions не обновлялись, закреплены digests прежних образов.
- Переставлены launcher, SSH include и три LaunchAgents. Прямой SSH из launchd
  не мог читать Documents из-за macOS privacy: установка создаёт производный
  private SSH cache вне Documents, с теми же ключами и trust stores.
- 12 previews схем заново отрисованы из перенесённых HTML; broken images — 0.

## Свежие Резервные Копии

| Узел | Результат | Каталог относительно корня |
| --- | --- | --- |
| TimeWeb | VERIFIED; 380 host files, 55 required restore files | `.local/backups/timeweb/2026-10-10T145803Z_current-config/` |
| Fornex | VERIFIED; 135 host files и конфигурации контейнеров | `.local/backups/fornex/2026-10-10T145910Z_current-config/` |
| Cenuta | VERIFIED после повторного сбора; 83 host files | `.local/backups/cenuta/2026-10-10T150156Z_current-config/` |
| Нахимова | VERIFIED_TRANSFER; fresh export и encrypted binary backup | `.local/backups/nakhimova/20261010T154232Z/` |
| Орехово | BLOCKED; timeout SSH из внешней сети | `.local/backups/orekhovo/20261010T150512Z/` |
| Локальное хранилище | VERIFIED; 777 source files + свежий RouterOS export, 778 files restored offline | `.local/backups/local/2026-10-10T154848547401Z_current-config/` |

Первый Cenuta сбор не прошёл проверку из-за timeout `unit-files`; он не
засчитан как verified, сохранён только как private failure evidence.
RouterOS backup downloaded twice с одинаковым checksum; реальное
восстановление на роутер не выполнялось. VPS archives проверены offline,
не являются проверенным восстановлением ОС/VM с reboot.

## Проверки

- Профили: точные SHA-256 всех 65 файлов, 21 устройство, без изменения ключей
  или адресов. Проверены cardinality observation inventory и отсутствие дубликатов.
- Полный набор актуальных unit tests: **265 passed**. Прежние лабораторные
  stage tests, требующие исключённых snapshots/vendor binaries, не выдаются
  за проверку текущей системы. Один промежуточный прогон дал cleanup PermissionError
  в существующем collector scheduler test; focused и полные повторы прошли.
- Приватный portable store: 388 файлов, 267 записей; восстановление из одного
  `secrets.json` в отдельный временный каталог проверяется побайтно и по правам.
- Проверены относительные Markdown/HTML links, heading anchors, Python/JSON/shell
  syntax, известные secret values и private-key markers в публичных файлах,
  включая XML внутри DOCX. Git dry-run не включает `.local` или `.venv`.
- 433 перенесённых/объединённых исходных файла повторно сверены с source hashes:
  исходные статические материалы не изменены. Runtime после нового запуска
  закономерно изменяется и не сравнивается с текущими байтами старой копии.
- Два свежих collector cycles: timestamps обоих uplink продвинулись, все три
  Prometheus targets UP, source/probe/FLEX observations fresh и valid.
- Console: UP / UP / READY, три устройства и три готовых FLEX-маршрута.
  Повторный запуск launcher переиспользует управляемый SSH, не создаёт дубль.
- Grafana health и database integrity — `ok`; в современной таблице `resource`
  присутствуют семь dashboards, включая TimeWeb pilot и device live.
- Current live runtime recovery `check` — PASSED. Policy не перепубликовывалась,
  неизвестный drift не подписывался.
- Локальный backup-инструмент учитывает имена systemd units с `\\x2d`; архив
  проверяется инертным восстановлением, без исполнения или слепой распаковки.
  Исправлена cleanup race уже завершённого дочернего процесса на macOS;
  ошибка при ещё работающем процессе не скрывается.
  Финальный local archive — VERIFIED, hashes до/после совпали; предыдущие
  FAILED/PARTIAL attempts сохранены как частные свидетельства, не как успех.

Итоговые результаты тестов, локального архива и static checks записаны в
[verification](2026-10-10-verification.json). Подробные runtime/private evidence
сохраняются только в `.local/evidence` и `.local/backups`.

## Ограничения

- Орехово: свежая копия не получена. Нет подтверждённого внешнего management
  route; `192.168.88.1` другой площадки не использовался как подмена. Кроме
  доступности, существующий `codex_audit` имеет read/ssh, не backup/sensitive.
- Legacy `maintenance_preflight.py --check` отказал на свежих локальных files:
  старый `hostguard` hash и Xray/hostguard baseline расходятся с applied
  snapshot. Контракт не обновлялся и drift автоматически не принимался.
  Этот gate отличается от current runtime recovery `check`.
- Импорт профилей и end-to-end тесты устройств не повторялись. Наличие файлов
  и готовность controllers не означают текущую активность устройства.

## Навигация И Откат

Вход: [README](../../README.md), [Quick Guide](../quick-start.md),
[хранение/перенос/откат](../operations/storage-and-transfer.md).
Исходная [карта классификации](2026-10-10-file-map.csv) сохранена;
[итоговая карта](2026-10-10-final-file-map.csv) содержит фактические target paths,
статус каждой операции и SHA-256. Generated canonical документы и helpers
описаны отдельно в README и verification.
Удаление исходных папок остаётся за пользователем, не выполнялось агентом.
