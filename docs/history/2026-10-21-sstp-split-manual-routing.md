# Нахимова - TimeWeb: Ручные SSTP-Cenuta/Fornex

Дата: 21 октября 2026. Разрешение пользователя: только Cenuta/Fornex;
BTH и управление оставить по WireGuard, самостоятельно проверить и обеспечить
откат, без автоматического переключения. Работа поверх HEAD821925861c1a0370ddc70ad3bf69f1805c4445fe;
это отчёт о live установке, не утверждение о новом commit/push.

## Установлено

- Device routing4.0.0: Standard, WG-Cenuta-RU, WG-Fornex-RU,
  SSTP-Cenuta, SSTP-Fornex, прежний Direct via Fethiye. Старые cenuta/fornex IDs
  и CENUTA_Devices/VPN_Devices сохранены. Новые SSTP списки взаимоисключающие.
- На Нахимова только постоянные DHCP reservations, включая offline;
  имена exact-MAC из справочника. На Фетхие только Wi-Fi MikroTik и Standard/Direct.
- Явный Apply; перед назначением SSTP новая HTTPS проверка выбранного выхода.
  Undo возвращает прежний режим, исходные записи/комментарии, включая disabled.
  Неизвестный результат сохраняет pending, без слепого повтора и фонового отката.
- SSTP split2.0.0 поверх транспорта1.1.1 на91.222.238.208:443/TCP. Один PPP,
  два source-класса; это не WireGuard-over-SSTP. Нет новых client profiles/keys.
  Подробная [топология и эксплуатация](../operations/Nakhimova_TimeWeb_SSTP_Split.md).

Контейнер wg-relay с прежними ID/image/start не пересоздавался и не
перезапускался; Xray и старые WireGuard службы не перезапускались.
Корневые routes/rules/firewall хоста не менялись. Namespace wg-relay расширен
только connector, /32 return routes, source selector218 и собственным nft guard.
WG peers, keys, configs, defaults tables100/200/300 сохранены. Полный BTH RPDB
contract расширен ровно этим additive selector, monitoring manifest/recovery
policy приняты отдельно после exact outside-scope comparison.

Сохранены исходные назначения всех устройств, включая Direct192.168.88.28.
Отключённый Synology192.168.88.206 временно использовался для приёмки
Apply/Undo; итоговый режим Standard. Рабочие клиенты не переключались.

## Приёмка

| Проверка | Результат |
| --- | --- |
| Автотесты | 670 passed, 38.39s; все36 переходов, CSRF/revision/readiness/pending/Undo, browser regression |
| HTTPS из namespace через Cenuta | 89.252.153.129, проверен TLS/фиксированный resolver и отдельный source |
| HTTPS из namespace через Fornex | 103.75.126.143, отдельный source |
| RouterOS через каждый SSTP класс | DF1200 ping3/3; это маршрутизируемые IP-пробы, не браузер клиента |
| Отказ каждого выхода | Временный source-only drop попал в ожидаемый counter, запрос не вернул IP; правило удалено, положительная проба повторена |
| Restart connector | Только новый service; normalized policy прежняя, identity wg-relay прежняя; проверенные bindings перепривязаны на новый ifindex |
| Обрыв PPP | Только sstp-timeweb выключен/включён под Safe Mode; BTH/WG management доступен, оба blackhole active |
| Восстановление PPP | Две alias routes восстановлены ip-up hook без ручного repair, оба routed ping3/3; persistent router export точен |
| Live Apply/Undo | Offline Synology: SSTP-Cenuta -> Undo -> SSTP-Fornex -> Undo; весь начальный mode map восстановлен |
| Панель | Реальный HTML/API, desktop1440x1050 и mobile390x844, шесть/два режима, без POST, JS errors и горизонтального overflow |

Полная клиентская приёмка с приложениями/браузером устройства и новый reboot
всей split-топологии не выполнялись. Автозапуск units установлен; restart
connector и reconnect PPP не подменяют host reboot. Transport-only reboot/soak
20 октября остаются [отдельным доказательством](2026-10-20-timeweb-maintenance-sstp-newip.md).
RU/local/BitTorrent исключения намеренно остаются прежними, не full-tunnel.
IPv6 и полный DNS leak audit не заявляются.

## Проверки Старых Каналов

Исходная утренняя runtime проверка не прошла fleet_ready; отдельный bounded
read-only повтор подтвердил3/3. Первый отрицательный nft тест не применился
из-за неэкранированного comment; исправленный тест выполнил оба drop/recovery.
Три ранних RouterOS попытки отменены Safe Mode с exact export rollback:
ошибки синтаксиса bare flags fib/do-not-fragment. Исправлены и покрыты тестом.
Ни один ошибочный прогон не выдан за успешный.

