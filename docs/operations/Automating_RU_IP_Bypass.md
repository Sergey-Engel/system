

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.
# Загрузка и обновление списка IP-адресов России (RU_Networks)

> [!warning] Историческая инструкция, сверка 2026-09-13
> Ни ручной импорт, ни scheduler ниже не были повторно применены/проверены этим ревью. Актуальная архитектура: [VPN_HLD](<../architecture/overview.md>), роутер: [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>). RU-list MikroTik и native nft `ru_networks_v4` на TimeWeb являются разными наборами. Не считать обновление одного обновлением другого. Перед заменой списков нужен свежий backup, проверка источника/содержимого и атомарный адресный change-план; не очищать действующий список до готовности замены.

Поскольку для корректной работы Split Tunneling требуется загрузить в роутер более 11 тысяч подсетей РФ, добавление их "вручную" невозможно. Ниже описаны два метода получения базы: автоматический (идеальный) и ручной через компьютер (гарантированно работающий).

## Метод 1: Ручная генерация через компьютер (Текущий рабочий вариант)

### Почему мы используем этот метод?
При попытке настроить автоматическое скачивание мы столкнулись с двумя препятствиями:
1. **Device Mode**: В новых прошивках RouterOS 7 утилита `/tool fetch` заблокирована корпоративной политикой безопасности. Для её разблокировки требуется аппаратное подтверждение (выдергивание питания или нажатие Reset).
2. **Блокировки GitHub**: Российские провайдеры часто блокируют или искажают трафик домена `raw.githubusercontent.com`, из-за чего роутер не может скачать базу.

Поэтому самый надежный способ — сгенерировать скрипт прямо на вашем компьютере с помощью PowerShell, обратившись к официальной базе RIPE, и "скормить" его роутеру.

### Шаг 1: Генерация базы на ПК (PowerShell)
1. Откройте **PowerShell** на вашем компьютере (поиск -> PowerShell).
2. Выполните команду, которая заберет актуальную базу и создаст файл `russia.rsc` в вашей папке Mikrotik:

```powershell
$json = Invoke-RestMethod -Uri "https://stat.ripe.net/data/country-resource-list/data.json?resource=ru"; $ips = $json.data.resources.ipv4; $outFile = "E:\Dropbox\System\Mikrotik\russia.rsc"; $sb = New-Object -TypeName "System.Text.StringBuilder"; $null = $sb.AppendLine("/ip firewall address-list"); foreach ($ip in $ips) { $null = $sb.AppendLine("add list=RU_Networks address=$ip") }; Set-Content -Path $outFile -Value $sb.ToString()
```

### Шаг 2: Загрузка в MikroTik
1. Откройте **WinBox**.
2. В левом меню нажмите **Files**.
3. Перетащите сгенерированный файл `russia.rsc` (из папки `E:\Dropbox\System\Mikrotik`) мышкой прямо в окно WinBox.
4. Откройте **New Terminal** и введите команду:
```routeros
/import file-name="russia.rsc"
```
5. Проверьте результат (должно быть около 11 000+ адресов):
```routeros
/ip firewall address-list print count-only where list=RU_Networks
```

*(Эту процедуру достаточно повторять раз в полгода, списки IP государств меняются крайне медленно).*

---

## Метод 2: Автоматический скрипт (Требует настройки Device-Mode)

Если в будущем вы захотите полностью автоматизировать процесс (при условии, что `raw.githubusercontent.com` начнет открываться, а защита `device-mode` будет снята), вы можете использовать этот системный скрипт.

### 1. Скрипт загрузки базы:
```routeros
/system script
add name="Update_RU_IPs" policy=read,write,policy,test source="\
    \n:log info \"Starting RU IP update...\"\
    \n/tool fetch url=\"https://raw.githubusercontent.com/Ghostolo/mikrotik-russia-list/master/russia.rsc\" mode=https dst-path=\"ru_ips.rsc\"\
    \n:delay 5s\
    \n:if ([:len [/file find name=\"ru_ips.rsc\"]] > 0) do={\
    \n    /ip firewall address-list remove [find list=\"RU_Networks\"]\
    \n    /import file-name=\"ru_ips.rsc\"\
    \n    /file remove \"ru_ips.rsc\"\
    \n    :log info \"RU IP list successfully updated!\"\
    \n} else={\
    \n    :log error \"Failed to download RU IP list.\"\
    \n}"
```

### 2. Настройка расписания в Планировщике (раз в неделю):
```routeros
/system scheduler
add name="Schedule_RU_IP_Update" interval=7d start-time=04:00:00 on-event="Update_RU_IPs" policy=read,write,policy,test
```
