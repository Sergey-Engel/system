# RU Bypass Во Всех Режимах Панели

21 октября2026. Запрос пользователя: все тоннели в Device routing должны
направлять российские IP в местного провайдера, с именами-RU. Scope - режимы
этой панели на обоих роутерах, не массовое изменение67 выданных профилей.
Device routing4.1.0, Direct controller3.1.0, RU policy1.0.0.

## Результат

WG-Cenuta-RU/WG-Fornex-RU сохранены, добавлены названия SSTP-Cenuta-RU,
SSTP-Fornex-RU, Direct SSTP-RU via Fethiye/Nakhimova.
Российский IPv4 идёт через провайдера исходной площадки, не удалённой.
Имена не меняют mode IDs. Все начальные назначения и prepared/selected
состояния сохранены, включая Direct192.168.88.28.

Исходный RU_Networks Нахимова не очищался/не заменялся. Его CIDR и start-end
диапазоны нормализованы без изменения покрытия:8588 CIDR, digest
7fbeb615837054bfaa66bc1aed809f8752e908eb514c6a86ffaab96aa4c2c770.
Точное эквивалентное покрытие добавлено Фетхие в ранее отсутствовавший список.
Это снимок существующей политики, не гарантия геолокации/свежести всех IP.
Автоматического обновления/переключения не добавлено.

RU bypass для четырёх native lists теперь выше legacy force195.133.216.210,
который также входит в RU. Direct перестал повторно захватывать RU catch-all
source rule: non-RU получает mangle mark, прежнее source rule сужено до DNS
target1.1.1.1. RU/private accept, scoped WAN accepts/replies до leak guard и
исключение RU DNS из redirect описаны в [runbook](../operations/Panel_RU_Direct.md).
IPv6 country classification не добавлена; старые Direct IPv6 guards сохранены.

## Проверки

Финальный повтор: 682 tests passed, 37.32s: controller/API/browser regression плюс CIDR/range,
оба направления RU Direct и Apply/Remove. Полная ROS конфигурация и порядок
новых правил проверены строгим контроллером; неизвестный drift не принят.

Шесть изолированных router-mode проб: пять режимов Нахимова и Direct Фетхие.
Источник10.60.67.250/32 и временная таблица не совпадают с LAN клиентами;
действующие mangle selectors скопированы без MAC/ingress-привязки в output,
с тем же RU set и отдельной таблицей. Это не end-client browser acceptance.
Выход измерен в postrouting после output routing adjustment, до SNAT.

Для каждого режима: российский77.88.8.8 -3/3 через ether1; зарубежный1.1.1.1 -3/3
через соответствующий WG/SSTP интерфейс. Expected counters >0, wrong counters0.
После отключения только временного tunnel default: RU3/3, non-RU0/3.
Рабочие интерфейсы/маршруты пользователей не выключались. Временные объекты
удалены, итоговые exports/строгие проверки обоих роутеров совпали с установленной
RU policy. Это проверка изолированной потери маршрута, не полного WAN outage.

### Что Пока Не Проверено С Устройств

После установки новых RU-правил не проводилась клиентская приёмка ни одного
из шести тоннельных вариантов: реальный LAN/Wi-Fi ingress, MAC/IP selectors,
DNS redirect, HTTPS, браузер и приложения. Router-originated output пробы
не исполняют клиентский prerouting с MAC-привязкой. Строгая сверка этих правил
и автоматические tests проверяют конфигурацию, но не заменяют такой трафик.
Старое подтверждение MacBook через Direct относится к предыдущему этапу.
Нет проверки полного реального обрыва рабочего тоннеля, IPv6 country routing,
полного reboot новой политики или длительной нагрузки.

Финальное уточнение: на обоих роутерах non-RU Direct mark исключает
`dst-address-type=local`. Проверено точное отличие только этого selector,
исходные назначения и остальная конфигурация сохранены. Receipt:
`20261021T082007Z-local-destination/accepted.json` в evidence root ниже.

Два свежих collector cycles прошли для Cenuta/Fornex: fresh1, все probe_valid1,
timestamp вырос. BTH, monitoring и runtime checks0; console mount namespace
fleet3/3, HTTP/state200, Prometheus22 devices, Grafana databaseok.
В TimeWeb не менялись102 защищённых обязательных файла, включая SSTP bindings:
post archive сравнён с verified05:48 archive. Изменений server RPDB/guards/peers
нет, перепубликация recovery policy/baseline не требуется и не выполнялась.

## Неуспешные Проверки И Восстановление

Первый deployment остановлен до commit: сравнивались redacted after и
sensitive before. Защитный diff отказал; режим скрытия выровнен.
Safe Mode отменил изменения, но оставил5 новых dst-address-list match fields.
Установка empty selector не воспроизвела исходный export; только эти5 правил
восстановлены из pre-export в прежних позициях. Exact exports и старые strict
controllers повторно приняты на обоих роутерах. Первый прогон не выдан за успех.

