---
type: backup
topic: mikrotik
system: timeweb
status: active
created: 2026-06-29T15:20:00Z
tags:
  - mikrotik
  - vpn
  - backup
  - timeweb
  - wireguard
---

## Назначение

Sanitized checkpoint после исправления selector client config template, расширения `wg-client-config` на все клиентские конфиги и ротации `sergey-iphone-12`.

## Что исправлено

- `wg-client-config` теперь показывает:
  - `selector` configs из `/root/wg-client-exports/`;
  - `legacy` configs из `/opt/wg/clients/`;
  - `bth` configs из `/opt/wg/clients_bth/`.
- Selector client configs больше не используют `AllowedIPs = 0.0.0.0/0`.
- Новый selector template использует public-IPv4 split list с исключением local/private IPv4 сетей.
- Selector client configs получили ULA IPv6 addresses `fd00:50:50::x/128`.
- Client-side `AllowedIPs` содержит `::/0`, чтобы предотвратить прямые IPv6 leaks; IPv6 через selector наружу не маршрутизируется.
- Server-side `wg-clients` peer `AllowedIPs` содержит IPv4 и ULA IPv6 каждого selector client.
- Добавлены команды:
  - `sudo /opt/wg-router/commands.sh refresh-clients`;
  - `sudo /opt/wg-router/commands.sh rotate-client <selector-client-name>`.

## Ротация

`sergey-iphone-12` был перевыпущен, потому что его private key был раскрыт в чате.

- Client IP: `10.50.50.20/32`.
- Client IPv6 ULA: `fd00:50:50::20/128`.
- New public key: `olpgvvhQDnRdakhbKYYPMpgjEYFFNyEWTsxTjBXPsnQ=`.

## Проверки

- `wg-client-config` interactive list показывает 27 configs: 2 BTH, 21 legacy, 4 selector.
- Selector exports перегенерированы:
  - `client-1-fornex.conf`;
  - `client-2-cenuta.conf`;
  - `sergey-iphone-12-cenuta.conf`;
  - `sveta-iphone-cenuta.conf`.
- Route checks для `sergey-iphone-12` и `sveta-iphone` проходят через table `200` -> `wg-up-cenuta`.
- Root-only backup after refresh: `/opt/wg-router/backups/20260629T152006Z`.

## Состав снимка

- `commands_and_docs_sanitized.txt` - sanitized `commands.sh`, `wg-client-config`, TimeWeb docs.
- `runtime_verification.txt` - safe fields, counts, route checks, public inventory, backup metadata.
- `SHA256SUMS` - checksums for snapshot files.

## Секреты

Полные client configs, private keys, preshared keys и QR-code не сохранены в этом snapshot.
