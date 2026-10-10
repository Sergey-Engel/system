---
type: guide
topic: mikrotik
status: draft
created: 2026-07-25
provider: Hosting.com.tr
tags:
  - mikrotik
  - vpn
  - vps
  - hosting-com-tr
source:
  - "[Турецкие хостинг провайдеры 2026-июнь](<Турецкие хостинг провайдеры 2026-июнь.md>)"
---

## Резюме

> [!summary] Практический выбор
> Для замены Cenuta я бы начинал с **Hosting.com.tr VPS Medium** в локации **Türkiye**: 4 CPU, 4 GB RAM, 100 GB NVMe. Это дороже минимального VPS Small, но дает нормальный запас под два параллельных VPN-сервиса: обычный WireGuard и AmneziaWG.

Hosting.com.tr выглядит более зрелым локальным турецким вариантом, чем Cenuta:

- есть отдельная линейка VPS с Турцией и другими локациями;
- на странице VPS публично указаны характеристики, root-доступ, web-панель, Linux/Windows OS и ticket support 7/24;
- есть оплата картой, Havale/EFT и другие способы оплаты по условиям сервиса;
- сайт остается турецко-ориентированным, но публичная продуктовая страница читается через автоперевод лучше, чем Cenuta.

## Адреса

- Сайт: [hosting.com.tr](https://www.hosting.com.tr/)
- VPS Server: [hosting.com.tr/server/vps-server](https://www.hosting.com.tr/server/vps-server/)
- Регистрация нового клиента: [hosting.com.tr/yeni-musteri](https://hosting.com.tr/yeni-musteri)
- Клиентская зона: [hosting.com.tr](https://www.hosting.com.tr/) -> `Müşteri Paneli` / вход в аккаунт.
- Knowledge Base: [hosting.com.tr/index.php?rp=/knowledgebase](https://www.hosting.com.tr/index.php?rp=%2Fknowledgebase)
- Договор/условия сервиса: [hosting.com.tr/sozlesmeler/hizmet](https://www.hosting.com.tr/sozlesmeler/hizmet/)

## Рекомендуемый хост

### Базовая рекомендация

Покупать: **VPS Medium**.

Текущая публичная конфигурация на 25 июля 2026:

- CPU: 4 Core CPU.
- RAM: 4 GB.
- Disk: 100 GB.
- Traffic: unlimited incoming/outgoing.
- Port: 200 Mbps.
- IP: 1 dedicated IPv4.
- Access: full root.
- OS: Linux, выбрать **Ubuntu 24.04 LTS x64**.
- Location: **Türkiye**.
- Цена при месячной оплате: $11.99 / 569.53 TRY.
- Цена при оплате на год: $9.99/mo / 474.52 TRY/mo.
- Цена при оплате на два года: $7.99/mo / 379.52 TRY/mo.

Почему не VPS Small:

- VPS Small 2 CPU / 2 GB RAM / 50 GB диска подойдет для одного легкого WireGuard;
- для WireGuard + AmneziaWG одновременно 2 GB RAM остается минимальным запасом, особенно после обновлений, логов, мониторинга и возможной Docker/панельной установки Amnezia;
- 4 GB RAM снижают риск нестабильности и дают место для диагностики без срочного upgrade.

### Когда брать VPS Large

Брать **VPS Large** вместо Medium, если:

- планируется много активных клиентов;
- Amnezia будет ставиться не минимально, а через Docker/Amnezia Server/панель;
- нужно держать дополнительные сервисы: мониторинг, reverse proxy, тестовые контейнеры;
- хочется запас по RAM на 6 GB без последующего апгрейда.

Публичная конфигурация VPS Large: 4 Core CPU, 6 GB RAM, 150 GB disk. Месячная цена на странице: $19.99 / 949.53 TRY.

## Параметры покупки

Рекомендуемые значения при заказе:

| Поле | Что выбрать | Почему |
| ---- | ----------- | ------ |
| Product | VPS Server | Нужен unmanaged Linux VPS с root-доступом. |
| Plan | VPS Medium | Оптимальный запас под WireGuard + AmneziaWG. |
| Billing | 1 month для первого теста | Сначала проверить стабильность и маршруты, потом продлевать на год. |
| Location | Türkiye | Нужен турецкий egress IP. |
| OS | Ubuntu 24.04 LTS x64 | Современная LTS, уже используется на Cenuta. |
| Control panel | Не ставить, если есть выбор | Для VPN не нужен cPanel/Plesk. |
| Extra IP | Не брать на старте | Один IPv4 достаточен. |
| Port speed upgrade | Не брать на старте | 200 Mbps должно хватить; upgrade до 1 Gbps рассматривать после теста. |
| Backup add-on | Не полагаться как на единственный backup | Нужны свои exports/config backups после настройки. |

## Стартовая покупка

1. Открыть [VPS Server](https://www.hosting.com.tr/server/vps-server/).
2. Выбрать **VPS Medium**.
3. Нажать `Satın Al`.
4. В конфигураторе выбрать:
   - срок: `1 Aylık`;
   - локация: `Türkiye`;
   - OS: `Ubuntu 24.04`;
   - панель управления: без платной панели, если это отдельная опция.
5. Перейти в корзину.
6. Создать аккаунт или войти в существующий.
7. Проверить invoice/billing данные.
8. Оплатить турецкой картой.
9. Дождаться письма с IP, логином и паролем/ключом. На странице VPS Hosting.com.tr указывает, что автоматическая установка после оплаты обычно выполняется в течение 30 минут.

Турецкие термины:

| Турецкий текст | Смысл |
| -------------- | ----- |
| `Satın Al` | Купить |
| `Sepet` | Корзина |
| `Ödeme Yap` | Оплатить |
| `Fatura` | Счет/invoice |
| `Hizmetlerim` | Мои услуги |
| `Sunucu` | Сервер |
| `Yeniden Başlat` | Перезагрузить |
| `Yeniden Kurulum` | Переустановка ОС |
| `Destek` | Поддержка |

## Первичная проверка после активации

После получения IP:

```bash
ssh root@<HOSTING_COM_TR_IP>
```

Если выдан пользователь не `root`, использовать его:

```bash
ssh <USERNAME>@<HOSTING_COM_TR_IP>
```

Базовая проверка:

```bash
hostnamectl
```

```bash
uname -a
```

```bash
ip -br addr
```

```bash
curl -4 https://api.ipify.org
```

```bash
sudo apt update
```

```bash
apt list --upgradable
```

```bash
sudo apt upgrade
```

Проверить, нужен ли reboot:

```bash
test -f /var/run/reboot-required && cat /var/run/reboot-required || echo "reboot not required"
```

## Базовая подготовка Ubuntu

Создать отдельный SSH-ключ на локальной машине:

```bash
ssh-keygen -t ed25519 -f .local/ssh/codex_hosting_com_tr_audit_20260725 -C "codex-hosting-com-tr-audit-20260725"
```

Загрузить ключ на сервер:

```bash
ssh-copy-id -i .local/ssh/codex_hosting_com_tr_audit_20260725.pub root@<HOSTING_COM_TR_IP>
```

Проверить вход по ключу:

```bash
ssh -i .local/ssh/codex_hosting_com_tr_audit_20260725 -o IdentitiesOnly=yes root@<HOSTING_COM_TR_IP>
```

Поставить базовые пакеты:

```bash
sudo apt install -y curl ca-certificates gnupg lsb-release jq wireguard wireguard-tools nftables qrencode
```

Включить forwarding:

```bash
printf '%s\n' 'net.ipv4.ip_forward=1' 'net.ipv6.conf.all.forwarding=1' | sudo tee /etc/sysctl.d/99-vpn-forwarding.conf
```

```bash
sudo sysctl --system
```

## План сетевой схемы

Чтобы WireGuard и AmneziaWG не конфликтовали:

| Сервис | Interface | UDP port | Subnet | Назначение |
| ------ | --------- | -------- | ------ | ---------- |
| WireGuard | `wg-hostingtr` | `51840/udp` | `10.60.60.0/24` | Замена Cenuta как обычного WG upstream. |
| AmneziaWG | `awg0` | `51841/udp` | `10.61.61.0/24` | Отдельный DPI-resistant VPN для клиентов. |

Правила:

- не использовать один и тот же UDP-порт для WG и AmneziaWG;
- не смешивать клиентские subnet с TimeWeb/Cenuta/Fornex текущими сетями;
- до миграции с Cenuta не менять TimeWeb production routing;
- сначала поднять новый сервер, проверить прямой AmneziaWG и обычный WG, затем подключать его как новый upstream.

## WireGuard: первичная установка

Для обычного WireGuard сервер должен иметь:

- `/etc/wireguard/wg-hostingtr.conf`;
- private key только на сервере;
- публичный ключ в документации можно фиксировать;
- firewall/NAT через nftables;
- systemd unit `wg-quick@wg-hostingtr`.

Минимальная проверка после настройки:

```bash
sudo systemctl status wg-quick@wg-hostingtr nftables --no-pager
```

```bash
sudo wg show wg-hostingtr
```

```bash
curl -4 https://api.ipify.org
```

## AmneziaWG: что учесть до установки

AmneziaWG лучше ставить после обычного WireGuard и базовой проверки сервера.

Важные моменты:

- AmneziaWG является WireGuard-подобным протоколом с обфускацией против DPI;
- для Linux-сервера обычно нужен пакет/модуль `amneziawg`, headers текущего kernel и DKMS-сборка;
- после kernel upgrade может понадобиться reboot и проверка DKMS/module status;
- server/client параметры AmneziaWG должны совпадать, иначе handshake не поднимется;
- для AmneziaWG нужен отдельный порт и отдельная подсеть;
- не отключать IPv6 глобально без необходимости: это может ломать часть клиентских сценариев AmneziaVPN.

Перед установкой AmneziaWG проверить:

```bash
uname -r
```

```bash
sudo apt install -y linux-headers-$(uname -r) software-properties-common gnupg2
```

Финальный способ установки выбрать отдельной задачей:

- **минимальный headless install**: меньше зависимостей, лучше для стабильного VPN-only VPS;
- **Amnezia/панель/Docker install**: удобнее управлять клиентами, но выше потребление RAM и больше движущихся частей.

Для текущей архитектуры предпочтительнее **headless install**, потому что сервер нужен как сетевой узел, а не как универсальная панель.

## Проверки перед миграцией с Cenuta

До переключения production-traffic:

1. Проверить внешний IP нового сервера.
2. Проверить, что UDP-порты WireGuard и AmneziaWG доступны снаружи.
3. Проверить обычный WireGuard-клиент с одного тестового устройства.
4. Проверить AmneziaWG-клиент с одного тестового устройства.
5. Проверить стабильность в течение 24-48 часов.
6. Сделать backup `/etc/wireguard`, nftables config и списка установленных пакетов.
7. Только после этого добавлять новый upstream на TimeWeb.

## Что документировать после покупки

Создать отдельную операционную карточку:

- `Hosting_com_tr_Parameters.md`;
- provider/product/plan;
- service ID из панели;
- дата заказа;
- дата следующей оплаты;
- публичный IPv4;
- hostname;
- SSH-команда;
- WireGuard interface/port/subnet;
- AmneziaWG interface/port/subnet;
- где лежат backup/export/config artifacts в Dropbox System.

Не сохранять в Obsidian:

- private keys;
- preshared keys;
- QR-коды;
- полные клиентские конфиги;
- пароль root/панели.

## Источники

- [Hosting.com.tr VPS Server](https://www.hosting.com.tr/server/vps-server/) - тарифы, локации, root-доступ, OS, traffic, порт, backup, SLA/support.
- [Hosting.com.tr service terms](https://www.hosting.com.tr/sozlesmeler/hizmet/) - методы оплаты и условия активации.
- [Domain ve Hosting Nasıl Satın Alınır?](https://www.hosting.com.tr/bilgi-bankasi/domain-ve-hosting-nasil-satin-alinir/) - общий checkout flow: счет, выбор оплаты, карта/Havale/EFT.
- [AmneziaWG Linux kernel module](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module) - требования к kernel headers/DKMS и установка пакета.
- [AmneziaWG Go](https://github.com/amnezia-vpn/amneziawg-go) - описание AmneziaWG как WireGuard-like протокола с DPI-защитой.
