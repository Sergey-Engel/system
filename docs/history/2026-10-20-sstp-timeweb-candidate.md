# SSTP Нахимова - TimeWeb: испытанный, но не принятый кандидат

Дата: 20 октября 2026. Результат: **Blocked / безопасно отключён**.
Это не отчёт о готовом постоянном резерве.

Позднее в тот же день пользователь отдельно разрешил обслуживание TimeWeb.
Успешная установка нового endpoint91.222.238.208:443 описана
в [новом протоколе](2026-10-20-timeweb-maintenance-sstp-newip.md).
Неуспешный результат этой первой попытки сохранён без изменения.

## Разрешение И Объём

Пользователь разрешил самостоятельную настройку SSTP на отдельном порту,
без изменения работающих WireGuard/Xray и без автоматического переключения.
Выбор устройств и действующие пользовательские маршруты не менялись.

Подготовлен независимый SSTP/TLS1.2 TCP5444: Нахимова 10.60.65.2,
TimeWeb 10.60.65.1, MTU/MRU1400, отдельные CA/сертификат/PPP credential,
MSCHAPv2, проверка доверия и адреса сервера, AES256-GCM/PFS.
Это не mutual TLS. Исходящий client не добавляет default route.

TimeWeb: accel-ppp в отдельном network namespace; public listening socket
передаётся systemd-socket-proxyd. Нет root veth, NAT, новых root routes или
изменений root firewall. LAN transit запрещён с обоих концов; сервер доступен
только с согласованного публичного адреса Нахимова и собственного адреса VPS.
Сборка выполнена вне VPS; его пакеты/OpenSSL не обновлялись.
Исходники, pin и ограничения: [runbook](../../services/transport/sstp-timeweb/README.md).

## Что Подтверждено

- Строгие SSH host key и serial HKM0BDXYG74 через новый SSTP.
- Двусторонний ICMP, DF1400, SFTP 262144 байта в каждую сторону с точным
  совпадением. После неуспешного soak передача файла повторно прошла.
- Неверный PPP password отклонён; сервер фиксировал authentication failed.
- Недоверенный серверный сертификат отклонён: RouterOS фиксировал
  no trusted CA certificate found. Правильные credentials/PEM восстановлены.
- Три отдельных reconnect: 10.66–10.98 s до проверки полезной передачи,
  включая явно заданные 5 s ожидания после running=true.
- Публичный доступ с несогласованного адреса запрещён. Сертификат проверен
  отдельно по CA/IP. В изолированном namespace нет маршрута в LAN.
- Два свежих цикла Cenuta/Fornex: fresh=1, все HTTPS probe_valid=1,
  reason=ok, timestamps увеличились. Старый monitoring manifest не менялся.
- Подготовлен отдельный read-only status: собственные file hashes,
  unit health, PPP address/MTU/counters, срок сертификата с предупреждением 30 дней.
  Он не выдан за существующую Grafana-телеметрию SSTP.

## Что Не Принято

Строгое десятиминутное окно не прошло: сохранены 18 успешных наблюдений
до примерно 578 s; следующий ICMP64 sample получил 0/3 ответа.
Нельзя считать это успешным soak. Последующий контроль дал 20/20 через
SSTP, 20/20 обычным путём и 20/20 обратно. PPP interface/процесс сервера
не пересоздавались, uptime SSTP составлял 13:22. Поэтому подтверждён сбой
передачи в окне, но разрыв TLS/PPP и точная причина потерь не доказаны.

На TimeWeb обнаружена тяжёлая ресурсная перегрузка:

| Показатель | Наблюдение |
| --- | --- |
| CPU / RAM | 1 vCPU / 2015212 kB |
| Load average | 14.67 / 19.82 / 17.37; ранее 28.46 / 23.04 / 18.05 |
| MemAvailable / swap | 73232 kB / swap отсутствует |
| CPU pressure avg10 | 99.54% |
| containerd-shim существующего wg-relay | 8990 threads, VmRSS 982192 kB |

