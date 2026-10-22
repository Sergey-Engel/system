# Список Устройств: Диагностика И Публикация

22 октября 2026. Локальная панель device routing4.1.1; IP-политика RU4.1.0
и Direct controller3.1.0 не меняются. Запрос пользователя: исправить загрузку
списка и опубликовать завершённые изменения без секретов/backups.

## Причина И Граница Вывода

Скриншот показывает отказ HTTP/ожидания статуса, не отсутствие DHCP reservations.
Read-only запрос `/routing-state/nakhimova` вернул HTTP200,7 устройств,
source_ready=true и все routes ready за90.9s. Отдельный capture с замерами
занял30.06s: pinned SSH Нахимова, source/peer Direct-проверки, повторные
exports/leases и SSTP proof; список и строгий baseline валидны.
Параллельные запросы раньше последовательно выполняли полный capture под
одним mutex и общим controller flock. Ожидание в очереди суммировалось с
длительностью capture; frontend прекращает чтение через120s. Конкретный
скриншот не содержит точного backend traceback: неизвестный сетевой отказ
в момент снимка не исключён. Наличие и валидность устройств подтверждены сейчас.

## Исправление

Только локальная facade: для каждого сайта запрос запоминает время поступления
до mutex. Ожидающий запрос может использовать результат проверки этого же
сайта, завершённой после его поступления. Это объединение текущей работы,
не TTL-cache: каждый новый Refresh после завершения запускает свежую проверку.
Сайты разделены. POST никогда не использует такой read result и очищает cache;
revision/readback/rollback/CSRF проверки сохранены. Отправка HTTP вынесена из
mutex, медленный/закрытый клиент больше не держит его при отправке.

При первом неудачном чтении UI показывает Check failed вместо оставшегося
Checking. При повторном отказе ранее полученные строки остаются видимыми,
но изменение маршрутов блокируется. Автоматические refresh/failover не добавлены.

## Проверки И Публикация

Регрессионный concurrent HTTP test сначала воспроизвёл отказ старой реализации.
Он проверяет объединение ожидающих reads, свежесть следующего чтения,
изоляцию сайтов и отдельную POST-проверку. Browser regression проверяет
ошибку первого чтения и сохранение строк при последующем отказе.
Полный suite:683 passed,106.29s. Живые одновременные GET Нахимова завершились
за80.19s каждый и вернули один checked_at,7 устройств и все routes ready.
Фетхие:53.44s,1 Wi-Fi устройство, оба routes ready. Следующий отдельный
Refresh Нахимова:82.40s, новый checked_at,7 устройств, все routes ready.
Хеши routing-state.json и обоих Direct state.json остались прежними; POST
не отправлялся. Только локальная facade перезапущена, SSH-forward/VPN службы
и router configurations не менялись. Остаточное ограничение: сетевой capture
всё ещё может занимать десятки секунд; объединение reads не устраняет потери
связи или нагрузку на TimeWeb. Новых гарантий мгновенной загрузки нет.

В текущей пользовательской вкладке выполнен Refresh:7 строк отображаются,
ошибка исчезла, назначения сохранены. Private evidence:
`.local/backups/panel-publication/20261022T061056Z/live-read.json`, screenshot
`.local/backups/panel-publication/panel-restored.png`. Приватные файлы не публикуются.
Реальная клиентская приёмка RU-политики
остаётся [не выполненной](2026-10-21-all-panel-routes-ru.md#что-пока-не-проверено-с-устройств).

## Backup И Git Audit

Локальный архив `.local/backups/local/2026-10-22T061623684340Z_current-config/`
получил VERIFIED:1018 исходных файлов,67 профилей плюс свежий read-only export
Нахимова в06:16:33 UTC;1019 файлов пробно восстановлены и сверены в отдельном
временном каталоге. Container identity/PID/namespace/start не менялись.
Это не disk image и не live restore. Canonical store VERIFIED:3682 files,
370 credential records. Изменена только локальная release metadata4.1.1;
настройки маршрутов/клиентские назначения не менялись.

Repository validator PASSED:510 public files,67 profiles,22 devices,problems=[].
44 staged файла проверены по точным bytes index: known private records,
PEM/WG private-key literals, приватные пути, backups, archive magic,
равенство index/worktree. Problems=[]. В tracked tree нет `.local`/`.venv`,
keys и backup artifacts; реальные paths secrets/SSH/backups проходят check-ignore.
Секреты, binary backups, полные RouterOS exports, private evidence и локальный
архив не включены в публикацию. Git whitespace check прошёл.

## Публикация

Основной коммит `a6d0c8f7d0138b4c303a655a9d64d1f1979de3c5` включает44
публичных файла: ручные SSTP-Cenuta/Fornex, IP-based RU bypass во всех режимах,
исправление очереди read-запросов, tests и документацию завершённых этапов.
Push в `origin/main` выполнен; отдельный `ls-remote` вернул тот же полный SHA.
Текущая запись о публикации сохраняется отдельным документационным коммитом.
Она не меняет deployed code, маршруты, ключи или клиентскую приёмку.
