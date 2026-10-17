---
type: checkpoint
status: prepared-not-deployed
created: 2026-10-16
updated: 2026-10-16
---

# Подготовка Удаленного Выхода MacBook

Шаг 8 [плана](../tasks/PLAN-fethiye-site-to-site.md),
[точный changeset](../architecture/Site_to_Site_Egress_Changeset.md).
Пользователь подтвердил выключенные VPN-приложения на MacBook Air Sergey.
Текущий dynamic bound lease `.89.197` и MAC текущего SSID сверены непосредственно
на Фетхие. Это не идентификация по старому inventory Deco.

## Результат Подготовки

Подготовлен чистый builder с fail-closed gates и отдельным IPIP внутри WG.
На TimeWeb проверен изолированный nft dry-run в отдельном network namespace:
план меняет только два собственных файла guard/manifest, не WG keys/routes.
В live network namespace эти изменения не применялись. IPIP на роутерах
не создан, lease не закреплен статически, Remote не включен.

Полный набор тестов: 350 PASS, из них 29 целевых egress tests.
Проверки массива RouterOS ID и раздельных IPv6 input/forward anchors сначала
воспроизведены как RED, затем прошли GREEN. Это тесты builder/preflight,
не доказательство работы еще не развернутого Internet-выхода.

Подготовка: `.local/backups/site-to-site/20261016T134255Z-egress-local/`.
Полные payloads и предыдущие read-only попытки хранятся только в private store.
Повторная проверка 13:46:42 UTC / 16:46:42 Europe/Istanbul: router exports,
host WG/guard и все 67 профилей неизменны; отдельные runtime/BTH/monitoring
contracts PASS. Private store VERIFIED: 819 files / 297 records.
Repository validation PASS: 409 public files, 67 profiles, 22 devices.
Неизмененные contracts не переподписываются; profile catalog и observations
не меняются ради еще не примененного changeset.

## Свежие Копии До Изменений

- TimeWeb `2026-10-16T131534Z_current-config`: VERIFIED, 386 host files,
  61 offline restore checks, SHA-256
  `c7001394dbb0c033de32a614d3c2af309a02454ddaede5af6b4cd50d11cd2dfc`.
- Fornex `2026-10-16T131652Z_current-config`: VERIFIED.
- Cenuta `2026-10-16T131729Z_current-config`: VERIFIED.
- Фетхие `20261016T132557Z-pre-egress`: VERIFIED_TRANSFER, двойное скачивание,
  конфигурация до/после сбора совпала.
- Нахимова `20261016T132738Z`: VERIFIED_TRANSFER, encrypted binary backup
  и sensitive export. Export SHA-256
  `15c58219585f61844e9c844c94e7e9af92e6983202b099529dd695589ea66608`.

VERIFIED_TRANSFER не означает restore на реальном роутере. Полные конфигурации,
пароль binary backup и ключи не включены в публичную документацию.

## Следующее Действие

Ожидается запрошенный внешний IP на MacBook через Wi-Fi MikroTik,
до переключения. После получения повторить актуальные gates и применить
изолированный transport сначала в Local. Затем отдельное переключение только
MacBook, проверка внешнего IP/DNS/HTTPS/приложения и объявленный fail-closed test.
Обратный выход, автоматическое восстановление и reboot/restore остаются
последующими непринятыми этапами. Сеть Deco остается без изменений.
