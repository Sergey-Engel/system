---
type: inventory
topic: mikrotik
system: cenuta
status: active
created: 2026-06-28
updated: 2026-10-24
provider: Cenuta
tags:
  - mikrotik
  - vpn
  - vps
  - cenuta
  - inventory
source:
  - "[Cenuta_Configuration](<Cenuta_Configuration.md>)"
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[VPN_Configuration_Registry](<../../registry/configuration.md>)"
---

## Подтвержденное состояние

24 октября 2026 установлены 14 обновлений Ubuntu 24.04.5 LTS, без
перезагрузки (не требуется). Ядро `6.8.0-147-generic`; WireGuard, nftables,
WSTunnel и SSH active. Контрольные конфигурации, маршруты, peers и структура
firewall до/после совпали. Копии до/после VERIFIED.
[Отчет и границы проверки](<../../history/2026-10-24-cenuta-maintenance.md>).
WSS reserve24 октября проверен по mTLS/WebSocket и UDP-доставке,
без переключения рабочих WG peers;
[протокол восстановления](<../../history/2026-10-24-cenuta-wss-recovery.md>).
Ниже сохранен отдельно датированный исторический снимок 13 сентября.

Снимок: live.json (source reference not migrated),
`hosts.cenuta`, 2026-09-13 14:45 UTC. Cenuta уже настроена как
WireGuard-egress TimeWeb, не ожидает установки или handoff.
Серверный инвентарь не заменяет приемку полного клиентского трафика.

## Хост и доступ

- Публичный IPv4: `89.252.153.129`; `ens3`: `89.252.153.129/24`.
- Default route: `89.252.153.1` через `ens3`.
- Kernel: `6.8.0-139-generic`; uptime около 2 суток; failed units: 0.
- RAM: 1968 MiB; swap отсутствует; корневой раздел 48 GiB, занят на 9%.
- На `ens3` виден только link-local IPv6; внешняя IPv6-связность не проверялась.
- Доступ: `ubuntu@89.252.153.129:22`, локальный alias `cenuta`.
  Ссылка на ключ: `.local/ssh/codex_cenuta_audit_20260628`;
  постоянный trust store: `.local/ssh/known_hosts_cenuta`.
- Проверка host key обязательна; временный `known_hosts_cenuta_temp`
  не использовать. Полная процедура: [Host_Access_Guide](<../../operations/access.md>).
- Название продукта `Cenuta Cloud II` сохранено из прежней карточки;
  панель провайдера отдельно не проверялась.

## Listeners и роли

- `51840/udp`: host-level `wg-cenuta`, адрес `10.40.40.1/24`.
- `22/tcp`: административный SSH.
- `127.0.0.53:53` и `127.0.0.54:53`: локальные DNS stubs, TCP/UDP.
- `89.252.153.129:68/udp`: DHCP-клиент.
- Docker не является runtime-границей этого WireGuard-контура:
  интерфейс, маршруты и nft находятся в namespace хоста.

В `wg-cenuta` два peer от TimeWeb:

- `10.40.40.2/32`: существующий `wg-relay/wg-up-cenuta`.
- `10.40.40.3/32`: отдельный userspace WireGuard outbound TimeWeb REALITY.

Оба peer имеют handshake и ненулевые counters в снимке.
Cenuta не является BTH hub и не принимает конечные selector-профили напрямую.
Реестр клиентов: [TimeWeb_VPN_Registry](<../../registry/tunnels.md>).

## Сервисы и конфигурация

- `wg-quick@wg-cenuta.service`: `active/exited`, интерфейс поднят.
- `nftables.service`: `enabled`, `active/exited`.
- Выход сети `10.40.40.0/24` через `ens3` разрешен firewall и MASQUERADE.
  Sysctl IPv4 forwarding в свежем снимке отдельно не снят.
- Native nft `inet reality_c3` ограничивает source `10.40.40.3`:
  блокирует доступ к самому хосту, частным/служебным адресам и выходам кроме `ens3`.
- Рабочий WG-конфиг: `/etc/wireguard/wg-cenuta.conf`.
- Основной firewall: `/etc/nftables.conf`; дополнение REALITY:
  `/etc/reality-c3/guard.sh`, `guard.nft`, `guard.expected`.
- Ранее учтенные пути: `/etc/wireguard/wg-cenuta.key`,
  `/etc/netplan/50-cloud-init.yaml`,
  `/root/wireguard-handoff/timeweb-wg-up-cenuta.conf`.
  Последний является историческим handoff, не будущим планом и не текущим master.

Подробная схема и границы проверки путей: [Cenuta_Configuration](<Cenuta_Configuration.md>).

## Мастер-копии и история

`System/...` отсчитывается от общего Dropbox рядом с `Obsidian/`.

- REALITY Cenuta: `services/transport/timeweb-reality/stage8-cenuta/`.
  Импортируемые профили публикуются в `.local/clients/`.
- Архитектура и владельцы файлов: [VPN_HLD](<../../architecture/overview.md>), [VPN_Configuration_Registry](<../../registry/configuration.md>).
- Оригинал страницы:
  `services/transport/documentation-audit-20260913/before/Obsidian/Personal/RESOURCE/IT/MIKROTIK/docs/Cenuta_Parameters.md`.
- Существующие исторические ссылки:
  [Аудит 2026-06-28](<../../history/cenuta/2026-06-28T1958Z-live-audit/README.md>),
  [Post-update 2026-06-28](<../../history/cenuta/2026-06-28T2017Z-post-update-check/README.md>),
  [Настройка wg-cenuta](<../../history/cenuta/2026-06-28T2025Z-wg-cenuta-setup/README.md>).
  Соответствующие каталоги существуют в `.local/backups/cenuta/`.

Архивы датированы и не обозначают «последний безопасный backup».
Ранние timeout/reboot/handoff-записи сохранены в оригинале, не описывают текущий отказ.

## Ограничения

Снимок не содержит новых внешних HTTP, браузерных, DNS/TUN или bandwidth-тестов.
Запущенный WG, SSH listener и handshake не подтверждают исправность всех
сайтов, устройств, fail-closed или длительную стабильность. Старый инцидент
2026-09-11 нельзя переносить на текущий статус без повторного воспроизведения.
SSH-security, пакеты, reboot-required и IPv6 forwarding сейчас не перепроверены.
Полные конфиги, ключи, PSK, UUID и QR здесь не хранятся.
