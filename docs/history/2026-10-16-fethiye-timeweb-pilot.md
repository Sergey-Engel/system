---
type: operational-checkpoint
status: accepted-icmp-only
created: 2026-10-16
updated: 2026-10-16
tags: [fethiye, mikrotik, wireguard, timeweb]
---

# Фетхие - TimeWeb: Первое Служебное Плечо

## Результат

Согласованный [пилот](../architecture/Fethiye_TimeWeb_Pilot_Changeset.md)
создан и технически проверен. Это не завершение всей межплощадочной сети.
Нахимова, Deco и прежние VPN не перенастраивались. MacBook HTTPS после
изменения подтвержден пользователем; затем он подтвердил открытие страницы
WebFig `http://192.168.89.1`. Служебный ICMP-only шаг 6 принят. Это не
повторная проверка авторизации и не приемка полного клиентского egress.

```text
MacBook Air -> Wi-Fi MikroTik -> ether1 -> Deco -> местный интернет
                    |
              wg-s2s-tw 10.60.60.3/29
                    | исходящий WG, keepalive 25, MTU 1420
                    v
       94.241.171.65:51860/UDP -> host wg-s2s 10.60.60.1/29
```

Только ICMP между `.1` и `.3`. AllowedIPs `.1/32` на Фетхие и `.3/32` на hub.
LAN/default routes и NAT не добавлялись. Переключение Internet-выхода,
второе плечо Нахимова и доступ между LAN не включены.

## Применение И Ошибки

- Расширенная проверка адресов: TimeWeb 2 namespaces, Fornex 8, Cenuta 1,
  плюс 47 прежних приватных WG/AWG конфигов. Конфликтов выбранного диапазона,
  имени интерфейса и порта не найдено; default selectors не считаются allocation.
- Fresh pre-backups всех VPS schema 3 VERIFIED; Фетхие pre-pilot VERIFIED_TRANSFER.
- Reviewed nft policy проверена в отдельном временном namespace, без
  изменения общего ruleset. На TimeWeb сначала guard/unit, затем WG.
- На Фетхие initial guard запрещал ping из-за порядка собственных правил.
  Попытки move вернули `cannot move builtin`; live list показал собственные
  записи перед dynamic FastTrack dummy. Исправлено отдельной input chain,
  без отключения FastTrack, reboot или изменения прежних firewall entries.
- Текущий RouterOS scope: interface, peer, address и пять firewall rules.
  Передача в/из WG закрыта двумя forward drops до прежних accepts/FastTrack.
  Input jump ведет в собственные ICMP allow и завершающий drop.
- Writer для будущего воспроизведения не использует числовой anchor 0;
  обязательна уникальная static management rule. Примененные one-shot mutators
  retired после фиксации результата; повторный запуск не регенерирует ключи.
- `fetch` и bandwidth-test запрещены device-mode home; эти ограничения
  не ослаблялись. Telnet в noninteractive SSH не выполнил сетевой тест;
  он не зачтен. Настоящий отрицательный TCP-тест выполнен через ssh-exec
  без передачи credentials и без принятия нового server trust.
- Один monitoring check отказал без вывода из-за nonblocking collector lock;
  повторный check прошел. Manifest не переподписывался для обхода ошибки.

## Проверки

| Проверка | Результат / область доказательства |
| --- | --- |
| Strict management SSH / serial | Фетхие `HM20B6QXS8H`, прежние pinned SSH identities |
| WG identities/runtime/master | Отдельные ключи, один exact peer, AllowedIPs/MTU/port и startup сверены |
| Туннельные пакеты | Ping обе стороны 3/3; 1400-byte пакеты прошли, Linux DF probe прошел |
| TCP 22 | Попытки обе стороны не проходят; увеличились собственные nft input/output drop counters |
| Реальный host transit | Два пакета из временного test namespace к `.3` заблокированы host forward guard; counter 0 -> 2 |
| Cleanup теста | Временный veth и namespace удалены; root default route не менялся |
| Router Internet | Ping 1.1.1.1 3/3; прежний default через Deco сохранен |
| MacBook | Пользователь подтвердил внешний HTTPS и открытие страницы WebFig `http://192.168.89.1`; повторная авторизация не проверялась |
| Неизменность старых VPN | Protected JSON snapshots до/после совпали; все 65 прежних profile SHA-256 сохранены |
| Recovery contracts | Runtime, BTH, monitoring и собственный pilot guard PASS |
| Console service context | Read-only fleet status внутри mount namespace консоли 3/3 ready; HTTP cards/controls PASS |
| Два collector cycles | Обоим upstream fresh=1, четыре HTTPS valid=1; 10:00:10.450 и 10:02:08.821 UTC |
| Prometheus | Новый source `timeweb-s2s`, peer present/fresh/rate-valid=1; существующие upstream valid |
| Grafana | В реально импортированных resources `timeweb-uplink-pilot` и `wg-device-live` есть новое устройство; это не проверка авторизованного UI render |

