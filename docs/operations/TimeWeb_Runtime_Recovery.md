---
type: runbook
status: current
updated: 2026-09-28
tags: [vpn, recovery, maintenance]
---

> Storage migrated 2026-10-10. Current entry point: [Quick Guide](../quick-start.md); private configuration/backups: [storage rules](storage-and-transfer.md). Dated paths below describe their original release, not current masters.


# TimeWeb: постоянное восстановление runtime

Установлены `timeweb-runtime-recovery.service` и `timeweb-runtime-recovery.timer`. Сервис включён в загрузку ОС; timer каждые 15 секунд проверяет идентичность namespace и привязку policy к конфигурации. При неизменном namespace повторное восстановление не выполняется. Пользователю не нужно запускать recovery вручную.

## Источник и порядок

Код: `services/monitoring/timeweb-uplinks/pilot/runtime_recovery.py` и `rebind_after_reboot.py`. Deployment: `/opt/vpn-runtime-recovery/`. Текущий root-only policy — `policy.json`, состояние — `/var/lib/vpn-runtime-recovery/state.json`.

Policy публикуется из проверенного действующего состояния после BTH, FLEX и monitoring gates, а не из старого maintenance archive. Привязка включает hashes persistent WG configs, compose, клиентских/RU реестров, RU IP set, BTH contract и FLEX controllers. Endpoint двух uplink-конфигов нормализован: их значениями владеют transport controllers. Переключаемые FLEX routes и RU marks восстанавливаются из текущего per-device state, не из исторического выбора gateway.

1. Проверить тот же container ID/image, policy bindings и дождаться startup WG links.
2. Остановить конкурирующие FLEX/BTH timers/services, collector и console, закрепить свежий namespace.
3. Проверить частичный snapshot. Допустимы только известные потери рестарта, свои quarantine и Docker DNS ephemeral port pairs. Чужие RPDB/firewall/routes/peers не принимаются.
4. Добавить отсутствующую `inet ru_bth`, RPDB 180/181/190, два endpoint host routes; восстановить порядок только трёх legacy FORWARD и двух NAT rules. Общих flush нет. Существующая RU policy должна совпадать с утверждённой; она не переписывается поверх неизвестных правил.
5. Поднять необходимые WG/Xray WSS carriers по текущему transport state; проверить сохранённый и наблюдаемый UDP/WSS режим. Reconcile каждого зарегистрированного FLEX device с его текущими defaults/overrides, затем BTH recovery и полный read-back.
6. Monitoring rebind допускается только после строгой проверки baseline, BTH и всей fleet. Обновляются namespace binding и ownership generation; сохранён backup предыдущих manifest/state.
7. Вернуть timers, collector, exporter и console. Status `ready` означает завершённый recovery; успешный сетевой трафик дополнительно подтверждает collector.

В каждой namespace-команде повторно проверяется container identity; замена процесса в середине операции вызывает отказ. Ошибка оставляет collector остановленным и recovery в состоянии `failed`; timer повторяет попытку, но не принимает конфигурационный drift автоматически. Слишком ранний запуск при загрузке ждёт WG links; неготовая или неизвестная топология не считается успешным recovery.

## Gate после изменения туннелей

Агент выполняет эти команды после reviewed deployment и согласования BTH/monitoring contracts:

```bash
python3 /opt/vpn-runtime-recovery/runtime_recovery.py publish
python3 /opt/vpn-runtime-recovery/runtime_recovery.py check
```

`publish` проверяет живые BTH/FLEX/monitoring, сохраняет предыдущий policy и публикует новую generation. Это **не** способ согласовать неизвестный drift. Timer не вызывает `publish`. После добавления нового типа policy/table при необходимости обновляются код валидатора и тесты: hardcoded allowlist нельзя расширять без review.

Создание/удаление/переименование устройств и изменение controller/config требуют обновления policy агентом, не пользователем. При изменении режима Gateway/RU-direct обычные контроллеры сохраняют текущий state; отдельная publication не нужна. Для console lock paths также требуется соответствующий tmpfiles allowlist.

## Диагностика

```bash
systemctl status timeweb-runtime-recovery.service timeweb-runtime-recovery.timer
journalctl -u timeweb-runtime-recovery.service -n 30 --no-pager
python3 /opt/vpn-runtime-recovery/runtime_recovery.py check
```

Container recreate, другой image и неподтверждённые изменения persistent configuration намеренно вызывают отказ. Новый ID/image требует отдельного reviewed deployment и publication. Полное восстановление нового сервера из backup не реализуется этим сервисом.

Новый runtime policy, scripts, units, state, monitoring manifest/state/helper, FLEX controller/state и console tmpfiles включены в host backup; при наличии recovery unit verifier требует соответствующие файлы. Исторические архивы до установки recovery проверяются по прежнему составу, не переименовываются в новые.

Console status reads сериализованы с командами переключения и используют общий кэш 5 s. Это исключает параллельный запуск тяжёлых fleet checks несколькими вкладками; после команды кэш сбрасывается. Лимит памяти 128 МБ и sandbox сохранены. Console source также включён в backup.

## Приёмка 28 сентября

- 13 focused unit tests для частичных потерь, foreign drift, endpoint conflicts, duplicate RPDB, paired DNS ports, WSS carriers и monitoring rebind; 28 backup/scanner tests passed.
- Реальный `docker restart wg-relay`: автоматический recovery завершён в 04:29:41 UTC. Ручные команды восстановления не запускались.
- Первый reboot TimeWeb: boot `ec941102-c77e-4dee-b865-474cac2bdad4`, recovery завершён в 04:32:17 UTC после автоматического retry. Добавлено ожидание WG links перед snapshot. Финальный reboot с этим исправлением: boot `9e23e306-e8e1-4b6c-b896-5519eab8abec`, recovery 04:38:38 → 04:39:27 UTC, с первой попытки, без ручных repair-команд и failed units.
- Выбранные Gateway/RU-direct значения и клиентские ключи сохранены. Проверки реальных приложений на устройствах этим этапом не заменяются.
- 13 console tests passed, включая concurrent reads и invalidation после переключения. Шесть одновременных HTTP requests: все 200 за 5.76 s, peak memory 76,013,568 bytes, NRestarts=0 после deployment. До исправления concurrent subprocesses вызвали cgroup OOM; это отражено в отчёте, а не скрыто успешным recovery.
- `qemu-guest-agent` обновлён с `1:8.2.2+ds-0ubuntu1.11` до `.18`, hold снят, сервис active после restart и reboot. Основание старого hold в доступной документации не найдено; provider-side management вызовы из гостевой ОС не проверялись. [TimeWeb рекомендует штатный пакет и проверку systemd service](https://timeweb.cloud/docs/unix-guides/installing-qemu-agent).

Свежая verified копия до изменения: `.local/backups/timeweb/2026-09-28T042108Z_current-config/backup.tar.gz`, SHA-256 `ddc31681857c19616025fa334bf275f17fd19fbd775a1171a267de5122da2580`. Итоговый backup и результаты collector: [TimeWeb_Runtime_Recovery_2026-09-28](<../history/TimeWeb_Runtime_Recovery_2026-09-28.md>).
