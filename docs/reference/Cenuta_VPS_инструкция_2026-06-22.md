---
type: report
topic: mikrotik
status: draft
created: 2026-06-22
tags:
  - mikrotik
  - vpn
  - vps
  - cenuta
source:
  - "[Турецкие хостинг провайдеры 2026-июнь](<Турецкие хостинг провайдеры 2026-июнь.md>)"
---

## Резюме

> [!summary] Практический вывод
> Для VPN/MikroTik-задачи у Cenuta лучше начинать не с самого общего `VPS Hosting`, а с `Cloud VDS / Cloud Server`, потому что публичная страница прямо указывает KVM, CloudStack/Ceph, Custom ISO и BGP-сценарии. Минимальный разумный вариант - **Cenuta Cloud II**: 1 CPU, 2 GB RAM, 50 GB NVMe, 2 TB traffic, Турция, Ubuntu 24.04 или Debian 11.

Вывод из [исходного обзора](<Турецкие хостинг провайдеры 2026-июнь.md>) в целом подтверждается: Cenuta остается сильным вариантом по цене. Но для рабочего VPN-хоста важно не только `113,35 TRY/мес.`, а полный операционный контекст:

- цены на сайте указаны **без 20% KDV**;
- серверные продукты у Cenuta в основном **unmanaged**: базовый support бесплатный, но администрирование ОС - ваша зона ответственности;
- для Cloud/Dedicated/Co-location Cenuta не берет на себя обычное резервное копирование данных, поэтому нужны свои backup/snapshot-процедуры;
- оплата турецкой картой выглядит нормальным основным сценарием: Cenuta использует карточную оплату и автоплатежи через Iyzico, с хранением карты на стороне Iyzico;
- банковский перевод в TRY тоже есть, но для первого тестового месяца проще использовать карту.

## Что покупать

### Рекомендованный стартовый вариант

