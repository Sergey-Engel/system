---
type: implementation-log
status: fornex-peer-applied
created: 2026-09-12
updated: 2026-09-12
tags:
  - timeweb
  - fornex
  - reality
parent: "[TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>)"
---

## Результат

По согласованию пользователя выполнен шаг 4: **только на Fornex** в действующий
`wg-exit/wg0` добавлен новый peer `10.20.0.3/32` с отдельным PSK и source guards.
Старый peer не изменен. TimeWeb, Cenuta, MikroTik, Amnezia и мониторинг не менялись.
Xray не устанавливался. Новых Python-пакетов нет; локальные скрипты исполнялись
через `python3 -B`, серверные операции через Bash/SSH.

## Предварительная проверка

12 сентября 2026, 17:13:23 UTC: Fornex доступен по SSH. RAM available 1406 MiB,
на диске около 11 GiB свободно. Все семь контейнеров работают две недели.
`wg-exit` PID 2481, StartedAt `2026-08-26T07:25:48.81006629Z`.
Старый peer имеет свежий handshake; новый адрес отсутствовал.

Свежий configuration backup скачан и проверен:
`.local/backups/fornex/2026-09-12T1720Z_pre-reality/backup.tar.gz`.
Размер 233044 байта; SHA-256
`aad5f8a9b8285a364539fd9a25912af7746b3b0444e540dac266919bd24dedcb`.
Проверены 181 файл bundle, 89 host files и конфиги шести Amnezia-контейнеров.
Capture errors: 0. Это не образ диска и не проверка восстановления целой VM.

## Точные изменения

| Объект | Изменение |
| --- | --- |
| `/opt/wg/config/wg_confs/wg0.conf` | Один PreUp и новый блок Peer с AllowedIPs 10.20.0.3/32 |
| `/opt/wg/config/reality-f3/` | guard.sh, filter.restore, expected.rules, peer.psk; закрытые файлы |
| `wg-exit/wg0` runtime | Один новый peer; listen UDP/51821 не изменен |
| filter INPUT | DROP только source 10.20.0.3/32, comment reality-f3 |
| filter FORWARD | Перед прежним ACCEPT добавлен jump только wg0/source 10.20.0.3/32 в REALITY_F3 |
| REALITY_F3 | DROP частных/специальных IPv4 и IP трех VPS; ACCEPT остального только через eth0; завершающий DROP |
| NAT, маршруты, policy rules | Не менялись |

PreUp выполняет `/bin/bash /config/reality-f3/guard.sh` до поднятия WG.
Это persistent hook, но **перезапуск/recreate не тестировался**, чтобы не прерывать
старый сервис. При расхождении существующей owned chain helper откажет, а не очистит ее.
Если hook отсутствует или сломан, следующий запуск всего wg0 может завершиться ошибкой;
эти файлы нельзя удалять отдельно от строки PreUp. Автогенерация конфигурации
при изменении параметров linuxserver image не проверялась.

## Проверки и журнал

1. Bash syntax и `iptables-restore --test --noflush` внутри контейнера: успешно.
2. Первый apply остановился до мутаций: `grep -q` вызвал SIGPIPE у Docker CLI
   под `pipefail`. Проверка исправлена на полное чтение вывода; следующая попытка успешна.
3. После apply: 8/8 сравнений, включая неизменность старого peer, NAT, routes/rules,
   исходных filter rules, PID/StartedAt всех контейнеров и hash нового конфига.
4. Повторный apply: `ALREADY_APPLIED`, дубликатов не добавлено.
5. Выполнен live rollback: 9/9 сравнений, firewall и persistent config точно исходные.
6. Выполнен повторный apply: 8/8 итоговых сравнений; это текущее состояние.
7. Runtime AllowedIPs и PSK нового peer совпали с подготовленным фрагментом.
   Повторная проверка guard и разбор `wg-quick strip wg0` успешны.
8. В 17:23:22 UTC старый peer: handshake 9 секунд назад, endpoint
   `94.241.171.65:55839`, RX 153.26 MiB / TX 1.12 GiB. Это не клиентский speed test.

У нового peer handshake отсутствует ожидаемо: его сторона на TimeWeb еще не запущена.
Полный маршрут, реальные deny-probes через нового peer, клиентский regression
и reboot persistence остаются непроверенными. Зеленые статические проверки их не заменяют.

## Master и откат

Master: `Dropbox/services/transport/timeweb-reality/`.
Скрипты: `stage4_fornex.py`, `check_stage4.py`.
Точный manifest и закрытые before/after evidence: `stage4-fornex/`.
Предварительный `stage4-fornex-draft/` оставлен как неиспользованный локальный черновик.
Старый `stage3_artifact_inventory.json` исторический, не inventory текущего master.

Серверный rollback: `/var/backups/timeweb-reality/stage4-fornex/control.sh rollback`.
Он удаляет только нового peer, его jump rules, собственную цепочку REALITY_F3 и
owned hook files; возвращает файл только при ожидаемом hash. Общего route/rule/filter
flush нет. При постороннем config drift откат останавливается для ручного разбора.
Не выполнять откат после начала использования нового peer без оценки влияния.

Исходный hash wg0.conf:
`01fe3b6e4b13bb2416d40b45541b650b5ee688d326895e558996e5a810b45cab`.
Текущий:
`98348faeaa8624a7075de4b71d2994c15db9648327333fae1fca0c95bf5868d9`.

## Следующий этап

Отдельно согласовать шаг TimeWeb по [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<../architecture/TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>):
свежий preflight, точная установка изолированного Xray и его ограничений,
проверка нового Fornex egress/fail-closed. Публичный listener и импорт Amnezia
не считать выполненными; BTH и Cenuta остаются последующими профилями.
