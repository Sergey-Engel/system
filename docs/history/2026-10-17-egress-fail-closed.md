---
type: checkpoint
status: completed-with-warning
created: 2026-10-17
updated: 2026-10-17
tags: [mikrotik, fethiye, fail-closed]
---

# Проверка Блокировки При Обрыве IPIP

Объем: только MacBook Air Sergey `.89.197` на Wi-Fi MikroTik. Операторский
Deco, ethernet/Wi-Fi, другие WG и профили не перенастраивались. Согласование:
«начинай» после [ограниченных проб 16 октября](2026-10-16-egress-trials.md).
Сейчас IPIP включен, MacBook возвращен в Local, 10 Remote controls выключены.

## Клиентские Результаты

| Проверка | Наблюдение | Граница доказательства |
| --- | --- | --- |
| Local до теста | `194.61.140.217` | Terminal HTTPS пользователя |
| Remote до обрыва | `5.18.141.112` | Terminal HTTPS через заранее проверенный IPv4 api.ipify.org |
| IPIP отключен | `curl: (28) Failed to connect to api.ipify.org port 443 after 8005 ms: Timeout was reached` | Тот же IP через `--resolve`, DNS исключен; адрес Фетхие не получен |
| Remote после восстановления | `5.18.141.112` | Отдельная ограниченная follow-up проверка после возврата первого watch в Local |
| Финальный Local | `194.61.140.217` | Terminal HTTPS пользователя после окончательного возврата Local |

Использовался `curl -4 --noproxy '*' --connect-timeout 8 --max-time 15
--resolve api.ipify.org:443:104.26.12.205` с обычной TLS-проверкой. Адрес выбран
по свежему TLS DNS reference и проверен положительным запросом до обрыва.
В отрицательной команде пользователь повторил URL query положительной пробы,
но destination/параметры совпадали, а curl не кэширует предыдущий HTTP-ответ.
Короткий ответ «443» получен во время Outage; полный предыдущий результат
предоставлен после автоматического Local и сохранен буквально, с provenance.

## Роутерные Свидетельства

- Отключен только `ipip-s2s-egress` Фетхие, выбранный по pinned ID/owner/endpoints.
- Все 10 Remote controls оставались включенными во время обрыва; IPv6 guards
  и DNS policy не снимались. Общий conntrack flush не применялся.
- RIB выбирал только blackhole default в `s2s_remote`, gateway не был выбран.
- LAN-pair ping через прежний WG продолжал работать, 3/3 во время Outage.
- После восстановления IPIP enabled/running; итоговый export совпал с исходным
  Local, включая неизменную static binding. Нахимова не менялась.

Предварительная проверка остановилась до любых сетевых записей: ROS 7.19.6
вернул JSON `null` для `get active` невыбранного маршрута. Исправление основано
на положительном наборе `/routing route ... where active=yes` и `contribution`,
не на приведении null к False. Добавлены refusal tests; правило записано в
[changeset](../architecture/Site_to_Site_Egress_Changeset.md).

## Восстановление И Предупреждение

Outage ограничивался 180 s, общий первый drill 900 s. Лимит сработал до
обработки позднего запроса recover. При включении IPIP LAN ping дал 2/3,
после чего exception containment вернул Local; первый watch завершился с
ненулевым кодом. Это сохраненный неуспешный gate, не «чистое» восстановление.

Позднее inner и LAN в обе стороны дали четыре серии по 10/10. Эти повторы
не устанавливают причину/устранение потери 1/3. Отдельный bounded follow-up
свежим read-back включил только Remote controls максимум на 240 s:
пользователь подтвердил восстановленный HTTPS, затем выполнен Local.
Это не автономный router failover. RouterOS scheduler/device-mode не менялись.

## Операционное Завершение

Current runtime/BTH/monitoring/pilot contracts PASS; host S2S и старый protected
snapshot неизменны, re-sign/publish/restart не требовались. Console namespace:
3 routes ready, HTTP controls доступны, observed degradation=False. Unit и
tmpfiles совпали с verified pre-change archive. Prometheus S2S mappings и оба
Grafana persisted resources проверены; authenticated UI render не проверялся.
Каталог, inventory и все 67 profiles неизменны, новые controller/lock paths
не нужны. WG метрики не подменяют клиентскую HTTPS-проверку.

Private evidence: `.local/backups/site-to-site/20261017T081437Z-fail-closed/`.
Точные фазы, RIB election, loss, команды, полные exports, контрольные суммы
и окончательные backup stamps хранятся там и в `completion.json`.
Два свежих валидных post-final-Local collector cycles подтверждены.
Финальные post-backups:

- TimeWeb `2026-10-17T083751Z_current-config`, VERIFIED; 386 host files,
  61 обязательный файл прошел offline restore verification.
- Fornex `2026-10-17T083920Z_current-config`, VERIFIED.
- Cenuta `2026-10-17T083947Z_current-config`, VERIFIED.
- Фетхие `20261017T084141Z-post-egress`, VERIFIED_TRANSFER; current
  синхронизирован, initial неизменен.
- Нахимова `20261017T084227Z`, VERIFIED_TRANSFER; current синхронизирован.

Завершенный receipt: `CONTROLLED_IPIP_OUTAGE_ACCEPTED_LOCAL_WITH_PACKET_LOSS_WARNING`.
Принят только ограниченный IPv4/HTTPS цикл с отдельной recovery-пробой;
неуспешный первый recovery gate 2/3 сохранен и не переобозначен как PASS.
VERIFIED_TRANSFER подтверждает совпадение двух скачанных encrypted binary
copies и export parity, не фактическую загрузку backup в роутер.
Live restore/reboot не выполнялись.

Локальные проверки: 371 tests PASS, включая 50 egress tests.
Не приняты: постоянный Remote, полный отказ WAN/TimeWeb, IPv6-negative test,
обратный egress, прикладная нагрузка/SLA, автономный резерв и reboot/restore.
Шаг 8 [плана](../tasks/PLAN-fethiye-site-to-site.md) остается In Progress.
