# BTH: автоматическое восстановление, 2026-09-13

Пользователь подтвердил работу BTH на MacBook и iPhone. Настроено восстановление
его runtime peer без перезапуска Xray или старых WG. Клиентские профили не менялись.

## Размещение

- Мастер: services/transport/timeweb-reality/bth_recover.sh,
  prepare_bth_recovery.py, install_bth_recovery.sh, test_bth_recovery_contract.sh,
  test_bth_recovery_live.sh, bth-recovery.service и bth-recovery.timer.
- Защищенный release: services/transport/timeweb-reality/bth-recovery-release.
- TimeWeb: /opt/timeweb-reality/bth-recovery; root-only конфигурация и ключи.
- systemd bth-recovery.timer: OnBootSec=45s, OnUnitInactiveSec=120s, AccuracySec=5s.
- Состояние: /run/bth-recovery-state.json; журнал: journalctl -u bth-recovery.service.

Это краткий root oneshot, а не постоянный Xray worker. Новых пакетов не установлено.
Используются имеющиеся bash, jq, nft, wg, nsenter и Docker. Python только локально
через python3. Лимиты сервиса: 96 МиБ, CPUQuota=20%,
TasksMax=32, TimeoutStartSec=30s. Измеренный CPUUsageNSec одного запуска:
556323000 (около 0.56 CPU-секунды); MemoryPeak systemd не предоставил.

## Проверки перед восстановлением

Каждый запуск заново получает Docker ID/PID и открывает descriptor namespace.
В конце повторно сверяет ID/PID/namespace, не переиспользуя прежний PID manifest.
Проверяет image ID, bind mount, адрес 172.19.0.2, WG public key/port/address,
хеш постоянного wg-home.conf и Xray config, полный набор ip rules/table 300,
route get нового source, AllowedIPs остальных peers и канонический host guard.

Только после успешного аудита создает отсутствующую собственную таблицу
reality_b5 и peer 10.30.30.5/32. Несовпадающую существующую таблицу не перезаписывает.
При ошибке снимает только новый peer в закрепленном namespace. Guard не удаляется.
Основной Xray и Fornex/Cenuta не являются зависимыми units и не останавливаются.
Повторный успешный запуск не переустанавливает уже верный peer.

Таким образом, перезапуск с прежней конфигурацией может быть восстановлен,
но изменение образа, IP, правил, WG peers или Xray config потребует нового аудита
и обновления контракта. Старый runtime manifest не является разрешением на reapply.
WG config остается без нового peer; восстановление выполняет отдельный helper.

## Выполненные тесты

- Исходный контракт прошел --check; unit-файлы прошли systemd-analyze verify.
- В private mount namespaces подменены image, WG hash, routes, rules, hostguard,
  expected guard. Все шесть вариантов отвергнуты. Рабочий список peers неизменен.
- На production удалены только новый BTH peer и reality_b5, затем запущен service.
  Оба объекта восстановлены, AllowedIPs всех peers совпали с исходными.
- PID Xray и ID старого WG-контейнера не изменились. Повторный запуск идемпотентен.
- После восстановления: BTH IP 5.18.237.241 и ya.ru HTTP 200;
  Fornex/Cenuta HTTP 200 и прежние собственные IP.
- Наблюдалось следующее автоматическое срабатывание timer без ручного запуска:
  checked_unix=1789304716.968022, restored=false; timer active/enabled.
- Артефакты: stage9-test-20260913T160336 и stage8-test-20260913T160337 в master.

Полная перезагрузка TimeWeb и пересоздание production контейнера не выполнялись.
Тест удаления peer/guard не заменяет приемку нового namespace после reboot.
Проверки раз в 120 секунд не являются непрерывным монитором ABA/конкурентных
изменений. Самовольный firewall flush между проверками этим не исключается.
Для отсутствующего маршрута к дому source guard запрещает иной исходящий интерфейс.

## Backup и отключение

Backup: .local/backups/timeweb/2026-09-13T1257Z_pre-reality/backup.tar.gz,
15771086 байт, SHA256 c50aa266112559db397188e27575a0a52b2dcc3f70882593c0c0c08ed9048f06.
Архив/хеши проверены; full-machine restore не проводился.

install_bth_recovery.sh rollback отключает только timer/service, сверив unit-файлы.
Текущий BTH peer остается runtime-only; configs и ключи сохраняются для аудита.
Перед полным откатом BTH отключить этот timer, затем использовать scoped rollback
этапа 9. Не удалять guards при продолжающемся новом пользовательском трафике.
