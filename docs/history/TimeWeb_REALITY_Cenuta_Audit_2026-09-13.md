# REALITY: аудит Cenuta перед добавлением профиля

Дата: 2026-09-13, 08:30-08:31 UTC. Только read-only команды и короткие сетевые пробы.
Основание: [Основной план](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>), шаг 8.

## Факты

- SSH ubuntu@89.252.153.129 доступен с выделенным ключом и строгой проверкой
  .local/ssh/known_hosts_cenuta. sudo -n работает.
- Uptime 1 день 18:26; load 0.17/0.04/0.01. RAM 1968 MiB, available 1642 MiB.
  Диск /: 48 GiB, свободно 44 GiB. Swap отсутствует. Failed units не выведены.
- wg-quick@wg-cenuta active/enabled. wg-cenuta: 10.40.40.1/24, MTU1420,
  UDP51840. Один текущий peer с AllowedIPs=10.40.40.2/32.
  Последний handshake на повторном чтении возрастом 2 секунды.
- Persistent config /etc/wireguard/wg-cenuta.conf, SaveConfig=false.
  SHA256 до/после аудита:
  5504135666c08cf0e0c55ac020f57104f5c0a1b9d1b30a480382e925f71478aa.
- Кандидат нового peer 10.40.40.3/32 отсутствует среди runtime/persistent peer
  AllowedIPs. Это проверка текущего WG, не резервирование адреса на сервере.
- IPv4 forwarding=1. Default route через 89.252.153.1, ens3.
- Firewall/NAT управляются native nftables, служба active/enabled.
  INPUT policy drop, разрешены established/related, ICMP, DHCP, SSH22 и UDP51840.
  FORWARD policy drop, разрешен wg-cenuta -> ens3 для source 10.40.40.0/24.
  NAT: ens3 + source 10.40.40.0/24 masquerade.
- iptables -S показывает ACCEPT, но НЕ отражает полноценную native nft политику.
  iptables -t nat предупреждает incompatible base-chains. Не делать вывод об
  отсутствии firewall/NAT по этому представлению и не дублировать NAT.
- /etc/nftables.conf содержит flush ruleset. Не загружать его целиком и не
  перезапускать nftables для адресного добавления нового peer/guard.
- С Cenuta api.ipify.org вернул 89.252.153.129; example.com HTTP200,
  TLS0.250s/total0.327s; speedtest.net HTTP200, TLS0.226s/total0.681s.
  Это короткие HTTPS-пробы, не нагрузочная приемка нового профиля.
- Из TimeWeb wg-relay через wg-up-cenuta (10.40.40.2/32) до 10.40.40.1:
  3/3 ICMP, RTT96.9-113.2ms. Это существующая WG-идентичность, не новая .3.
- TimeWeb: available RAM1452 MiB; новый Xray active, MemoryCurrent24010752,
  NRestarts=0. Ресурсов для второго userspace outbound по текущему снимку достаточно;
  CPU/RSS при одновременном трафике двух профилей еще нужно измерить.

## Предлагаемые изменения, еще не применены

1. Свежие backups Cenuta wg-cenuta.conf/nftables.conf/runtime nft и TimeWeb
   конфигурации/guard; локальная master-копия в services/transport/timeweb-reality.
   Проверенные manifest/rollback только собственных объектов.
2. Новые WG ключи/PSK для .3/32, без переиспользования старого peer .2.
3. На Cenuta сначала адресная защита нового source: запрет доступа к самому
   хосту, private/bogon и management IP трех VPS; разрешен публичный выход ens3.
   Реализация native nft, до общих разрешений. Persistent часть согласована с
   runtime и валидируется отдельно; общий flush/reload не выполняется.
4. Добавить .3/32 в файл WG и runtime адресным wg set. Без wg-quick down/up.
   Существующие peer и NAT не меняются. Перед применением повторить проверку drift.
5. На TimeWeb добавить wg-cenuta outbound, разрешение UID10001 только к
   89.252.153.129:51840/UDP и новые UUID/routing для MacBook и iPhone.
   Действующие Fornex UUID, WG ключи и SNI не меняются. Применение новой Xray
   конфигурации потребует отдельно согласованного короткого рестарта общего сервиса.
6. DNS-reserve из основного плана необходимо отдельно проверить на поддерживаемой
   версии Xray, включая холодный cache и независимость при отказе Fornex/Cenuta.
   Не выдавать текущий dns-fornex за независимый Cenuta DNS. Нельзя добавлять
   direct DNS с TimeWeb или автоматически переключать пользовательский egress.
7. Выдать два отдельных клиентских файла .local/clients, обновить реестр.
   Проверки: новый handshake, внешний IP Cenuta, HTTPS/DNS/upload/download,
   private destinations denied; затем regression Fornex и два профиля одновременно.
8. Отдельно согласовать fault test каждого нового выхода и подтвердить независимость
   второго профиля с холодным DNS cache. Общий restart/reboot не делать в этом аудите.

Итог: технических препятствий в этом снимке не обнаружено. Ничего на VPS
не установлено и не изменено. Нового peer/профиля Cenuta пока нет.