Идентичность shim сверена с исходным ID работающего wg-relay.
Два новых SSTP server/proxy процесса потребляли суммарно менее 4 MiB,
около 3.3 CPU seconds за наблюдаемое время, без аварийных рестартов.
Это не доказательство окончательной причины перегрузки или ICMP-сбоя.

Ошибки SSH/banner, Docker capture и fleet readiness наблюдались ещё до
deployment. Общая runtime recovery проверка и после него то отказывала на
fleet_ready, то не укладывалась в timeout; самостоятельный fleet status
показывал 3/3 ready. Встречались busy-отказы BTH/monitoring checks.
Неизвестный drift не переподписан; recovery generation не публиковалась.
Полный общий operational gate не принят.

## Финальное Состояние

Новый client, profile, восемь owned rules и только новый CA удалены с
Нахимова; fingerprint проверен. Sensitive export без служебного заголовка
совпадает с исходным. Общий config/state/routing intent восстановлен
побайтово, исходные выбранные устройства сохранены.

Пять новых служб inactive; автозапуск отключён, порт5444 закрыт,
новый namespace удалён. Новые server files/PKI сохранены как staged candidate.
Работающий Direct SSTP между площадками не изменён.

Без обращения к перегруженному Docker daemon проверены container ID/image/
PID/start, WG runtime через закреплённый namespace, все защищённые старые
файлы, Xray PID/start, root firewall/routes/rules и все 67 профилей.
Результат совпадает с исходным. Learned WG endpoints исключены только из
сравнения runtime key/policy; persistent configs проверены точно.
WG/Xray/container не перезапускались, их конфиги/ключи не менялись.

## Копии И Источники

Приватный evidence root:
.local/backups/sstp-timeweb/20261020T143015Z-preflight/.
Там сохранены исходные снимки, попытки с Safe Mode, исходы отрицательных
тестов, неуспешное окно, ресурсная диагностика и точный финальный no-touch proof.
Неуспешные backup/gate receipts и неуспешный soak не удалены и не заменены PASS.

Полная предоперационная копия TimeWeb VERIFIED:
.local/backups/timeweb/2026-10-20T143815Z_current-config/backup.tar.gz,
SHA256 5678832e31750a9d89dcc2b391aafc8f1f5fa3307e47d701923b92ca025df8cc.
Также получены свежие VERIFIED Fornex/Cenuta и pre RouterOS encrypted backup.

Staged SSTP server archive: post/timeweb-sstp/config.tar.gz внутри evidence
root, **VERIFIED**, 48 обязательных файлов проверены офлайн:
SHA256 6e4ef9c05184d5980cbc92c2ab4e7205cc1b8fd01247880a3ccd8d4a5ef86e78.
Архив включает binary/libs, private server config/PKI, units, manifest и
явно отключённое runtime состояние. Это не образ диска и не live restore drill.
Закрытый CA key остаётся только в локальном canonical private store.

Постоперационная encrypted RouterOS копия после точного отката:
.local/backups/sstp-timeweb/20261020T153307Z-post/nakhimova-pre/router.backup,
**VERIFIED_TRANSFER**, SHA256
2e4776fef35dc23ebec8140c8f4c1755d10d9e742d8b56b934741f213f1b7dde.
Password только в canonical private store; live restore не выполнялся.
Финальная проверка portable store: **VERIFIED**, 3016 файлов и 358 records;
receipt сохранён в evidence root. Локальный полный suite: **626 passed**,
включая 16 новых тестов и прежние browser regressions; NODE_PATH указывает
на bundled runtime Playwright. git diff --check прошёл.
Полный тяжёлый
Docker-based post collector не запускается повторно на перегруженном VPS;
исходное рабочее состояние подтверждено независимым read-only сравнением.

## Следующий Шаг

Нужно отдельно согласованное обслуживание TimeWeb/Docker и выяснение причины
thread/memory роста. Возможный restart существующего container/runtime не
разрешён текущей задачей. После устранения перегрузки нужен новый preflight,
fresh changeset и полная приёмка SSTP. Не включать старый кандидат вслепую,
не переключать устройства и не добавлять failover до этого.
