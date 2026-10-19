# PLAN: Автоматическое Распознавание Имен По MAC

Статус: Done. Дата: 2026-10-19.

| Шаг | Статус |
| --- | --- |
| Источники и границы идентификации | Done |
| RED и структурированный LAN inventory | Done: 14 exact bindings |
| Resolver и локальный IEEE cache | Done: 58 795 prefixes, 2 ambiguous |
| Подписи панели и автоматические проверки | Done: 554 passed, browser/HTTP |
| Local deploy, проверка актуального выбора | Done: Local по последующему выбору пользователя |

Пользователь сначала подтвердил Internet через Нахимова для MacBookAir192.168.89.197.
В процессе обнаружен уже существовавший pending Remove, generation9 до правок
имен. Пользователь уточнил требуемый режим: обычный выход Фетхие. Подтвержден
успешный Remove generation11, selected=false/pending=false. Имена сами не
меняют выбор/роутеры. MAC52:EB:3F:26:E9:5A пока не сопоставлен.
Полный подтвержденный MAC дает имя из нашего реестра; DHCP hostname остается
отдельным источником. IEEE MA-L/MA-M/MA-S/IAB дает только производителя,
не владельца/модель. Для locally administered MAC OUI lookup запрещен.

Новый JSON LAN inventory основан на таблице паспорта Фетхие и принятом
MikroTik MAC тестового MacBook; старые VPN inventory/profile counts не менять.
Нельзя объединять устройства по IP, hostname, производителю или другому SSID.
Разрешен только точный full-MAC match. Ошибки базы имен не блокируют транспорт.

Runtime lookup только локальный: нет сетевых запросов в status/Add, MAC не
передаются сторонним сервисам. Для vendor cache скачать публичные IEEE CSV
с HTTPS verification, ограничениями времени/объема и атомарной заменой.
Это восстанавливаемый cache, не credential store. Обновление snapshot отдельно,
без новой периодической автоматизации. Подписи не меняют selection revision.

Тесты: exact/private/unknown/vendor/longest prefix/дубликаты/ошибка cache,
сохранение старого cache при ошибке загрузки, status label без изменения
MAC/IP/revision. Проверить браузер desktop/mobile, полный suite, local HTTP,
неизменность config/state и Remote. Restart только local facade.

Pre-edit snapshot: `.local/backups/site-to-site/20261019T113109Z-device-names/`.

Результат: [протокол](../history/2026-10-19-sstp-device-names.md).