`timeweb-s2s` читает host namespace, а не wg-relay. 66 profiles / 22 devices;
новый профиль находится в `Infrastructure/mikrotik-fethiye`, не под MacBook.
Source, tests, inventory и dashboard mappings обновлены вместе.

Пилот не является переключаемым FLEX device: новые controller locks/controls
ему не нужны. Console sandbox/tmpfiles и fleet allowlist не расширялись.
Старый protected snapshot/bindings не изменились: обновлять BTH/monitoring
manifest или публиковать новую старую runtime generation не требовалось.
Новый startup guarded своим manifest/unit и включенным wg-quick unit.
Полное автоматическое восстановление/резервирование относится к шагу 9.

Финальные локальные проверки: 268 tests PASS; repository validation PASS
(397 public files, 66 profiles, 22 devices); private store VERIFIED
(608 files, 288 records); `git diff --check` PASS. Dry-run staging исключает
`.local`; commit/push не выполнялись.

## Хранение

Все пути ниже относительно корня System checkout. Секретов в этом отчете нет.

| Объект | Размещение / проверка |
| --- | --- |
| Immutable initial Фетхие | `.local/backups/fethiye/20261016T054841Z-initial/`, исходные hashes сохранены |
| Fresh pre Фетхие | `.local/backups/fethiye/20261016T093516Z-pre-s2s-pilot/` |
| Pre VPS | TimeWeb `2026-10-16T091749Z_current-config`; Fornex `2026-10-16T091900Z_current-config`; Cenuta `2026-10-16T091926Z_current-config`; VERIFIED |
| Post TimeWeb | `.local/backups/timeweb/2026-10-16T101524Z_current-config/`, VERIFIED, 386 host files / 61 required offline restore files |
| Post Фетхие | `.local/backups/fethiye/20261016T102035Z-post-s2s-pilot/`, VERIFIED_TRANSFER; current обновлен, initial неизменен |
| Пилотный changeset/evidence | `.local/backups/site-to-site/20261016T093901Z-prepared/`, bundle/manifest, before/after, counters, cycles, snapshots writers/rollback |
| Server masters | `.local/config/hosts/timeweb/current/host/etc/wireguard/` и exact systemd files |
| Portable secrets | `.local/secrets.json`: новый профиль/ключи, masters, evidence; dirs 700 / files 600 |

TimeWeb post-archive SHA-256:
`4da362ba454e04bbc1c86ddac75af62a4a8f87a35f8a3f484ad88ce22d013c26`.
Backup gate требует все шесть pilot files при появлении любого из них,
runtime showconf до/после и успешный guard check. Endpoint динамичен и
нормализован при сравнении; private output хранится только в закрытом архиве.

## Ограничения И Следующий Шаг

- Доступность страницы WebFig на MacBook подтверждена; повторная авторизация не проверялась.
- Публичный egress IP MacBook не измерен; подтверждены прежний router default
  и пользовательский HTTPS, не состояние иных клиентских VPN-приложений.
- Реальный reboot, restore и rollback drill не выполнялись. Откат подготовлен
  с ownership/hash checks; неизвестный drift требует отказа, не общего restore.
- Grafana API без авторизации вернул 401. Доступ/пароль не сбрасывались;
  данные проверены в provisioned runtime resources read-only и в Prometheus.
- Новое плечо Нахимова требует своего changeset; до него LAN transit закрыт.

[Текущий план](../tasks/PLAN-fethiye-site-to-site.md),
[паспорт Фетхие](../hosts/fethiye/network-passport.md),
[реестр конфигурации](../registry/configuration.md).

Первичные источники:
[RouterOS WireGuard](https://help.mikrotik.com/docs/spaces/ROS/pages/69664792/WireGuard),
[RouterOS SSH exec](https://help.mikrotik.com/docs/spaces/ROS/pages/132350014/SSH),
[wg-quick](https://man7.org/linux/man-pages/man8/wg-quick.8.html).
Похожий симптом расположения перед dummy описан пользователем на
[официальном форуме MikroTik](https://forum.mikrotik.com/t/winbox-4-is-here/178358/3405);
это сообщение о наблюдении, не подтверждение исправления в конкретном релизе.
