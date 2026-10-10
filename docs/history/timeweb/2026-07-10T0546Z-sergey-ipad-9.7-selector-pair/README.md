# Sergey iPad 9.7 selector pair

## Scope

Созданы два новых selector-тоннеля для устройства `Sergey iPad 9.7`:

- `sergey-ipad-9.7-cenuta-domru.conf` - `10.50.50.36/32`, RU -> BTH/Home/Dom.ru, non-RU -> Cenuta.
- `sergey-ipad-9.7-fornex-domru.conf` - `10.50.50.37/32`, RU -> BTH/Home/Dom.ru, non-RU -> Fornex.

Полные импортируемые `.conf` сохранены только в Dropbox `.local/clients`.

## Backups

TimeWeb backups:

- before change: `/opt/wg-router/backups/20260710T054437Z`
- after `sergey-ipad-9.7-cenuta-domru`: `/opt/wg-router/backups/20260710T054515Z`
- after `sergey-ipad-9.7-fornex-domru`: `/opt/wg-router/backups/20260710T054518Z`
- after RU-via-BTH state update: `/opt/wg-router/backups/20260710T054544Z`

## Host Changes

Created through:

```bash
/opt/wg-router/commands.sh add-client sergey-ipad-9.7-cenuta-domru cenuta
/opt/wg-router/commands.sh add-client sergey-ipad-9.7-fornex-domru fornex
```

Added to `/opt/wg-router/state/ru_bth_clients.tsv`:

```text
10.50.50.36	sergey-ipad-9.7-cenuta-domru	remote-selector
10.50.50.37	sergey-ipad-9.7-fornex-domru	remote-selector
```

Applied:

```bash
/opt/wg-router/commands.sh apply-ru-bth
```

## Local Sync

Copied to `.local/clients`:

- `sergey-ipad-9.7-cenuta-domru.conf`
- `sergey-ipad-9.7-fornex-domru.conf`

Updated:

- `docs/registry/tunnels.md`
- `Personal/RESOURCE/IT/MIKROTIK/docs/TimeWeb_VPN_Registry.md`

## Verification

- `sessions --interface wg-clients` shows both new selector profiles.
- `test-client sergey-ipad-9.7-cenuta-domru` shows base route `10.50.50.36 -> table 200 -> wg-up-cenuta`.
- `test-client sergey-ipad-9.7-fornex-domru` shows base route `10.50.50.37 -> table 100 -> wg1`.
- Marked RU route check shows both new IPs go to `wg-home` table `300`.
- New profiles have no handshake yet, as expected before import on the device.

No private keys, preshared keys, QR-codes, or full configs are stored in this Obsidian summary.
