# Тестовое разделение туннеля (Split Tunneling) для 2ip.ru

Эта инструкция описывает безопасный способ протестировать отправку определенного трафика (в нашем случае сайта `2ip.ru`) мимо VPN-туннеля `wg1`, отправляя его напрямую к провайдеру Дом.ру.

## Архитектура решения: Mangle вместо Routing Rule

В текущей конфигурации вы используете `/routing rule` (например, для Mac Mini и Apple TV). 
Проблема в том, что `routing rule` **не поддерживает списки адресов** (`address-list`). Когда мы захотим добавить 10 000 российских подсетей, мы не сможем сделать это через одно правило маршрутизации.

Поэтому для масштабируемого Split Tunneling мы плавно переходим на **маркировку трафика (Mangle)**. 

Логика работы:
1. Пакет вылетает от устройства (Mac Mini).
2. Роутер проверяет: "Летит ли пакет на локальные адреса?" -> Если да, оставляем дома.
3. Роутер проверяет: "Летит ли пакет на сайты-исключения (2ip.ru)?" -> Если да, отправляем провайдеру.
4. Всё остальное получает «печать» `WG1-Route` и улетает в VPN.

---

## 🛠 Пошаговая настройка в терминале

Для теста мы переведем в новый режим одно из ваших устройств — **Mac Mini M4 (192.168.88.35)**.

### Шаг 1: Создаем список исключений

В RouterOS можно использовать доменные имена прямо в `address-list`. Роутер сам узнает их IP-адреса и будет поддерживать их в актуальном состоянии.

```routeros
/ip firewall address-list
add list=Bypass_VPN address=2ip.ru comment="Test bypass for 2ip.ru"
add list=Bypass_VPN address=myip.ru comment="Additional test site"
```

### Шаг 2: Отключаем старое правило маршрутизации

Нам нужно выключить прежнее "жёсткое" правило для Mac Mini, чтобы оно не перебивало наши новые гибкие маркировки.

```routeros
/routing rule disable [find comment="Mac Mini M4 (Sergey)"]
```
*(Оно останется в роутере выключенным серого цвета на случай, если захотите откатиться).*

### Шаг 3: Настраиваем правила Mangle

Теперь задаем логику работы с трафиком от Mac Mini. Эти три команды должны идти именно в таком порядке.

```routeros
# 1. Оставляем доступ к локальной сети (NAS, сам Роутер) в обход VPN
/ip firewall mangle
add action=accept chain=prerouting src-address=192.168.88.35 dst-address-list=Local_Networks comment="VPN Bypass: Local Network"

# 2. Оставляем доступ к сайтам-исключениям в обход VPN
add action=accept chain=prerouting src-address=192.168.88.35 dst-address-list=Bypass_VPN comment="VPN Bypass: Sites"

# 3. Весь остальной трафик маркируем для отправки в VPN туннель
add action=mark-routing chain=prerouting src-address=192.168.88.35 new-routing-mark=WG1-Route passthrough=no comment="VPN: Route all other for Mac Mini"
```

### Шаг 4: Решение конфликта с FastTrack (Аппаратным ускорением)

FastTrack — популярная функция RouterOS, которая отправляет пакеты напрямую, минуя правила Mangle. Из-за этого первый пакет может уйти в VPN, а остальные сорваться к провайдеру, ломая загрузку сайтов. Нам нужно добавить два правила-исключения:

```routeros
# Разрешаем трафик в/из туннеля проходить в обход FastTrack
/ip firewall filter
add action=accept chain=forward out-interface=wg1 connection-state=established,related comment="Bypass FastTrack for WG (Out)" place-before=[find action=fasttrack-connection]
add action=accept chain=forward in-interface=wg1 connection-state=established,related comment="Bypass FastTrack for WG (In)" place-before=[find action=fasttrack-connection]
```

---

## 🔬 Как протестировать

1. Откройте браузер на **Mac Mini**.
2. Зайдите на сайт **[2ip.ru](https://2ip.ru)**. 
   - Вы должны увидеть ваш реальный IP от провайдера (Дом.ру, Пермь).
3. Зайдите на иностранный чекер, например **[whatismyip.com](https://www.whatismyip.com/)** или **[speedtest.net](https://www.speedtest.net/)**.
   - Вы должны увидеть IP адрес вашего VPS сервера (94.241.171.65).

Если тест успешен — значит наша архитектура работает идеально. Позже мы легко сможем добавить скрипт, который скачает 10 000 российских подсетей и одной командой добавит их в список `Bypass_VPN`.

---

### 🔙 Как откатить изменения (если что-то пошло не так)

Если нужно всё вернуть как было (через жесткое `routing rule`):
```routeros
/ip firewall mangle remove [find comment~"VPN"]
/routing rule enable [find comment="Mac Mini M4 (Sergey)"]
```
