---
type: checkpoint
system: timeweb
status: complete
created: 2026-09-17
tags: [vpn, wireguard, bth, clients]
---

# Apple TV (Fethiye) и новый BTH для MacBook

## Изменение

- Пользователь подтвердил, что действующий BTH peer `10.30.30.3/32` принадлежит Apple TV (Fethiye).
- Его ключи и серверная идентичность сохранены; импорт на Apple TV не требуется.
- Профиль перенесен в `.local/clients/Other/apple-tv-fethiye/` и переименован по действующему правилу.
- Для MacBook Sergey выдан отдельный persistent WG BTH peer `10.30.30.6/32` и опубликован профиль `WG-TW-BTH-S-MacBook.conf`.

## Safety и проверка

- До изменения: verified backup TimeWeb/Fornex/Cenuta и check BTH recovery.
- Изменение применено без restart/recreate `wg-relay` через `bth_client_changeset.py`.
- Recovery-contract допускает только проверенные состояния перехода для `wg-home` и списка allowed IPs.
- После изменения: persistent и runtime peer `.6` совпали, `bth_recover.sh --check` валиден, `bth-recovery.timer` active.
- При финальной сверке исправлена только reference-копия `bth-recovery/wg.baseline`, оставшаяся от предыдущего поколения; перед заменой проверены final persistent config, contract, allowed IPs и recovery helper. Повторный strict preflight прошел полностью.
- Exporter после reload показывает активный `WG-TW-BTH` для Apple TV (Fethiye); MacBook peer ожидает импорта и handshake.
- После изменения: verified backups `timeweb/2026-09-17T132124Z_current-config`, `fornex/2026-09-17T132209Z_current-config`, `cenuta/2026-09-17T132238Z_current-config`.

Ключи, PSK, QR и содержимое клиентских конфигов здесь не сохраняются.
