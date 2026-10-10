---
created: 2026-04-12 09:32
topic: router
tags:
  - vpn
  - mikrotic
  - wan
  - LangGraph
  - wify
---
# Config

## Сводка параметров старой конфигурации (Nakhimova)

> [!info] Технические детали (из ART-001 (source reference not migrated))
> - **Устройство**: RB750Gr3 (RouterOS 7.12.1)
> - **Identity**: `MikroTik Nakhimova`
> - **LAN (Bridge)**: `192.168.88.1/24` (ether2-ether5)
> - **DHCP**: Пул `192.168.88.10 - 192.168.88.254`
> - **VPN**: WireGuard на порту `13231` (MTU 1420)
> - **Сервисы**: IPv6 отключен, включен Fasttrack.

> [!abstract] Параметры Провайдера (Static IP)
> - **IP-адрес**: `10.12.20.168`
> - **Маска**: `/22` (`255.255.252.0`)
> - **Шлюз**: `10.12.20.1`
> - **DNS**: `192.168.248.21`, `192.168.251.21`
> - **Интерфейс**: `ether1` (WAN)

> [!tip] Зарезервированные устройства (Static DHCP)
> - **IP `.206`** (`00:11:32:5D:AA:19`) — **Synology NAS**.
> - **IP `.248`** (`00:D8:61:3A:23:BC`) — **Samsung TV / DigitalRazor**.
> - **IP `.221`** (`80:EA:96:E7:DF:FF`) — **seap**.


### Quick Set
![Pasted image 20260412093604.png](<assets/attachments/Pasted image 20260412093604.png>)

### Interface

![Pasted image 20260412093646.png](<assets/attachments/Pasted image 20260412093646.png>)
![Pasted image 20260412094313.png](<assets/attachments/Pasted image 20260412094313.png>)

![Pasted image 20260412094358.png](<assets/attachments/Pasted image 20260412094358.png>)

### IP Address

![Pasted image 20260412094542.png](<assets/attachments/Pasted image 20260412094542.png>)

![Pasted image 20260412094606.png](<assets/attachments/Pasted image 20260412094606.png>)

![Pasted image 20260412094637.png](<assets/attachments/Pasted image 20260412094637.png>)

![Pasted image 20260412094708.png](<assets/attachments/Pasted image 20260412094708.png>)

![Pasted image 20260412094731.png](<assets/attachments/Pasted image 20260412094731.png>)
落,Description:
