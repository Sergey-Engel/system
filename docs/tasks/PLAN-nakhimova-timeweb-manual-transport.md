# PLAN: Ручной выбор транспорта Нахимова - TimeWeb

Дата: 2026-10-20; завершено 2026-10-21. Статус: Complete. Разрешение: пользователь поручил
добавить в действующую панель ручной выбор WireGuard/SSTP, с проверкой
и возможностью отката; автоматический failover запрещён.

| Шаг | Задача | Приоритет | Статус |
| --- | --- | --- | --- |
| 1 | Read-only discovery текущих плеч, routing и recovery contracts | P0 | Done: pinned router, три production WG-плеча и отдельный S2S |
| 2 | Зафиксировать точный scope переключения, транзакцию и rollback | P0 | Done: per-device SSTP-Cenuta/Fornex, BTH/management остаются WG |
| 3 | Controller/API/UI и отрицательные/rollback tests | P0 | Done: 670 tests, 36 transitions, explicit Undo и pending recovery |
| 4 | Свежие backups, узкий deployment, живые пробы и возврат WG | P0 | Done: egress/negative/reconnect/connector restart, offline device Apply+Undo, исходные назначения сохранены |
| 5 | Два monitoring cycles, console namespace, реестры и post backups | P0 | Done: два валидных цикла, contracts/HTTP/fleet/Grafana, host/router/local backups VERIFIED, private store VERIFIED |

## Контракт

UI: существующий селектор маршрута каждого устройства Нахимова.
Режимы: Standard, WG-Cenuta-RU, WG-Fornex-RU, SSTP-Cenuta,
SSTP-Fornex, Direct SSTP via Fethiye. Старые mode IDs cenuta/fornex
сохраняются; новые sstp_cenuta/sstp_fornex. На Фетхие изменений нет.
Показывать наблюдаемый/сохранённый режим, готовность каждого транспорта,
время проверки и результат последней операции. Выбор не выполняет запись;
нужны явные Apply и подтверждение. Refresh не меняет режим и не удаляет
сообщение об ошибке. Для возврата доступна отдельная операция Roll back.

Перед записью проверяются identities, revision, protected snapshot,
готовность целевого пути и отсутствие pending operation. Операция должна
иметь durable intent и узкий журнал. Ошибка/timeout не считаются успехом;
откат транзакции не является автоматическим failover.

## Ограничения

Нельзя менять default route площадки, назначения устройств, Direct SSTP
Фетхие, Xray identities, ключи/профили и чужие firewall/routes. Нельзя
пересоздавать контейнеры, ослаблять contracts, скрывать CPU-риск или
выдавать handshake за клиентскую приёмку. Сначала определяется полный
состав действующих Nakhimova-TimeWeb плеч: один лишь новый isolated PPP
ещё не является взаимозаменяемой заменой нескольких WireGuard каналов.
До доказанной rollback-схемы live routing не меняется.

## Приёмка

Проверить оба направления переключения и откат, полезную передачу,
негативный target readiness, stale revision, CSRF, повторный запрос,
pending-after-restart, согласованность действующих защит и панели.
Существующий выбор устройств сохраняется. Финальный режим - WireGuard,
если пользователь не назначил иной. Никакого фонового выбора транспорта.

## Discovery

Read-only проверка закреплённого HKM0BDXYG74: wg1 -> UDP51820/Fornex,
wg-cenuta -> UDP51850/Cenuta, wg-home -> UDP51830/BTH и существующий
SSH management proxy. Отдельный wg-s2s-tw -> UDP51860 обслуживает связь
с Фетхие; он не должен попадать в переключение по умолчанию.
Все endpoint сейчас 94.241.171.65. SSTP10.60.65.1/10.60.65.2 работает,
но его forward guards запрещают transit. Ни маршруты, ни фильтры,
ни runtime contracts во время discovery не изменялись.

Пользователю отправлен один вопрос о границе переключателя:
только Cenuta/Fornex (рекомендованный первый этап) либо также BTH.
До ответа live writer/deployment не запускается. Private evidence:
.local/backups/timeweb-manual-transport/20261020T182449Z-discovery/.

## Уточнение 21 Октября

Пользователь разрешил только Cenuta/Fornex и потребовал два независимых
per-device SSTP режима. BTH, управление, исходные device memberships,
WG keys/profiles, default route и Direct SSTP не переключаются.
Новые address lists взаимоисключающие со старыми; RU/local exceptions
наследуются от действующей политики. SSTP не является WG-over-SSTP:
пользовательские IP-пакеты приходят на PPP и направляются в существующий
зарубежный выход через узкий namespace connector с отдельными sources.
Новые source selectors не совпадают с выданными client identities.
Protected diff BTH RPDB/monitoring принимается только на конкретные новые
правила/линк, с копией и exact outside-scope proof. Unknown drift запрещён.
