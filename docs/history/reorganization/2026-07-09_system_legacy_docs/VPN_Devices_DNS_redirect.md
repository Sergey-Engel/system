# DNS для VPN_Devices

## Цель
Устройства из списка `VPN_Devices` должны получать по DHCP DNS-серверы:

- `1.1.1.1`
- `8.8.8.8`

Остальные DHCP-клиенты остаются на общем DNS `192.168.88.1`.

## Применимость
Инструкция рассчитана на текущую конфигурацию:

- DHCP server: `defconf`
- LAN subnet: `192.168.88.0/24`
- LAN gateway: `192.168.88.1`
- VPN routing table: `WG1-Route`
- список устройств для VPN: `VPN_Devices`

Текущие устройства `VPN_Devices`:

| Address | Device |
| --- | --- |
| `192.168.88.11` | AppleTV Gostinnaya |
| `192.168.88.35` | Mac Mini M4 |
| `192.168.88.28` | AppleTV Spalna |
| `192.168.88.252` | DigitalRazor PC |

## Конфигурация

### 1. Создать DHCP option для DNS

```routeros
/ip dhcp-server option
add name=VPN-DNS code=6 value="'1.1.1.1''8.8.8.8'"
```

Проверить созданный option:

```routeros
/ip dhcp-server option print detail where name=VPN-DNS
```

Ожидаемое значение:

```text
raw-value=0x0101010108080808
```

### 2. Назначить DHCP option VPN-устройствам

```routeros
/ip dhcp-server lease
set [find address=192.168.88.11] dhcp-option=VPN-DNS
set [find address=192.168.88.35] dhcp-option=VPN-DNS
set [find address=192.168.88.28] dhcp-option=VPN-DNS
set [find address=192.168.88.252] dhcp-option=VPN-DNS
```

Проверить lease:

```routeros
/ip dhcp-server lease print detail where dhcp-option=VPN-DNS
```

### 3. Обновить DHCP lease на клиентах
Новые DNS-серверы применятся после обновления DHCP lease на самих устройствах.

Для каждого устройства выполнить один из вариантов:

- переподключить устройство к сети;
- отключить и включить Wi-Fi/Ethernet;
- выполнить DHCP renew в настройках ОС.

## Проверка

### На MikroTik

```routeros
/ip dhcp-server option print detail where name=VPN-DNS
/ip dhcp-server lease print detail where dhcp-option=VPN-DNS
```

### На клиентах
Проверить, что устройство получило DNS `1.1.1.1` и `8.8.8.8`.

Windows:

```powershell
ipconfig /all
```

macOS:

```shell
scutil --dns
```

DNS lookup:

```shell
nslookup example.com
```

## Откат

### Убрать специальный DNS с VPN-устройств

```routeros
/ip dhcp-server lease
set [find address=192.168.88.11] dhcp-option=""
set [find address=192.168.88.35] dhcp-option=""
set [find address=192.168.88.28] dhcp-option=""
set [find address=192.168.88.252] dhcp-option=""
```

После этого обновить DHCP lease на клиентах. Устройства снова получат DNS из общей DHCP network-конфигурации.

### Удалить DHCP option

```routeros
/ip dhcp-server option
remove [find name=VPN-DNS]
```

## Итоговая команда для применения

```routeros
/ip dhcp-server option
add name=VPN-DNS code=6 value="'1.1.1.1''8.8.8.8'"

/ip dhcp-server lease
set [find address=192.168.88.11] dhcp-option=VPN-DNS
set [find address=192.168.88.35] dhcp-option=VPN-DNS
set [find address=192.168.88.28] dhcp-option=VPN-DNS
set [find address=192.168.88.252] dhcp-option=VPN-DNS
```
