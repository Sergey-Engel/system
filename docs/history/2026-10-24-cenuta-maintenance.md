---
type: maintenance-report
status: completed-with-limitations
updated: 2026-10-24
tags: [cenuta, vpn, maintenance, backup]
---

# Cenuta: Обслуживание 24 Октября 2026

По поручению пользователя обновлен сервер `89.252.153.129`,
`VM-65a473e7-94a5-4a83-bcd8-161603acf6a0`. Обслуживание выполнено через
существующий SSH-ключ с проверкой host key и `sudo -n`.

## Обновление

Установлены 14 обновлений Ubuntu 24.04.5 LTS, без новых пакетов, удаления,
autoremove или перехода на другой выпуск ОС. Сохранены существующие
конфигурации через `--force-confdef/--force-confold`.

| Компонент | До | После |
| --- | --- | --- |
| AppArmor | `4.0.1really4.0.1-0ubuntu0.24.04.8` | `4.0.1really4.0.1-0ubuntu0.24.04.9` |
| snapd | `2.76.3+ubuntu24.04` | `2.77.1+ubuntu24.04` |
| GLib | `2.80.0-6ubuntu3.9` | `2.80.0-6ubuntu3.10` |
| open-vm-tools | `2:13.0.10-0ubuntu0.24.04.1` | `2:13.0.10-0ubuntu0.24.04.2` |
| tmux | `3.4-1ubuntu0.1` | `3.4-1ubuntu0.2` |

Также обновлены open-iscsi/libopeniscsiusr, ubuntu-pro-client/l10n и sosreport.
После установки обычных доступных обновлений нет; `cloud-init` отложен
самим APT из-за phasing и принудительно не устанавливался.

Ядро до/после `6.8.0-147-generic`. Перезагрузка не требовалась и не проводилась;
boot ID совпал. VPN-службы вручную не перезапускались.

## Копии И Неизменность

Обе конфигурационные копии VERIFIED: состав 84 файла хоста, проверены
контрольные суммы и временное офлайн-восстановление 10 файлов:

- До: `.local/backups/cenuta/2026-10-24T014350Z_current-config/backup.tar.gz`,
  6 084 299 байт.
- После: `.local/backups/cenuta/2026-10-24T014607Z_current-config/backup.tar.gz`,
  6 084 215 байт.

Это не образы диска; полный аварийный запуск восстановленного VPS не проверялся.
Приватные снимки и журнал установки:
`.local/backups/cenuta/20261024-maintenance/`.
Архивы и приватные материалы исключены из Git.

SHA-256 12 выбранных файлов WireGuard, netplan, reality-c3 guard, локальных
systemd units и nftables до/после совпали. Также совпали IPv4 RPDB, все
IPv4 route tables, WireGuard peer identities/AllowedIPs и структурный nft
ruleset без изменяющихся counters/handles. Это ограниченный снимок, не
побайтовая проверка всего диска. Ключи/профили/назначения устройств не менялись.
Monitoring baseline и recovery policy не переподписывались.

## Проверки Работы

- `dpkg --audit` чистый, failed units отсутствуют.
- `wg-quick@wg-cenuta`, nftables, `wstunnel-cenuta-wg-fallback`, SSH active.
- Основной WG peer имеет свежий handshake. У второго настроенного peer
  latest-handshake=0 до и после обслуживания; его сквозная работа не подтверждена.
  WSTunnel проверен как active-служба, но трафик на резерв не переключался.
- Внешний DNS хоста разрешается; HTTPS хоста возвращает HTTP 204.
- Изолированная SSTP split-проба TimeWeb: оба выхода ready,
  Cenuta `89.252.153.129`, Fornex `103.75.126.143`; автоматического
  переключения и назначения пользовательских устройств не выполнялось.
- Два свежих цикла TimeWeb monitoring после установки: `01:46:06` и
  `01:48:07 UTC` (04:46:06 и04:48:07 по Стамбулу), оба upstream UP/fresh,
  внешние HTTPS-пробы valid/success; подтверждены peer ICMP, DNS UDP/TCP.

Repository validation PASSED:521 public files,67 profiles,22 devices,
problems отсутствуют. Private store VERIFIED:3694 files/372 records.
`git diff --check` без ошибок; обе копии подтвержденно исключены из Git.
Код не менялся, повторный запуск программных тестов не выполнялся.

Проверки с реальных клиентских устройств не выполнялись; успешная серверная
проба не заменяет приемку приложений на устройствах. Код панели/API и версия
ее выпуска не менялись. Commit/push этим поручением не запрашивались.
