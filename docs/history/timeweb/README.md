---
type: archive-index
topic: mikrotik
system: timeweb
status: active
created: 2026-06-28
tags:
  - mikrotik
  - vpn
  - archive
  - timeweb
---

## Назначение

Папка хранит sanitized archive summaries и task checkpoints по TimeWeb. Это
история работ и проверок, а не место для полных backup-файлов.

Полные/evidence файлы вынесены в Dropbox:

`.local/backups/timeweb`

## Снимки

- 2026-06-28T1726Z live audit (source reference not migrated) - read-only аудит текущего состояния TimeWeb.
- 2026-06-28T1836Z post-update check (source reference not migrated) - проверка после `apt upgrade` и reboot.
- 2026-06-29T0649Z pre-selector baseline (source reference not migrated) - checkpoint перед внедрением TimeWeb selector.
- 2026-06-29T0701Z TimeWeb selector implementation (source reference not migrated) - post-implementation checkpoint после настройки `wg-clients` и `wg-up-cenuta`.
- 2026-06-29T0734Z client creation wrapper (source reference not migrated) - checkpoint после добавления единой команды `add-client <client-name> fornex|cenuta|bth`.
- 2026-06-29T1453Z add-client wrapper fix (source reference not migrated) - checkpoint после исправления wrapper и создания `sergey-iphone-12` через Cenuta.
- 2026-06-29T1505Z client config viewer (source reference not migrated) - checkpoint после добавления команды `sudo wg-client-config` для вывода config и QR-code.
- 2026-06-29T1520Z selector allowedips viewer fix (source reference not migrated) - checkpoint после исправления selector `AllowedIPs`, расширения viewer на `selector/legacy/bth` и ротации `sergey-iphone-12`.
- 2026-06-29T1550Z client maintenance menu (source reference not migrated) - checkpoint после добавления меню `view/delete/regenerate` и smoke-test на временных `selector/legacy/bth` clients.
- 2026-07-09T1332Z softreload sessions (source reference not migrated) - checkpoint после перевода `wg-status` на named `sessions` и мягкого применения selector client changes через `wg syncconf`.
- 2026-07-09T1343Z Sveta MacBook M3 (source reference not migrated) - checkpoint после создания двух новых selector profiles `cenuta-domru` и `fornex-domru` для нового устройства.
- 2026-07-09T1356Z delete Sveta MacBook M2 (source reference not migrated) - checkpoint после удаления неиспользуемого legacy profile `sveta-macbook-m2-cenuta-domru.conf`.
- 2026-07-09T1403Z Sveta iPhone 16 Fornex+RU (source reference not migrated) - checkpoint после создания selector profile `sveta-iphone-16-fornex-domru.conf` и удаления старого legacy profile `sveta-iphone-16-fornex.conf`.
- 2026-07-09T1451Z Sveta iPad 9.7 selector pair (source reference not migrated) - checkpoint после создания новых selector profiles `cenuta-domru` и `fornex-domru`, удаления старого legacy profile и исправления пустого legacy RU-via-BTH state.
- 2026-07-09T1459Z Mac Mini M4 selector pair (source reference not migrated) - checkpoint после создания новых selector profiles `cenuta-domru` и `fornex-domru` для `Mac Mini M4`.
- 2026-07-09T1506Z Win Orekhovo selector pair (source reference not migrated) - checkpoint после создания новых selector profiles `cenuta-domru` и `fornex-domru` для `Win Orekhovo`.
- 2026-07-09T1510Z Engel Samsung Pad Cenuta+RU (source reference not migrated) - checkpoint после создания selector profile `cenuta-domru` для `Engel Samsung Pad`.
- 2026-07-10T0546Z Sergey iPad 9.7 selector pair (source reference not migrated) - checkpoint после создания новых selector profiles `cenuta-domru` и `fornex-domru` для `Sergey iPad 9.7`.
- 2026-09-17T1323Z Apple TV Fethiye и MacBook BTH (source reference not migrated) - подтвержденная переатрибуция действующего BTH peer и выдача отдельного peer MacBook.
- 2026-09-25T0559Z Mac Mini FLEX (source reference not migrated) - отдельные identity и peer, маршрут FLEX на третье устройство; импорт ожидается.

## Правило секретов

Полные private keys, preshared keys, QR-коды и client configs в Obsidian не
сохранять. Если понадобится полный секретный backup, хранить его в Dropbox
`System` или отдельном зашифрованном контуре.
