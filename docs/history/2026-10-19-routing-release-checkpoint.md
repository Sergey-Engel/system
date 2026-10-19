# Сохранение Изменений: SSTP И Маршруты Устройств

Дата: 19 октября 2026. Исходный Git HEAD: `e5c50cb` (`Bridge to Fethiye - 1`).
Текущий release controller/UI: **3.0.0**. Рабочий проект — этот checkout
`system`, не прежний Obsidian-каталог. Поручение: документировать накопленные
изменения, сделать свежие копии обоих роутеров, commit и push.

## Состав Изменений

| Область | Результат И Источник |
| --- | --- |
| TimeWeb site-to-site | Прежний рабочий WG/IPIP сохранён. Ограниченный тест отказа и возврата в Local зафиксирован в [протоколе](2026-10-17-egress-fail-closed.md). Новых изменений TimeWeb при этом checkpoint нет. |
| Direct WireGuard | Проброс Deco проверен, нестабильность прямого UDP/WG исследована, временные объекты удалены. Причина на уровне конкретного DPI/NAT middlebox не установлена. [Диагностика](2026-10-18-direct-path-diagnosis.md). |
| SSTP/TCP443 | Проверены TLS, отрицательный CA, reconnect и длительное окно; затем установлен постоянный mutual-TLS канал с отдельной PKI/PPP. [Soak](2026-10-19-sstp-direct-soak.md), [постоянная установка](2026-10-19-sstp-direct-permanent.md). |
| Выход в обе стороны | Forward через Нахимова и reverse через Фетхие используют тот же SSTP. Lookup-only tables, scoped NAT/DNS/MAC/IPv6 guards, без автоматического fallback. [Reverse и границы приёмки](2026-10-19-sstp-reverse-egress.md). |
| Local console | Facade19118 и отдельный SSH-forward19119; VPN-раздел прежний. Улучшены проверки управления, Add/Remove, recovery, sticky errors; серверная панель не развёртывалась заново. [Эксплуатация](../operations/Direct_SSTP.md). |
| Unified device routing3.0 | Нахимова: только enabled permanent DHCP reservations, включая offline; Standard/Cenuta/Fornex/Direct. Фетхие: только actual authorized Wi-Fi registrations; Standard/Direct. Exact-MAC справочник, IP, явная Apply, взаимное исключение режимов, shared lock, durable intent/readback. [Полный протокол](2026-10-19-unified-device-routing.md). |
| Каталоги | Отдельный SSTP infrastructure inventory и LAN name dictionary. Состав обычных VPN-профилей67 и наблюдаемых устройств22 не изменён. |
| Неактивный candidate | В исходниках сохранены прежний server-side S2S UI/controller и связанное покрытие backup/sandbox. Это не действующая конфигурация TimeWeb и не инструкция её применять. [Статус candidate](../operations/Site_to_Site_Console.md). |

Код и тесты находятся в `services/transport/site-to-site/`; локальный launcher
включает facade, если её private config установлен. Исторический server-side
candidate, изменения console unit/tmpfiles и условное backup coverage
сохраняются как исходники, **не применяются** этим commit/push.

## Свежие Резервные Копии

Private recovery bundle:
`.local/backups/site-to-site/20261019T183237Z-documentation-checkpoint/`.

Для каждой площадки сохраняются:

- Зашифрованный AES-SHA256 RouterOS binary `fethiye-pre/router.backup` /
  `nakhimova-pre/router.backup`. Два независимых чтения по SFTP и SHA-256.
- Полный sensitive export: `fethiye-config.rsc`, `nakhimova-config.rsc`,
  а также копия рядом с каждым binary backup. Конфигурация сверяется до/после
  создания backup и с текущим private master.
- Serial, фактическая RouterOS version, board, certificate metadata,
  строгий routing view, verification report и общий manifest с размерами/SHA.
- Frozen `recovery/sstp-direct/`: config, forward/reverse state, unified
  intent, журнал, LaunchAgents, PKI и credentials. Существующие SSH identities,
  trust и config скопированы в `recovery/ssh/`, новые ключи не генерируются.