CPU остаётся ограничением TimeWeb: pressure около99%, load около8-11,
memory pressure0 в исходном окне; это не исправлено данным changeset.
Итоговые BTH/monitoring/runtime checks прошли; fleet внутри mount namespace
работающей консоли3/3 ready, HTTP/state200. Оба upstream получили два свежих
collector cycles1792561569.8926888 ->1792561688.6970963 с fresh=1 и всеми
probe_valid=1. Prometheus содержит22 device activities, Grafana database=ok;
семь persisted dashboards проверены read-only, не authenticated screenshot.
Существующие WG/uplink метрики не выдаются за SSTP telemetry.

## Копии И Приватные Masters

Полные архивы находятся только в закрытом .local/backups, не в Git.
В canonical private store записаны новые masters, пароль router backup,
metadata/hash и evidence; полные архивы дополнительно не дублируются внутри JSON,
чтобы избежать рекурсивного роста. Локальный полный backup включает canonical
store, профили/ключи/masters и source tree; отчёт в .local/backups/local/.

Локальный run2026-10-21T055414920545Z_current-config: VERIFIED,
1011 source files,1012 temporary restores,448521248 included bytes,
67 профилей и свежий read-only RouterOS export. Это не remote live restore;
после архива изменены только финальные строки статуса/доказательств в документах.

| Копия | Путь относительно .local/backups | Проверка |
| --- | --- | --- |
| TimeWeb до изменения | timeweb/2026-10-21T045727Z_current-config/backup.tar.gz | VERIFIED; SHA256 0b80ae4f306b460a069b156667c9f39338e1b0033607fba9b75bf94e6bedb019 |
| Нахимова до изменения | nakhimova/20261021T045728Z/router.backup | VERIFIED_TRANSFER; SHA256 c10a08f4174656faf9f802f2f7e42ddcd2646cc71319fa3ecc771afe3983a0dd |
| TimeWeb после изменения | timeweb/2026-10-21T054811Z_current-config/backup.tar.gz | VERIFIED; 448 host files,122 temporary file restores; SHA256 b35efba647495303cc226e7b45413d61b791ca0806e3c1474190b4d56e19566f |
| Нахимова после изменения | nakhimova/20261021T054812Z/router.backup | VERIFIED_TRANSFER; SHA256 80d8728e0863755414db52fd7e08017d9fe871e63e32036e08d26ddc2a4456fd |

Post export Нахимова SHA256 f1530561629d0982dc0d9f7ad44d2eb88bacfe81cd8b381749391f291dcab262.
Пароль backup хранится в canonical store record backup:nakhimova:20261021T054812Z,
не в этом документе. Binary backup - зашифрованная конфигурационная копия
RouterOS, не образ диска. Live restore drill не выполнялся.

Из verified TimeWeb archive обновлены37 reviewed masters;39 обязательных
файлов прежних VPN вне scope побайтно совпали с pre-backup. Остальные SSTP
артефакты сверены с pre-master либо остались неизменными. Неизвестный локальный
drift запрещает синхронизацию. Новый backup verifier требует split sources,
guards, hook, units/dropin и проверяет hash coverage manifest.

Private evidence root: .local/backups/sstp-split/20261021T045726Z-preflight/.
Основные receipts: router-deploy-20261021T052318Z,
qualification-20261021T052759Z, device-test-20261021T053029Z,
reconnect-20261021T054511Z, final-20261021T054621Z, checkpoint.json.
Private helpers сохранены для аудита, не являются универсальными mutators.
Не переигрывать одноразовые deployment scripts при восстановлении.

## Откат

Для устройства: явный Undo прежнего подтверждённого режима либо Standard,
с той же MAC/IP/lease привязкой и проверкой readiness. Обновление статуса
не меняет сохранённый выбор. Сбой одного SSTP выхода не блокирует второй
при его независимой успешной проверке. Никакого автоматического выбора WG.

Для удаления всей новой инфраструктуры требуется отдельный reviewed changeset:
сначала снять SSTP assignments, затем удалить только новые router objects и
connector, вернуть сохранённые BTH/monitoring/recovery bindings и masters.
Нельзя восстанавливать весь роутер/пересоздавать контейнер ради смены одного
устройства. [Эксплуатационная процедура](../operations/Nakhimova_TimeWeb_SSTP_Split.md).
