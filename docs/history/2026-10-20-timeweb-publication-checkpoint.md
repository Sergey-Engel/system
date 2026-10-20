# TimeWeb: документация, свежие копии и публикация

Дата: 20 октября 2026. Scope: фиксация завершённого обслуживания и
независимого SSTP, без нового изменения маршрутов, ключей или служб.
Исходный Git baseline: 59642ee1215bda0b3cd14c11a7073a31e78a651a.

## Что Зафиксировано

- [Протокол обслуживания](2026-10-20-timeweb-maintenance-sstp-newip.md):
  25 package upgrades, Docker29.9.1/containerd2.4.2, swap2GiB,
  kernel6.8.0-147-generic, два согласованных reboot и штатный recovery.
- [Паспорт](../hosts/timeweb/TimeWeb_Parameters.md) и
  [конфигурация](../hosts/timeweb/TimeWeb_Configuration.md): Lucky Bridge,
  provider ID6275803, оба IPv4, новый SSTP endpoint, изоляция и ограничения.
  Старые счётчики/PID и неуспешный сентябрьский export явно помечены
  историческими; они не подменяют результаты проверки 20 октября.
- [Исходники SSTP1.1.1 и runbook](../../services/transport/sstp-timeweb/README.md),
  [inventory](../../config/inventory/sstp-timeweb.json), оба плана,
  configuration/tunnel registry, Quick Guide и обзор архитектуры.
- Backup collector/verifier теперь проверяет новые SSTP files/manifest,
  binary/libs/units, netplan overlay и fstab, с регрессионными тестами.

Новый SSTP: **91.222.238.208:443/TCP**, PPP10.60.65.1/10.60.65.2,
MTU1400, namespace sstp-timeweb. Старый Xray94.241.171.65:443 и WireGuard
сохранены. Direct SSTP между Нахимова и Фетхие не перенастраивался.
Production routing, LAN transit и автоматическое переключение через новый
канал не включены. Имена end-device profiles, их SHA256 и состав67/22
остались прежними; отдельный transport не выдан как новый клиентский профиль.

## Повторная Live-Проверка

20 октября, **17:59:41 UTC / 20:59:41 по Фетхие**:

- hostname6275803-hh441050, kernel6.8.0-147-generic;
  reboot-required отсутствует, dpkg audit пуст, failed units нет;
- оба IPv4 находятся на eth0, swap присутствует;
- Xray active; read-only runtime recovery check завершился с rc0;
- SSTP ready, собственные persistent hashes/units/PPP/MTU валидны;
- исходные container ID и image совпадают; boot ID тот же, что после
  контрольной перезагрузки при обслуживании. Нового reboot не было;
- нагрузка 8.78 / 8.08 / 6.95 остаётся отдельным CPU-риском,
  не скрывается успешным статусом транспорта.

Private read-only evidence:
`.local/backups/timeweb-maintenance/20261020T175924Z-publication/`.
Первый вспомогательный read-only сбор остановился на неподдерживаемом
swapon --json; ошибка сохранена отдельно, повтор использует /proc/swaps.
Службы для устранения этой ошибки не менялись.

Это повторная проверка состояния, не новый длительный soak.
Строгий soak904.9s/26samples, негативные TLS/PPP тесты, reconnect,
двусторонние DF1400 и SFTP512KiB остаются доказательствами этапа приёмки
в основном протоколе. Они не заменяют клиентскую проверку пользовательских
маршрутов, которые на новом канале намеренно не включены.

## Свежие Резервные Копии

| Копия | Состав и проверка | SHA256 |
| --- | --- | --- |
| `.local/backups/timeweb/2026-10-20T175723Z_current-config/backup.tar.gz` | VERIFIED, 437 host files, 112 обязательных файлов инертно восстановлены; integrity/metadata/source-before-after/runtime проверки пройдены | e1dc0606f57e2616a6bbb4e16599e9c03a0d88ee03fa78ac13566374f10ffc37 |
| `.local/backups/nakhimova/20261020T175802Z/router.backup` | VERIFIED_TRANSFER, AES-SHA256 encrypted config backup, 1077841 байт; скачан дважды с одинаковыми байтами, пароль только в canonical store | 5eb9703b062d8566a59a635ce009d70e0e770beb4d07084b2a76d014cf86c9d5 |
| `.local/backups/nakhimova/20261020T175802Z/router-export.rsc` | Свежий sensitive export, 842262 байт, serial HKM0BDXYG74, hAP ax3 | 1ab9022d77000a83ad59236e12fcbc9a5fdce9019356f3dab3fe7eb95d034908 |
| `.local/backups/local/2026-10-20T180250632391Z_current-config/current-config.tar.gz` | VERIFIED, 984 инертно восстановленных файла, 67 профилей, 204889452 байта; source hashes before/after совпали, свежий read-only export Нахимова включён | a5bb8b21e0e2da7fdff87c46e1d22e08cd3c5098b5990760cd59c1e6c31f6cb8 |

Локальный переносимый набор сохраняется отдельно в `.local/backups/local/`:
исходники/документы, все 67 профилей, приватные masters/PKI/SSH и
canonical store с password records. Точные timestamp/hash, состав,
инертное восстановление файлов и свежий read-only RouterOS export записаны
в verification.json соответствующего набора. Нельзя помещать этот local
archive обратно в его собственный canonical store: это рекурсивная копия.
Набор снят до добавления его собственной квитанции в этот публичный
checkpoint; точные версии документов привязаны к inventory архива.

Полные config backups и их пароли не публикуются. Архивы VPS/локального
набора не являются образами диска, Docker images или копиями живой БД
мониторинга. VERIFIED_TRANSFER не является live restore, а offline file
restore не является disaster-recovery drill. Старые failed evidence
сохранены, не переименованы в успешные результаты.

Новый TimeWeb архив также побайтно сопоставлен с предыдущей принятой копией:
**92 защищённых файла** прежнего VPN и нового SSTP совпали.
После включения свежих копий canonical store прошёл verify-only:
**3335 files / 361 records**. Local archive сохраняет этот store,
но сам не записывается в него.

## Gates Публикации

Полный локальный suite: **633 passed**, 27.51 s. Repository validator:
**PASSED**, 491 public files, 67 profiles, 22 devices, problems=[];
private store и git diff --check прошли. Перед commit повторно проверяется
staged diff. Browser regression tests используют существующий
bundled Playwright через NODE_PATH, без установки новых зависимостей.
Первый запуск без NODE_PATH дал три MODULE_NOT_FOUND, это ошибка среды,
не live-сбой панели; исправленный повтор прошёл полностью.
Рабочая конфигурация не менялась ради тестов.

В Git включаются только публичные исходники, тесты, планы, паспорта,
реестры и журналы. `.local`, profiles, sensitive exports, PKI, private keys,
backup archives, execution logs и canonical store остаются исключены.
При push сверяются branch main, origin/main и точный remote HEAD;
публикация не является новым deployment сервера.

## Открытые Ограничения

CPU control plane остаётся высоким. Короткая приёмка не доказывает отсутствие
многодневной утечки памяти. Если внешний IP Нахимова изменится, фиксированный
source allowlist нового SSTP потребует отдельного reviewed обновления.
Автоматический failover и выбор нового транспорта для пользовательского
трафика требуют отдельного changeset, не входят в этот checkpoint.
