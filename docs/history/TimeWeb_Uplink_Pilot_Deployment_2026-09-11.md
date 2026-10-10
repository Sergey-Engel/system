# Развертывание пилота TimeWeb Uplinks, 2026-09-11

## Решение и область

Пользователь согласовал серверную .venv, collector/exporter и живое отображение
в существующей Grafana Mac Mini. Это ограниченный наблюдательный пилот, не полная
production-приемка. Отдельный конфиг `pilot/config.json` включает snapshot scope;
CLI требует `--pilot` и `deployment_mode=pilot`. `config.candidate.json` сохраняет
`allow_snapshot_scope=false`. Не установлен серверный Prometheus.

## Ход работ (UTC)

- 13:09: TimeWeb доступен; MemAvailable 1466 MiB, свободный диск 18 GiB;
  существующий guard check: VALID generation=5.
- 13:13: сохранен и проверен tar backup guards/manifest/state перед установкой.
- HTTP-репозитории Ubuntu отвечали нестабильно/таймаутами. Локальный timeout
  SSH не остановил удаленный apt мгновенно; перед повтором проверены PID/dpkg.
  Первая установка пакетов завершилась позднее. Повторный bootstrap через
  временные HTTPS sources прошел, python3-venv уже был установлен.
  Системные sources не изменены, apt upgrade/autoremove не выполнялись.
- 13:19: установлены dnspython 2.8.0 в серверной .venv, отдельный код пилота,
  два systemd-сервиса. Архив сохранил UID Mac 501, проверка root ownership
  корректно отказала. Исправлен только владелец нового дерева; installer
  дополнен `tar --no-same-owner --no-same-permissions`.
- 13:22: первая реальная двухканальная запись; цикл около 7.5 s.
- Exporter столкнулся с SQLite WAL metadata под ProtectSystem=strict.
  Воспроизведено `sqlite3.OperationalError: unable to open database file`
  в mount namespace exporter. Добавлен ReadWritePaths только каталога state;
  SQLite остается mode=ro/query_only, HTTP API ничего не записывает в историю.
- 13:24 и 13:26: реальные HTTPS/DNS/ICMP проверки обоих каналов успешны.
  В модель сохранения добавлен измеренный handshake_age, в exporter scope,
  reason/signal и handshake метрики. Добавлены 2 локальных теста, всего 78 PASS.
- 13:27:45: сквозная проверка Mac SSH/API, Prometheus, SQLite и копий кода:
  master matches server; SQLite integrity ok, 6 строк cycles (3 цикла × 2 канала).
  Оба канала UP, exporter слушает только 127.0.0.1:19106.

## Ресурсы и безопасность

После старта окончательной версии systemd MemoryCurrent: collector 15,433,728 B,
exporter 12,013,568 B. CPUUsageNSec: 2,768,434,000 и 262,058,000 соответственно
с запуска этих экземпляров. Это короткая проверка, не длительный baseline.
Лимиты: collector MemoryMax160M/CPUQuota30%, exporter64M/10%.

Installed helper SHA256 неизменен:
`2f883e3ea356b1d88719a148acb89a5b50ccc629b6b51fd619fe2f67ab88cde1`.
Guard check после установки: VALID generation=5. Маршруты и VPN peers не меняли.
Серверный HTTP exporter и локальный SSH forward доступны только по loopback.

## Evidence и мастер

Корень: `services/monitoring/timeweb-uplinks`.

- `evidence/20260911T131904Z-pilot-deployment/pre-install.tar.gz`;
  SHA256 `41c029de5ab9c735957f9e027ceaea82b123b582bc88c8557f2de3c9cc4268ee`.
- `evidence/20260911T132745Z-pilot-live/verification.json`: реальные API/Prometheus
  результаты, ресурсы, SQLite integrity и SHA256 локальных/серверных модулей.
- `pilot/deploy.py`, `bootstrap.sh`, `update.py`, `verify.py`: установка и проверки.
- `pilot/config.json`, systemd units, LaunchAgent plist, dashboard JSON и генератор.
- `pilot/prometheus.before.yml`: конфигурация локального Prometheus до добавления job.

Инструкция и откат: [../../TimeWeb_Uplink_Pilot_Quick_Guide](<../operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).
Откат пилота: остановить/disable два новых systemd units; не вызывать rollback
guardctl, не удалять историю. На Mac выгрузить только LaunchAgent пилота и удалить
только job timeweb-uplink-pilot, затем reload Prometheus. Не восстанавливать целиком
старый prometheus.yml поверх последующих чужих изменений.

## Оставшиеся ограничения

Дополнение после запуска: по просьбе пользователя retention сокращена до 7 дней.
Параметр `retention_days=7` применен в серверном config, collector перезапущен;
exporter и VPN не останавливались. Старых записей за пределами окна не было.
Резервная копия кода/config, live resource audit и synthetic 7-day load находятся
в `evidence/20260911-retention-7d/`. 79 тестов PASS, включая границу 7 дней.
План дальнейшей подкачки: [../../TimeWeb_Uplink_History_Sync_Plan](<../reference/TimeWeb_Uplink_History_Sync_Plan.md>).

- WG/firewall ABA не закрыт; маркировка PILOT обязательна.
- Snapshot expiry, runtime-only guards и отказ старого manifest сохраняются.
- Период 120 s не позволяет гарантированно заметить короткие обрывы.
- Локальный Prometheus не получает offline backfill. Автономная серверная история
  есть в SQLite/API, но еще не интегрирована как исторический datasource Grafana.
- Полные T01-T35, SIGKILL/orphan, watcher loss/overflow, долгий baseline и
  клиентский regression не объявляются принятыми этим коротким запуском.
- Не выполнялся намеренный обрыв живых WG для демонстрации DOWN.
