---
type: inventory
topic: mikrotik
status: active
created: 2026-06-22
provider: Cenuta
tags:
  - mikrotik
  - vpn
  - vps
  - cenuta
  - inventory
source:
  - "[Cenuta_VPS_инструкция_2026-06-22](<Cenuta_VPS_инструкция_2026-06-22.md>)"
  - "[Турецкие хостинг провайдеры 2026-июнь](<Турецкие хостинг провайдеры 2026-июнь.md>)"
---

## Назначение

Этот документ фиксирует рабочую информацию по аккаунту Cenuta, настройкам доступа и будущим VPS/Cloud-хостам этого провайдера.

На 2026-06-22 зафиксировано:

- аккаунт Cenuta зарегистрирован;
- в панели есть настройка `Allowed IP Access`;
- активных правил ограничения доступа нет;
- доступ сейчас разрешен со всех IP.
- получено уведомление Cenuta о входе в аккаунт с IP `194.61.140.217`.

Когда будет создан конкретный VPS/Cloud-сервер, добавить его в раздел [](#Реестр хостов).

## Реестр хостов

### Cenuta ID / клиентская панель

- Провайдер: `Cenuta`.
- Тип записи: аккаунт и клиентская панель провайдера.
- Статус: зарегистрировано.
- Панель: `https://id.cenuta.com/`.
- Связанная инструкция: [Cenuta: покупка VPS/Cloud, регистрация и оплата](<Cenuta_VPS_инструкция_2026-06-22.md>).
- Настройка доступа: `Allowed IP Access`.
- Текущий публичный IP, показанный панелью: `194.61.140.217`.
- Текущее состояние правил: правил нет, доступ разрешен со всех IP.

### VPS/Cloud host 1

- Статус: active, SSH-доступ проверен.
- Назначение: VPN/MikroTik/WireGuard-хост.
- Целевая роль: Fornex-аналог для турецкого WireGuard egress; на начальном этапе используется как upstream для TimeWeb-router, где `client-2` направляется в Cenuta, а `client-1` направляется в Fornex.
- Продукт: `Cenuta Cloud II`.
- Текущая ОС после maintenance 2026-06-28: `Ubuntu 24.04.4 LTS x86_64`.
- Текущий kernel после maintenance 2026-06-28: `GNU/Linux 6.8.0-124-generic`.
- Исходная ОС/kernel при первом аудите: `Ubuntu 24.04.3 LTS`, `6.8.0-71-generic`.
- Возможная альтернатива: `Debian 11 x64`.
- Hostname: `VM-65a473e7-94a5-4a83-bcd8-161603acf6a0`.
- Целевой hostname: `wg-tr-01`.
- Публичный IPv4: `89.252.153.129`.
- Network interface: `ens3`.
- IPv4 на интерфейсе: `89.252.153.129/24 metric 100`.
- IPv6: public IPv6 не зафиксирован; link-local `fe80::1c00:97ff:fe00:3c5e/64`.
- DNS-имя: не используется на начальном этапе; endpoint задается прямым IPv4 `89.252.153.129`.
- SSH-пользователь: `ubuntu`.
- SSH-команда:

```bash
ssh ubuntu@89.252.153.129
```

- WireGuard UDP port: `51840/udp`.
- Дата получения IP: 2026-06-22.
- Дата проверки SSH: 2026-06-22 09:54:25 UTC.
- Дата проверки параметров: 2026-06-28 11:53:59 UTC.
- Дата maintenance/update verification: 2026-06-28 20:18 UTC.
- Проверенный пользователь: `ubuntu`.
- Machine ID: `65a473e794a54a83bcd8161603acf6a0`.
- Virtualization: `kvm`.
- Hardware vendor/model: `Apache Software Foundation` / `CloudStack KVM Hypervisor`.
- Firmware: `0.5.1`, date `2011-01-01`.
- Boot ID на момент проверки: `2edc558d77db4a3dacbafbfd4d72f7ce` (меняется после перезагрузки).
- Примечания: заменить provider-generated hostname на `wg-tr-01`; DNS A-запись на начальном этапе не создавать; после первичной настройки добавить snapshot/backup-политику и факт смены пароля. Верхнеуровневая модель зафиксирована в [VPN HLD](<../architecture/overview.md>), рабочий план настройки - в [Cenuta Routing Setup](<../history/workplans/Cenuta_Routing_Setup.md>).

#### Initial проверка ОС, сети и WireGuard от 2026-06-28 до maintenance

- CPU: `Intel Xeon E312xx (Sandy Bridge, IBRS update)`, `1` socket, `1` core, `1` thread per core.
- RAM: `1.9Gi`, использовано `341Mi`, доступно `1.6Gi`.
- Swap: `0B`.
- Root filesystem: `/dev/vda1`, `ext4`, `48G`, использовано `2.4G`, свободно `46G`, `5%`.
- Boot partitions: `/dev/vda16` `ext4` `881M`; `/dev/vda15` `vfat` `105M` mounted as `/boot/efi`.
- Default gateway: `89.252.153.1` via `ens3`.
- DNS: `1.1.1.1`, `1.0.0.1`; DNS domain `cs1cloud.internal`.
- Timezone: `Etc/UTC`; NTP active; system clock synchronized.
- Reboot state на initial audit: `*** System restart required ***`.
- Reboot-required packages: `linux-image-6.8.0-124-generic`, `linux-base`, `libc6`.
- Package updates на initial audit: были накопленные обновления Ubuntu 24.04; `apt upgrade` и reboot выполнены 2026-06-28.
- UFW: `inactive`.
- Listening ports: SSH `22/tcp` на `0.0.0.0` и `[::]`; локальный `systemd-resolved` на `127.0.0.53/54:53`.
- Failed systemd units: `0 loaded units listed`.
- WireGuard kernel module: загружается успешно (`wireguard`, `curve25519_x86_64`, `udp_tunnel`, `ip6_udp_tunnel`).
- Forwarding: `net.ipv4.ip_forward = 0`, `net.ipv6.conf.all.forwarding = 0`; для роли WireGuard hub/router потребуется включить forwarding.

#### Live-аудит от 2026-06-28 20:00 UTC

Каноническая системная документация:

- [Cenuta Parameters](<../hosts/cenuta/Cenuta_Parameters.md>).
- [Cenuta Configuration](<../hosts/cenuta/Cenuta_Configuration.md>).
- [Cenuta live audit snapshot](<../history/cenuta/2026-06-28T1958Z-live-audit/README.md>).

Уточнения после аудита и maintenance 2026-06-28:

- SSH key access для Codex настроен через `.local/ssh/codex_cenuta_audit_20260628`.
- `ubuntu` имеет passwordless sudo.
- Upgrade/reboot выполнены; текущая ОС `Ubuntu 24.04.4 LTS`, kernel `6.8.0-124-generic`.
- Pending updates после проверки: `0`.
- Docker не установлен.
- `wireguard-tools` установлен: команды `wg` и `wg-quick` доступны.
- WireGuard kernel module загружен.
- `wg-cenuta` настроен и активен на `89.252.153.129:51840/udp`.
- Hostname задан: `wg-tr-01`.
- IPv4 forwarding включен; IPv6 forwarding выключен.
- Firewall/NAT: `nftables`, SSH `22/tcp` и WireGuard `51840/udp` разрешены.
- Cenuta public key: `3fg6rK3jeTdtGxtr0yX896BhEtH33OvWyx3ncTm6uR0=`.
- TimeWeb peer public key: `OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=`.
- TimeWeb private handoff config находится только на Cenuta в `/root/wireguard-handoff/timeweb-wg-up-cenuta.conf`; не копировать в Obsidian.

## Allowed IP Access

### Текущая настройка

Снимок состояния из панели:

```text
Allowed IP Access
Current IP Address: 194.61.140.217

IP Address/Subnet
eg. 194.61.140.217

IP Address/Subnet
No rules were set - access was allowed from all IPs.
```

Интерпретация:

- `Current IP Address: 194.61.140.217` - публичный IP, с которого сейчас открыт кабинет.
- `No rules were set` - явных allow-правил не задано.
- `access was allowed from all IPs` - кабинет не ограничен по source IP.

Это удобно на этапе первичной настройки, но для постоянного аккаунта лучше включить ограничение только если есть стабильный IP или запасной способ восстановления доступа.

### Форматы правил

Панель поддерживает такие форматы:

- `all` - ключевое слово, которое соответствует всем IP.
- `xxx.xxx.xxx.xxx` - один конкретный IPv4.
- `xxx.xxx.xxx.xxx/M` - CIDR-маска.
- `xxx.xxx.xxx.xxx/mmm.mmm.mmm.mmm` - маска в dotted decimal format.

Примеры из панели:

```text
120.123.123.57/28 matches IP from 120.123.123.48 to 120.123.123.63
120.123.123.57/16 matches IP from 120.123.0.0 to 120.123.255.255
```

### Практические варианты

Оставить как сейчас:

```text
No rules
```

Смысл: доступ к панели разрешен со всех IP. Это самый простой вариант до завершения покупки, оплаты и первичной настройки сервера.

Разрешить только текущий IP:

```text
194.61.140.217
```

или эквивалентно:

```text
194.61.140.217/32
```

Смысл: доступ к панели будет только с текущего публичного IP. Использовать только если IP действительно статический или есть понятная процедура восстановления доступа через поддержку.

Явно разрешить всем:

```text
all
```

Смысл: эквивалент открытого доступа по IP. Обычно это нужно только если интерфейс требует явное allow-правило; текущее состояние уже разрешает все IP без правил.


## SSH-доступ и смена пароля VPS

### Что нужно до подключения

Для SSH нужен именно публичный IP созданного VPS/Cloud-сервера из письма Cenuta или из панели услуги.

Важно: IP `194.61.140.217` выше зафиксирован как `Current IP Address` для входа в клиентскую панель. Это IP текущего подключения к Cenuta ID, а не обязательно IP будущего сервера. Для SSH использовать только IP, выданный в карточке конкретного VPS/Cloud-хоста.

Текущий публичный IPv4 сервера Cenuta Cloud II: `89.252.153.129`.

Минимальные данные для входа:

- публичный IPv4 сервера;
- SSH-пользователь для текущего сервера: `ubuntu`;
- временный пароль или SSH key;
- SSH-порт: обычно `22`, если не указан другой.

Пароль сервера не записывать в Obsidian. Хранить в password manager.

### Вход по SSH с Mac

Открыть `Terminal` на Mac и выполнить:

```bash
ssh ubuntu@89.252.153.129
```

Общий формат:

```bash
ssh <username>@<IPv4_сервера_Cenuta>
```

Если для другого сервера в письме указан другой пользователь:

```bash
ssh <username>@<IPv4_сервера_Cenuta>
```

Если SSH-порт не стандартный:

```bash
ssh -p <порт> <username>@<IPv4_сервера_Cenuta>
```

При первом входе SSH может показать предупреждение о новом host key:

```text
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

Если IP совпадает с IP сервера из панели Cenuta и сервер только что создан, ввести:

```text
yes
```

После этого ввести временный пароль. При вводе пароль в терминале не отображается: это нормально.

### Проверка, что вошли на правильный сервер

После входа выполнить:

```bash
whoami
hostnamectl
ip -br addr
```

Проверить:

- `whoami` показывает ожидаемого пользователя;
- hostname соответствует свежему серверу или стандартному имени образа;
- в сетевых адресах есть IP, выданный Cenuta.

### Смена пароля текущего пользователя

Если вошли как `root`, сменить root-пароль:

```bash
passwd
```

Порядок:

1. Ввести текущий временный пароль, если система запросит `Current password`.
2. Ввести новый пароль.
3. Повторить новый пароль.
4. Дождаться сообщения об успешной смене пароля.

Если вошли не как `root`, а как обычный пользователь, сменить пароль этого пользователя:

```bash
passwd
```

Если нужно сменить пароль другого пользователя и есть `sudo`:

```bash
sudo passwd <username>
```

Root-пароль на Ubuntu лучше не включать без необходимости. Для администрирования достаточно пользователя с `sudo`.

### Проверка нового пароля

Не закрывая текущий SSH-сеанс, открыть второе окно `Terminal` и проверить новый вход:

```bash
ssh <username>@<IPv4_сервера_Cenuta>
```

Если вход успешен, старый временный пароль больше не нужен. После проверки можно закрыть первый сеанс:

```bash
exit
```

В реестр хоста записать только факт смены пароля и дату, без самого пароля:

```markdown
- Пароль: сменен 2026-06-22, хранится в password manager.
```

### Если SSH не работает

Короткая диагностика:

```bash
ping <IPv4_сервера_Cenuta>
ssh -vvv <username>@<IPv4_сервера_Cenuta>
```

Типовые причины:

- сервер еще не активирован после оплаты;
- используется IP входа в панель, а не IP сервера;
- неверный пользователь: попробовать `root`, `ubuntu`, `debian`;
- неверный пароль или пароль уже был изменен;
- SSH слушает не на `22` порту;
- firewall в панели или внутри ОС закрыл SSH;
- образ ОС еще устанавливается или сервер перезагружается.

Если SSH недоступен, но сервер активен, зайти через web/VNC/console в панели Cenuta и проверить:

```bash
systemctl status ssh
ss -tlnp | grep ':22'
ufw status
```

### Факт успешного входа

Зафиксировано успешное подключение:

```bash
ssh ubuntu@89.252.153.129
```

Системная информация при входе:

```text
Welcome to Ubuntu 24.04.3 LTS (GNU/Linux 6.8.0-71-generic x86_64)

System information as of Mon Jun 22 09:54:25 UTC 2026

System load:  0.0
Processes:    97
Usage of /:   3.4% of 47.39GB
Users logged in: 0
Memory usage: 8%
IPv4 address for ens3: 89.252.153.129
Swap usage:   0%

0 updates can be applied immediately.
```

Дополнительно Ubuntu сообщает, что `Expanded Security Maintenance for Applications` не включен. Для текущего VPN-хоста это не блокер; к ESM можно вернуться позже, если сервер будет жить долго и на нем появятся приложения из Universe/Multiverse.

## Рекомендация по безопасности

Пока аккаунт новый и сервер еще не зафиксирован, разумно оставить доступ без IP-ограничения, чтобы не заблокировать себя из-за смены адреса.

После покупки и проверки сервера:

1. Проверить, есть ли в Cenuta двухфакторная аутентификация и включить ее, если доступна.
2. Убедиться, что email и телефон восстановления работают.
3. Если используется стабильный домашний/офисный/VPN IP, добавить его как single IP или `/32`.
4. Не использовать широкую подсеть вроде `/24`, если нет осознанной причины разрешать весь диапазон.
5. После изменения правила сразу проверить вход в панель из нового браузерного сеанса.

## Шаблон записи нового хоста

```markdown
### <hostname>

- Провайдер: `Cenuta`.
- Продукт: `Cloud II` / `VPS II` / другое.
- Статус: active / suspended / cancelled / planned.
- Назначение:
- Дата заказа:
- Период оплаты:
- Локация:
- ОС:
- Публичный IPv4:
- IPv6:
- DNS-имя:
- SSH-порт:
- SSH-пользователь:
- Пароль: не хранить в заметке; указать только дату смены и место хранения.
- VPN-порт:
- Firewall:
- Snapshot:
- Backup:
- Автоплатеж:
- Примечания:
```

## Журнал изменений

- 2026-06-22: зафиксирована регистрация аккаунта Cenuta и состояние `Allowed IP Access`: текущий IP `194.61.140.217`, правил нет, доступ разрешен со всех IP.
- 2026-06-22: добавлено уведомление Cenuta о входе в аккаунт и английский перевод турецкого текста.
- 2026-06-22: добавлена инструкция по SSH-входу на VPS/Cloud-сервер и смене пароля.
- 2026-06-22: добавлен публичный IPv4 сервера Cenuta Cloud II `89.252.153.129` и конкретная SSH-команда.
- 2026-06-22: SSH-пользователь текущего сервера уточнен как `ubuntu`; команда изменена на `ssh ubuntu@89.252.153.129`.
- 2026-06-22: зафиксирован успешный SSH-вход и фактические параметры Ubuntu 24.04.3 LTS на сервере.
