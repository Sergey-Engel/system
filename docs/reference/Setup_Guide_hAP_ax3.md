---
type: historical-guide
status: historical-do-not-apply
updated: 2026-09-13
---

> [!warning] Историческая миграция, не текущий runbook
> hAP ax3 уже установлен. Адреса, DHCP, интерфейсы и команды обновления ниже не применять поверх работающего роутера. Актуальное описание: [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>), [VPN_HLD](<../architecture/overview.md>), [MikroTik_Quick_Guide](<../quick-start.md>). При ревью из двух примеров удалены литералы паролей; если они применялись, требуется отдельная ротация. Роутер и пароли не менялись. Исходная закрытая копия в services/transport/documentation-audit-20260913/before содержит старые значения и не должна публиковаться.

# Инструкция по настройке MikroTik hAP ax3 (C53UiG+5HPaxD2HPaxD)

Данное руководство описывает пошаговый процесс миграции со старого роутера (Nakhimova 11) на новый **hAP ax3**.

![800](<../../.local/config/router-factory-label.png>)
## 🛡 Стратегия безопасной миграции
Чтобы не остаться без интернета в процессе настройки и избежать конфликтов:

1. **Изоляция**: Настраиваем новый роутер «на столе», пока старый продолжает раздавать интернет. **НЕ втыкайте** кабель провайдера в новый роутер до Шага 5.
2. **Подключение**: 
   - Используйте Wi-Fi (сеть `MikroTik-XXXXXX`, пароль на наклейке роутера в поле **Wifi Password**).
   - Либо Ethernet (порты 2, 3, 4 или 5). 
3. **Конфликт имен**: На этапе 1 используйте временное имя Wi-Fi (например, `AX3-Setup`), чтобы ноутбук не метался между двумя роутерами.

---

## Часть 1: Автономная настройка (OFFLINE)
*На этом этапе роутер подключен только к питанию и вашему ноутбуку.*

### Шаг 1: Базовая безопасность
1. Зайдите через WinBox (192.168.88.1, вкладка **Neighbors** > клик по MAC).
2. **System > Users**: Установите сложный пароль на `admin`.
   ```routeros
   /user set admin password="<SET_UNIQUE_SECRET_PRIVATELY>"
   ```
3. **IPv6 > Settings**: Установите галочку `Disable IPv6`.
   ```routeros
   /ipv6 settings set disable-ipv6=yes
   ```

### Шаг 2: Настройка WAN и Клонирование MAC
Это критически важный шаг для работы в сети Дом.ру. 

1. **Клонирование MAC**:
   ```routeros
   /interface ethernet set ether1 mac-address=C4:AD:34:87:6B:7A
   ```
2. **IP Провайдера**:
   ```routeros
   /ip address add address=10.12.20.168/22 interface=ether1
   ```
3. **Шлюз**:
   ```routeros
   /ip route add gateway=10.12.20.1
   ```
4. **DNS**:
   ```routeros
   /ip dns set servers=192.168.248.21,192.168.251.21 allow-remote-requests=yes
   ```

### Шаг 3: Локальная сеть (LAN)
Проверка и настройка базового моста (обычно в дефолте, но полезно проверить):
```routeros
/ip address add address=192.168.88.1/24 interface=bridge
/ip dhcp-server network add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=192.168.88.1
```

### Шаг 4: Wi-Fi 6 (Временный SSID)
На hAP ax3 используется новый драйвер. Команды для быстрой настройки:
```routeros
# Создаем профиль безопасности
/interface wifi security add name=sec_setup authentication-types=wpa2-psk,wpa3-psk passphrase="<SET_UNIQUE_SECRET_PRIVATELY>"

# Настраиваем временный SSID на обоих радиомодулях (2.4 и 5 ГГц)
/interface wifi set wifi1 ssid="AX3-Setup" security=sec_setup disabled=no
/interface wifi set wifi2 ssid="AX3-Setup" security=sec_setup disabled=no
```

---

## Часть 2: Переключение (THE SWITCH)
*На этом этапе вы заменяете старое оборудование на новое.*

### Шаг 5: Физическая замена
1. Вытащите кабель провайдера из порта `ether1` старого роутера.
2. **Выключите старый роутер из розетки**.
3. Вставьте кабель провайдера в **порт 1** (2.5G) нового hAP ax3.
4. Дождитесь 1-2 минуты. Проверьте на ноутбуке (подключившись к `AX3-Setup`), появился ли интернет.

---

## Часть 3: Финальная настройка (ONLINE)
*Роутер уже имеет доступ в интернет.*

### Шаг 5.1: Проверка связи
Перед обновлением убедитесь, что роутер успешно подключился к Дом.ру и видит интернет.
```routeros
# Проверка таблицы маршрутов (должна быть строка с флагом AS и шлюзом 10.12.20.1)
/ip route print

# Проверка пинга до внешнего мира
/tool ping google.com count=5
```

### Шаг 6: Обновление ПО (Критично)
Выполните последовательно:
```routeros
# Проверка и установка ОС
/system package update set channel=stable
/system package update install

# После перезагрузки - обновление Firmware (железа)
/system routerboard upgrade
/system reboot
```

### Шаг 7: Финальные штрихи
1. **Замена SSID** (на чистовой):
   ```routeros
   /interface wifi set [find where ssid="AX3-Setup"] ssid="Ваше_Имя_Сети"
   ```
2. **Static Leases** (Synology, DigitalRazor, SEAP):
   ```routeros
   /ip dhcp-server lease add address=192.168.88.206 mac-address=00:11:32:5D:AA:19 comment="Synology NAS"
   /ip dhcp-server lease add address=192.168.88.248 mac-address=00:D8:61:3A:23:BC comment="DigitalRazor"
   /ip dhcp-server lease add address=192.168.88.221 mac-address=80:EA:96:E7:DF:FF comment="seap"
   ```

### Шаг 8: Настройка VPN (WireGuard)
*Этот шаг обсудим более подробно позднее. Для базовой инициализации интерфейса:*
```routeros
/interface wireguard add name=wireguard1 listen-port=13231
```

### Шаг 9: Финальный бэкап

```routeros
/system backup save name=final_config
/export file=final_config_text
```

Просмотр конфигурации:

```
/export hide-sensitive
```

---
> [!TIP]
> FastTrack нельзя включать общей рекомендацией: сначала проверить действующие исключения policy routing/WG/BTH и порядок firewall. Производительность процессора не заменяет проверку совместимости правил.