Первый IP-пробник неверно проверял egress в output filter, до routing adjustment;
foreign probe был остановлен самим тестовым guard. По официальному packet flow
измерение перенесено в postrouting. Рабочие per-device правила не менялись
для устранения ошибки теста.

После всех успешных6 проб ROS7.19 на Фетхие оставил2 временных inactive route,
ссылающихся на уже удалённую временную table*405. Удалены только эти2 owned
routes после проверки полного diff; установленная RU policy совпала точно.
Нельзя считать выход из Safe Mode достаточным подтверждением очистки.

## Резервные Копии

Закрытый evidence root .local/backups/panel-ru/20261021T074538Z-discovery/.
Успешная установка20261021T080131Z-deployment, пробы20261021T080515Z-qualification,
monitor20261021T080739Z-monitor, итог20261021T081331Z-post.
Неуспешные receipts и точные восстановления сохранены отдельно, без секретов в Git.
Финальная сверка и backups после local-destination selector:
`20261021T083431Z-post/accepted.json`. Повтор мониторинга:
`20261021T083602Z-monitor/accepted.json`. Итоговый `completion.json`
подтверждает сохранённые назначения, шесть проб, границы клиентской проверки
и равенство102 защищённых файлов свежего TimeWeb archive с исходным состоянием.

| Копия | Приватный путь относительно .local/backups | Результат/SHA256 |
| --- | --- | --- |
| Нахимова pre | nakhimova/20261021T074735Z/router.backup | VERIFIED_TRANSFER; f37e416e30d5e6fb328ccdc8c4ddd50de17d127920633067b39cf1bec7cc8777 |
| Фетхие pre | panel-ru/20261021T074538Z-discovery/20261021T080131Z-deployment/fethiye-pre/router.backup | VERIFIED_TRANSFER; metadata в verification.json |
| TimeWeb final | timeweb/2026-10-21T083521Z_current-config/backup.tar.gz | VERIFIED;448 host files/122 temporary restores;ab4a73aba0cb75a358cd62116e36ba7cc5bc7027c845c110d61aa5e1c1789adc |
| Нахимова final | nakhimova/20261021T083451Z/router.backup | VERIFIED_TRANSFER;962ea9bd0676de8cdae8d6bd7f3563d7a610edee0a3bd930514169726a595f37 |
| Фетхие final | panel-ru/20261021T074538Z-discovery/20261021T083431Z-post/fethiye-pre/router.backup | VERIFIED_TRANSFER;77ffe0bc751a3b8f1f3f4882efd626a8f28b7549a1ffd1db00c438058f2f0e31 |
| Local checkpoint | local/2026-10-21T084008022941Z_current-config/current-config.tar.gz | VERIFIED;96098c5cec00f8077b08bdccbb3d39510148d36c2e62944284ee2ff07c1a8167 |

Названия fethiye-pre в post-каталоге - формат прежнего backup helper;
это свежая post-копия с отдельным password record. Binary backups зашифрованы,
переданы дважды и сверены; live restore drill и disk images не выполнялись.
Masters/config flag и metadata/receipts checkpointed в canonical store.
Полные архивы и дубли чувствительных export остаются только в private backups,
не дублируются рекурсивно в JSON. Финальный local configuration archive
находится в `.local/backups/local/`; точный run, SHA256, состав и результат
сверки находятся в его `verification.json`. Его проверка означает локальную
побайтовую распаковку в отдельный временный каталог, не полноценный machine
restore. Server archives не зашифрованы: доступ ограничен правами 700/600;
RouterOS binary backups отдельно зашифрованы.

Первый повтор tests в этой сессии: 678 passed, 3 failed, 1 skipped из-за
отсутствия Playwright в Node resolution. Повтор со штатным `NODE_PATH`
прошёл полностью: 682 passed. Первый live browser заход превысил 30s;
отдельные HTTP-пробы вернули 200. В test harness установлен timeout90s,
соответствующий существующему backend deadline; production deadline не менялся.
Повтор live browser завершён успешно: оба сайта, desktop/mobile, все названия
с -RU, без POST, JavaScript errors и горизонтального переполнения.
Приватный checkpoint синхронизирован после обновления browser receipts;
проверка до checkpoint обнаружила ожидаемое отличие materialized файла и
canonical record. После синхронизации store VERIFIED:3677 файлов/370 records.

Local checkpoint содержит1016 исходных файлов и свежий read-only export
Нахимова (08:40:17 UTC); всего1017 файлов восстановлены в отдельный временный
каталог и побайтово сверены. 67 профилей сохранены без изменений. Размер
архива207188877 bytes. После внесения этой записи выполняется отдельный
финальный снимок документации; его metadata остаются в private verification.json,
без рекурсивного включения архивов в canonical store.
Финальная проверка repository: PASSED,508 public files,67 profiles,22 devices,
problems=[]; diff whitespace check прошёл. Коммит и push этим запросом не выполнялись.