CA private key и оба PKCS12 декодируются существующим паролем, проверяются
соответствие ключа сертификату, подпись CA, metadata и live certificate
fingerprints обоих роутеров. Пароль binary backup находится только в
canonical `.local/secrets.json`, в записи `backup:<site>:direct:<timestamp>`.
Frozen files тоже включены в canonical store; права dirs700/files600.
Это private material, не содержимое Git-коммита.

Первый сбор `20261019T183125Z-documentation-checkpoint` остановился до создания
binary backups: `print as-value` не выдал certificate fingerprints. Явный
`get <id> fingerprint` вернул ожидаемые SHA256; сертификаты не заменялись.
Новый сбор выполняется в отдельном каталоге, старые копии не перезаписываются.

Ограничение: `.backup` — бинарная копия **конфигурации RouterOS**, не побитовый
образ flash, не установочный NPK и не доказанное восстановление железа.
Сохраняются реальные версии каждой площадки; restore требует отдельного окна,
проверки того же устройства/версии и может перезагрузить роутер. Raw disk image,
reboot и restore drill не выполнялись. Это соответствует разделению backup
и export/import в [документации MikroTik](https://manual.mikrotik.com/docs/getting-started/configuration-management/backup/).

## Восстановление И Публикация

1. Получить публичный Git checkout и canonical private store по доверенному
   каналу; не через публичный GitHub. Проверить целостность и права файлов.
2. По `manifest.json` выбрать точный serial/RouterOS version и способ recovery.
   Не импортировать backup другого роутера и не подменять всё состояние ради UI.
3. RouterOS restore выполнять только отдельной согласованной операцией.
   PKI/SSH и local config/state восстанавливать согласованным набором;
   не терять актуальные пользовательские назначения при более старом snapshot.
4. После reviewed restore проверить строгие identities, маршруты, guards,
   реальные клиентские HTTPS/DNS и TimeWeb/BTH/monitoring отдельно.
5. В Git входят исходники, тесты, безопасные inventory, runbooks, планы и
   датированная история. `.local`, binary backups, полный export, PKI и пароли
   в staging не допускаются. Push не развёртывает серверы или роутеры.

Общая процедура: [хранение и перенос](../operations/storage-and-transfer.md).

## Проверки

Повторный полный тестовый прогон перед публикацией: **610 passed**.
UI desktop/mobile и переходы между режимами уже проверены в протоколе release3.0;
реальные клиенты ради checkpoint не переключаются. Readiness конфигурации не
означает новую пользовательскую приёмку всех маршрутов. Нахимова reverse
проверялся с роутера, не с физического клиентского устройства.

Fresh backup завершён: обе площадки `VERIFIED_TRANSFER`, 37 файлов плюс
manifest сохранены в canonical store. Live/current export совпали;
controller config/state и защищаемый TimeWeb snapshot за время сбора не
изменились. PKI декодирована и сопоставлена с live SHA256.

| Площадка | Serial | RouterOS | SHA256 Binary Backup |
| --- | --- | --- | --- |
| Фетхие | HM20B6QXS8H | 7.19.6 stable | `304293f063b87ba7b8d24301f31f1b09892a3bab9d7e38d18479baf27e806f91` |
| Нахимова | HKM0BDXYG74 | 7.24.4 stable | `922def082ed8d42e255d70926c33e9453732f923055ca3e336d7c851aa614ada` |

Repository validation PASS:476 public files,67 profiles,22 devices, без
проблем. Private-store verification PASS; sensitive files не включаются в
Git. Для read-only backup/documentation topology gate не перепубликуется:
маршруты, службы, peer identities и ранее проверенные transport policies не
менялись. Финальный `git diff --cached --check` и staging allowlist проверяются
до commit. Точный SHA публикации определяется
Git-коммитом, содержащим этот документ, и проверенным remote ref `origin/main`.