Покупать: **Cloud II** на странице [Cloud (Bulut) Server](https://www.cenuta.com/cloud-bulut-sunucu).

Публично подтвержденная конфигурация:

- CPU: 1 Core / Xeon Gold.
- RAM: 2 GB.
- Disk: 50 GB NVMe.
- Traffic: в конфигураторе Cloud II видно 2 TB traffic; на FAQ Cloud указано, что cloud-серверы имеют 1 Gbps, а после 8 TB применяется 100 Mbit limit.
- Snapshots: на карточке услуги заявлены 2 бесплатных snapshot.
- Firewall: заявлена поддержка firewall.
- OS: на странице заявлены Windows / Linux / BSD / Custom ISO, но в публичном конфигураторе без логина реально видел selectable Linux-варианты, включая Ubuntu 24.04, Debian 11, AlmaLinux 9 и CentOS 7; Windows/Fedora часть была disabled как "coming soon/beta".
- Location: в публичном конфигураторе selectable только **Türkiye**; US/DE/UK/SG/KR были marked as soon/coming.

### Почему Cloud II, а не VPS II

Для обычного сайта оба варианта близки, но для VPN/MikroTik-сценария Cloud II лучше как стартовая ставка:

- на Cloud-странице прямо указано KVM и CloudStack/Ceph;
- Custom ISO и BGP описаны именно в Cloud FAQ, включая примеры MikroTik/VyOS/Bird;
- KVM снижает риск проблем с WireGuard, TUN/TAP, kernel modules и нестандартными сетевыми сценариями.

Если задача только простая Linux WireGuard-нода, берите **Ubuntu 24.04 x64**. Если цель - именно **MikroTik CHR**, сначала откройте ticket и письменно уточните, доступна ли загрузка/подключение RouterOS CHR ISO для конкретного тарифа Cloud II.

Турецкий текст для ticket:

```text
Merhaba,

Cloud II hizmeti satın almayı planlıyorum. MikroTik RouterOS CHR veya özel ISO kullanımı mümkün müdür?
Cloud II paketinde Custom ISO yükleme/bağlama ve KVM konsol erişimi aktif mi?
Ayrıca WireGuard VPN kullanımı ve UDP port yönlendirmesi/firewall kuralı konusunda bir kısıtlama var mı?

Teşekkürler.
```

Русский смысл: "Планирую купить Cloud II. Можно ли использовать MikroTik RouterOS CHR или custom ISO? Доступны ли Custom ISO и KVM console? Есть ли ограничения на WireGuard VPN и UDP firewall rules?"

## Ожидаемая стоимость

Проверено 22 июня 2026 года.

Для Cloud II публичная карточка показывает **113,35 TRY/мес.** В конфигураторе выбранный пакет отображался как `Cloud II - ₺113.15`, а месячный период как `₺113.35`. Это расхождение небольшое, но финальной считать нужно сумму в checkout.

Ориентир:

- 1 месяц Cloud II: 113,35 TRY без KDV.
- С 20% KDV: примерно 136,02 TRY.
- 3 месяца: 340,05 TRY без KDV.
- 6 месяцев: 680,10 TRY без KDV.
- 12 месяцев: 1360,20 TRY без KDV.
- Weekly backup add-on: 21,24 TRY/мес. без KDV.
- Support level:
  - Basic: бесплатно.
  - Bronze: 299 TRY/мес.
  - Silver: 599 TRY/мес.
  - Platinum: 1196 TRY/мес.

Для первого теста я бы взял:

- Cloud II.
- 1 month.
- Ubuntu 24.04 x64.
- Türkiye.
- SLA: Basic.
- Weekly backup: выключить на первый тест, если сразу настроите свои snapshot/backup; включить, если сервер сразу станет рабочим узлом.

## Регистрация аккаунта

Страница регистрации: [id.cenuta.com/signup](https://id.cenuta.com/signup).

Публичная форма регистрации требует:

- `Adınız` - имя.
- `Soyadınız` - фамилия.
- `E-Posta Adresiniz` - email.
- `Şifreniz` - пароль.
- `Mobil Telefon Numaranız` - мобильный телефон; прямо указано, что нужна phone verification.
- согласие с `Hizmet Sözleşmesi` и `KVKK Aydınlatma Metni`.

Практические шаги:

1. Откройте `Üye Ol`.
2. Введите реальные имя/фамилию латиницей, как в банковском/турецком профиле.
3. Укажите email, к которому есть постоянный доступ.
4. Укажите турецкий мобильный номер, если он привязан к банковской карте и принимает 3D Secure SMS/push.
5. Создайте пароль и сохраните его в password manager.
6. Примите service agreement/KVKK.
7. Подтвердите телефон.
8. После входа заполните профиль/адресные данные.

В `Kullanım Şartları` Cenuta отдельно требует корректные профильные данные, включая name, phone, T.C. Kimlik и address, и оставляет за собой право временно или постоянно закрывать доступ/услуги при fake/invalid данных. Если у вас нет T.C. Kimlik, но есть турецкая карта, до оплаты лучше уточнить в support, какое поле использовать для иностранца: `Yabancı Kimlik No`, passport или другой вариант.

Короткий текст для support:

```text
Merhaba,

Türkiye'de banka kartım var ancak T.C. kimlik numaram yok / yabancı kimlik numarası kullanıyorum.
Cenuta hesabında fatura/profil bilgileri için hangi kimlik bilgisini girmem gerekiyor?

Teşekkürler.
```

## Покупка Cloud II

### Шаг 1. Открыть Cloud

Откройте [Cloud (Bulut) Server](https://www.cenuta.com/cloud-bulut-sunucu).

Ищите блок **Cenuta Cloud II** и кнопку `Yapılandır`.

Переводы основных кнопок:

- `Üye Ol` - зарегистрироваться.
- `Giriş Yap` - войти.
- `Sepetim` - корзина.
- `Yapılandır` - настроить конфигурацию.
- `Satın Al` - купить.
- `Öde ve Sunucuyu Oluştur` - оплатить и создать сервер.
- `Destek Bildirimi` - support ticket.
- `Faturalarım` - мои счета/invoices.
- `Kayıtlı Kartlarım` - сохраненные карты.
- `Kart Ekle` - добавить карту.

### Шаг 2. Выбрать период

В конфигураторе первый блок называется `1. Ödeme periyodu seçin`.

Для первого теста выбирайте **1 Ay**. Так вы проверите:

- проходит ли оплата турецкой картой;
- как быстро активируют сервер;
- какой фактический IP и latency;
- есть ли скрытые ограничения по VPN/UDP;
- устраивает ли support.

На 6 или 12 месяцев переходить только после рабочей проверки.

### Шаг 3. Оставить Cloud II

В блоке `2. Paketi değiştirmek ister misiniz?` Cloud II уже выбран.

Не понижайте до Cloud I: 1 GB RAM для VPN-хоста может работать, но запас минимальный. Cloud II с 2 GB RAM - более спокойный baseline.

### Шаг 4. Выбрать ОС

В блоке `3. İşletim sistemi seçin` для Linux WireGuard выбирайте:

- основной вариант: **Ubuntu 24.04 x64**;
- запасной вариант: **Debian 11 x64**;
- не брать CentOS 7 для нового сервера, потому что это устаревшая база.

Если нужна MikroTik CHR, не рассчитывайте на это без предварительного ticket. В публичном описании Cloud есть Custom ISO и упоминание MikroTik/VyOS/Bird, но в открытом конфигураторе без логина я не увидел явного selectable `Custom ISO` поля.

### Шаг 5. Выбрать локацию

В блоке `Veri merkezi bölgesi seçin` оставляйте **Türkiye**.

Это логично для вашей задачи:

- турецкий IP;
- хорошая связность для Турции;
- ожидаемо нормальная задержка до РФ/Европы по сравнению с дальними регионами;
- остальные публично видимые локации в конфигураторе были marked as "çok yakında".

### Шаг 6. Дополнительные опции

В блоке `Ek seçenekleri belirleyin` есть:

- `Haftalık Yedekleme` - weekly backup, 21,24 TRY/мес. без KDV.
- `Destek Seviyeleri` - Basic/Bronze/Silver/Platinum.

Рекомендация:

- первый тест: Basic, без weekly backup;
- рабочий VPN-хост: включить weekly backup или делать свой backup/snapshot после каждого важного изменения;
- платный SLA брать только если вы хотите, чтобы Cenuta сопровождала сервер как managed service. Для обычного WireGuard на Ubuntu это не нужно.

### Шаг 7. Оплатить и дождаться активации

Нажмите `Öde ve Sunucuyu Oluştur`.

До логина и реального checkout я не подтверждал финальную форму оплаты. Но по публичным материалам Cenuta поддерживает карту/Iyzico и автоплатежи в клиентской панели.

После оплаты ожидайте:

- письмо о создании услуги;
- IP-адрес сервера;
- root/user credentials или доступ через panel/console;
- доступ к server control panel: start/stop/reboot, console, reinstall/format, firewall, snapshot.

Если письмо не пришло за разумное время, создайте `Destek Bildirimi` и укажите invoice/order number.

## Оплата турецкой картой

Основной сценарий:

1. В checkout выбрать оплату картой.
2. Ввести данные турецкой debit/credit card.
3. Пройти 3D Secure в приложении банка или SMS.
4. Дождаться invoice/payment success.
5. После первой успешной оплаты, если сервер оставляете, включить autopay.

Перед оплатой проверьте в банковском приложении:

- e-commerce / internet alışveriş включен;
- лимит онлайн-оплаты выше суммы с KDV;
- карта поддерживает 3D Secure;
- телефон для 3D Secure доступен;
- если карта debit, на счете есть запас под KDV и возможную банковскую проверку.

### Автоплатеж

Cenuta в блоге от 7 декабря 2024 описывает новый payment/autopay flow:

1. `Müşteri Paneli`.
2. `Faturalarım`.
3. `Kayıtlı Kartlarım`.
4. `Kart Ekle`.
5. Включить automatic payment.

Важно: Cenuta пишет, что карточные данные хранятся на стороне Iyzico с Level 1 PCI DSS, а не на серверах Cenuta.

Моя рекомендация: не включать autopay до первой ручной оплаты и проверки сервера. После проверки включить autopay, чтобы не попасть на suspension из-за пропущенного invoice.

## Оплата банковским переводом

У Cenuta есть публичные TRY IBAN на странице [Ticari Bilgiler](https://www.cenuta.com/ticari-bilgiler).

Получатель: **Cenuta Telekomünikasyon Anonim Şirketi**.

Публичные счета:

- Denizbank: `TR86 0013 4000 0183 3274 7000 01`, TRY.
- Finansbank Enpara: `TR53 0011 1000 0000 0094 2662 88`, TRY.

После перевода Cenuta просит уведомить бухгалтерию по адресу `muhasebe@cenuta.com`.

Для первого платежа я бы не выбирал bank transfer, если карта работает. Перевод полезен как резервный способ, но карточная оплата быстрее и понятнее для автоматического продления.

Шаблон письма после havale/EFT:

```text
Konu: Ödeme Bildirimi - [Fatura No]

Merhaba,

[Fatura No] numaralı faturam için [tutar] TRY ödeme yaptım.
Banka: [Denizbank / Enpara / kendi bankanız]
Gönderici adı: [Ad Soyad]
İşlem tarihi: [YYYY-MM-DD]

Dekont ektedir.

Teşekkürler.
```

## Домен и "регистрация хоста"

Здесь важно развести три вещи:

- **VPS/Cloud host** - сам сервер у Cenuta.
- **Hostname сервера** - техническое имя внутри Linux, например `wg-tr-01`.
- **DNS-имя** - публичное имя, например `wg-tr.example.com`, указывающее на IP сервера.

### Если домен уже есть

Самый правильный путь:

1. Купить Cloud II у Cenuta.
2. Получить публичный IPv4.
3. У текущего DNS-провайдера создать запись:

```text
wg-tr.example.com.  A  <IPv4_сервера_Cenuta>
```

4. TTL на время настройки поставить 300 секунд.
5. Проверить:

```bash
dig +short wg-tr.example.com
ping wg-tr.example.com
```

6. В Linux на сервере задать hostname:

```bash
sudo hostnamectl set-hostname wg-tr-01
```

Для VPN это достаточно. Покупать новый домен у Cenuta необязательно.

### Если домена нет

Можно купить домен у Cenuta через [Domain](https://www.cenuta.com/domain), но я бы не покупал `.ru` у Cenuta: в таблице [Domain Fiyatları](https://www.cenuta.com/domain-fiyatlari) строка `.ru` показывает около **11,6-11,9 тыс. TRY/год**, что выглядит слишком дорого для практического использования.

Если нужен именно `.ru`, лучше оставить регистрацию у нормального `.ru`-регистратора, а в DNS просто добавить A-запись на турецкий VPS.

Что Cenuta дает для доменов:

- управление доменом через турецкую customer panel;
- free DNS zone management;
- free name server / child DNS;
- free Whois privacy для поддерживаемых доменных услуг.

## Первичная настройка после активации

Минимальный безопасный порядок для Ubuntu 24.04:

1. Получить IP и root/user credentials из панели или письма.
2. Зайти по SSH.
3. Сразу сменить пароль или добавить SSH key.
4. Обновить систему.
5. Настроить firewall: открыть только нужные порты.
6. Для WireGuard открыть выбранный UDP port, например `13231/udp` или свой порт.
7. Сделать snapshot до сложных изменений.
8. Настроить external monitoring: хотя бы uptime-check с другого провайдера.

Пример базовых команд на сервере:

```bash
sudo apt update
sudo apt upgrade -y
sudo hostnamectl set-hostname wg-tr-01
sudo ufw allow OpenSSH
sudo ufw allow 13231/udp
sudo ufw enable
```

Для production лучше не использовать root/password login. После настройки SSH key:

```bash
sudo adduser admin
sudo usermod -aG sudo admin
```

Дальше переносите WireGuard/MikroTik hub-конфигурацию отдельным планом.

## Риски и ограничения

### Оплата и продление

В service agreement указано:

- при проблемах с оплатой или card authorization Cenuta может приостановить услуги;
- через 10 дней после due date услуга может быть suspended;
- если в течение 30 дней не оплатить, услуга прекращается;
- возврат идет только на исходный payment channel.

Практический вывод: включить autopay после проверки или завести календарное напоминание за 3-5 дней до renewal.

### Возвраты

Не рассчитывайте на легкий refund для серверного продукта. В условиях встречается 15-day guarantee, но явно с исключениями для domain, SLA, server rental/hosting или отдельных категорий. Для теста поэтому берите 1 месяц, а не 12.

### Backup

В `Kullanım Şartları` Cenuta пишет, что для `Kiralık Sunucu`, `Bulut Sunucu`, `Co-Location` backup со стороны Cenuta не предоставляется, ответственность за backup на клиенте. Это не противоречит наличию snapshot в панели: snapshot удобен для rollback, но не заменяет независимый backup.

Минимум для рабочего VPN-хоста:

- snapshot перед изменениями;
- экспорт WireGuard/MikroTik config в локальное хранилище;
- хранить ключи и конфиги вне VPS;
- не держать единственную копию секретов на сервере.

### Email ports

Cenuta пишет, что для Cloud/Dedicated/Co-location email service ports по умолчанию закрыты, если IP предоставляет Cenuta; для включения нужен support ticket и принятие условий. Для VPN это не проблема, но не планируйте на этой машине SMTP без отдельного согласования.

### Контент и abuse

Запрещены phishing, spam, warez, adult, mining tools, proxy/anonymizer scripts и другие категории из `Kullanım Şartları`. Для личного VPN/WireGuard важно не превращать сервер в публичный open proxy и не давать доступ неизвестным пользователям.

### Поддержка

Cenuta заявляет 7/24 technical support. При этом server-side software issues в unmanaged server scope обычно остаются на стороне клиента; платный SLA нужен для более управляемого сопровождения.

## Контрольный чек-лист покупки

До оплаты:

- [ ] Есть доступ к турецкому телефону для SMS/push 3D Secure.
- [ ] В банковском приложении включены online payments.
- [ ] Выбран Cloud II, не Cloud I.
- [ ] Период - 1 month.
- [ ] OS - Ubuntu 24.04 x64.
- [ ] Location - Türkiye.
- [ ] SLA - Basic.
- [ ] Weekly backup осознанно включен или выключен.
- [ ] Итоговая сумма проверена с учетом 20% KDV.
- [ ] Если нужен MikroTik CHR/Custom ISO, есть письменный ответ support.

После оплаты:

- [ ] Получен IPv4.
- [ ] SSH/console доступ работает.
- [ ] Сменен пароль или добавлен SSH key.
- [ ] Открыт только нужный UDP port для VPN.
- [ ] DNS A-запись указывает на VPS IP.
- [ ] Сделан snapshot baseline.
- [ ] Renewal/autopay настроен или поставлено напоминание.

## Мой итоговый сценарий

Я бы действовал так:

1. Зарегистрировать аккаунт Cenuta с реальными данными и турецким номером.
2. Купить **Cloud II на 1 месяц**.
3. Оплатить турецкой картой через 3D Secure.
4. Поставить **Ubuntu 24.04 x64**.
5. Не покупать `.ru` у Cenuta; использовать существующий домен и A-запись.
6. Проверить latency, стабильность и UDP/WireGuard в течение 7-14 дней.
7. Если все нормально - включить autopay и weekly backup или построить свой backup.
8. Если нужен именно MikroTik CHR - не платить за long-term до письменного подтверждения Custom ISO/CHR support.

## Источники

- [Cloud (Bulut) Server - Cenuta](https://www.cenuta.com/cloud-bulut-sunucu): тарифы Cloud I-VIII, Cloud II, KVM/CloudStack/Ceph, 1 Gbps/8 TB limit, unmanaged support, BGP/IPv4/IPv6/Custom ISO.
- [VPS Hosting - Cenuta](https://www.cenuta.com/vps-hosting): похожая VPS-линейка и функции панели.
- [Cenuta ID signup](https://id.cenuta.com/signup): поля регистрации, phone verification, service agreement/KVKK consent.
- [Yeni Ödeme Sistemi ve Otomatik Ödeme - Cenuta Blog](https://www.cenuta.com/blog/cenuta-yeni-odeme-sistemi-ve-otomatik-odeme-ozelligi-yayinda/): saved cards, automatic payment, Iyzico PCI DSS.
- [Ticari Bilgiler - Cenuta](https://www.cenuta.com/ticari-bilgiler): юридические данные компании, TRY IBAN, email уведомления о переводе.
- [Domain - Cenuta](https://www.cenuta.com/domain): domain management, DNS management, child DNS, Whois privacy.
- [Domain Fiyatları - Cenuta](https://www.cenuta.com/domain-fiyatlari): наличие `.ru` и текущая высокая цена `.ru`.
- [Hizmet Sözleşmesi - Cenuta](https://www.cenuta.com/hizmet-sozlesmesi): suspension, termination, refund channel, due-date logic.
- [Kullanım Şartları - Cenuta](https://www.cenuta.com/kullanim-sartlari): profile data correctness, backup responsibility, email ports, support scope, prohibited content.
- [İletişim - Cenuta](https://www.cenuta.com/iletisim): support ticket, phone numbers, address.
